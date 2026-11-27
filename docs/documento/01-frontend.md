# Especificación, arquitectura y análisis del programa fuente

## Resumen

Este documento describe un compilador completo para MiniLang, un lenguaje imperativo pequeño con dos tipos (`int` y `bool`), expresiones con precedencia definida, bloques con ámbito propio, `if/else`, `while`, `print` y funciones con parámetros y retorno. El compilador está escrito en Python 3.12 sin dependencias externas y recorre todas las fases clásicas: análisis léxico, análisis sintáctico con construcción de un árbol de sintaxis abstracta (AST), tabla de símbolos y análisis semántico, código intermedio de tres direcciones, un optimizador local y generación de código para una máquina de pila que el propio proyecto simula. Un solo comando compila y ejecuta un archivo `.src` y, si se pide, muestra el artefacto de cada fase. Cada fase reporta los errores que encuentra con su tipo, línea y columna, y las de análisis siguen después del primero para informar varios a la vez. El repositorio incluye 184 pruebas automatizadas por fase y de extremo a extremo, y los artefactos de tres programas de ejemplo.

## Objetivos

- Definir un lenguaje de tamaño controlado con una especificación y una gramática sin ambigüedades.
- Implementar cada fase como un módulo con una interfaz explícita, de modo que se pueda probar sola y que el contrato entre fases quede escrito.
- Reportar errores léxicos, sintácticos, semánticos y de ejecución con su ubicación, sin fallos silenciosos y, en el análisis, sin detenerse en el primero.
- Traducir el programa a código intermedio, mejorarlo con al menos una optimización local cuya corrección se pueda justificar, y ejecutarlo en una máquina de pila.
- Dejar evidencia reproducible: pruebas por fase, artefactos versionados y un comando documentado.

## 1. Especificación del lenguaje

La especificación completa está en `docs/especificacion-lenguaje.md`. Esta sección resume las decisiones y el porqué de cada una.

### 1.1 Tokens

| Categoría | Patrón | Ejemplos |
|---|---|---|
| Identificador | `[A-Za-z_][A-Za-z0-9_]*`, que no sea palabra reservada | `x`, `_total`, `valor2` |
| Entero | `0 \| [1-9][0-9]*`, de 0 a 2 147 483 647 | `0`, `42` |
| Booleano | `true \| false` | `true` |
| Palabras reservadas | `int bool if else while print func return` | |
| Operadores | `+ - * / % == != < <= > >= && \|\| ! =` | |
| Delimitadores | `( ) { } ; , :` | |
| Comentarios | `// hasta el fin de línea` y `/* de bloque */`, sin anidar | |

Los enteros no tienen signo en el léxico: `-5` es el operador unario aplicado a `5`. Así el lexer no necesita saber si un `-` es una resta o un signo, que es una decisión que depende del contexto y le corresponde al parser. El límite de 2 147 483 647 viene de que un `int` es un entero con signo de 32 bits. Se prohíben los ceros iniciales (`007`) para que cada número tenga una sola forma de escribirse. No hay cadenas: la guía las deja como opcionales y `print` con enteros y booleanos basta para mostrar la salida de los programas.

### 1.2 Tipos

| Tipo | Valores | Valor inicial si se declara sin asignar |
|---|---|---|
| `int` | enteros con signo de 32 bits | `0` |
| `bool` | `true`, `false` | `false` |

No hay conversiones implícitas entre `int` y `bool`. Una condición tiene que ser `bool` (`if (x)` con `x` entero es un error), lo que evita una fuente común de errores en C. Dar un valor inicial a toda variable declarada evita que exista un estado "sin valor" en el programa principal.

### 1.3 Operadores y precedencia

De menor a mayor precedencia:

| Nivel | Operadores | Asociatividad | Operandos → resultado |
|---|---|---|---|
| 1 | `\|\|` | izquierda | `bool, bool → bool` |
| 2 | `&&` | izquierda | `bool, bool → bool` |
| 3 | `==` `!=` | izquierda | dos del mismo tipo → `bool` |
| 4 | `<` `<=` `>` `>=` | izquierda | `int, int → bool` |
| 5 | `+` `-` | izquierda | `int, int → int` |
| 6 | `*` `/` `%` | izquierda | `int, int → int` |
| 7 | `-` `!` (unarios) | derecha | `-`: `int → int`; `!`: `bool → bool` |

La tabla sigue el orden de C, que es el que el equipo ya conocía. La división es entera y trunca hacia cero, y el residuo toma el signo del dividendo (`-7 / 2 = -3`, `-7 % 2 = -1`), también como en C. Dividir entre cero es un error de ejecución. `&&` y `||` evalúan los dos operandos, sin cortocircuito: como las expresiones no tienen efectos laterales salvo las llamadas a funciones, la diferencia solo se nota si un operando llama a una función que imprime, y a cambio la traducción a código intermedio queda más simple.

### 1.4 Sentencias y funciones

```
int x;                    // declaración, x vale 0
bool listo = true;        // declaración con valor inicial
x = x + 1;                // asignación
{ int y = 2; }            // bloque: abre un ámbito nuevo
if (x > 0) { ... } else if (x < 0) { ... } else { ... }
while (x < 10) { ... }    // ciclo
print(x);                 // imprime un int o un bool
saludar(3);               // llamada a procedimiento como sentencia
return x;                 // dentro de una función

func suma(int a, int b): int {   // función: regresa int
    return a + b;
}
func saludar(int veces) {        // procedimiento: no regresa valor
    print(veces);
}
```

El cuerpo de `if`, `else` y `while` siempre lleva llaves. Con eso desaparece el problema del `else` colgante y la gramática no necesita reglas especiales para resolverlo. Las funciones se declaran solo en el nivel superior, reciben sus parámetros por valor y pueden ser recursivas. Una función se puede llamar antes de su declaración en el texto; una variable, no. Las sentencias del nivel superior forman el programa principal y sus variables son globales.

### 1.5 Ejemplo

```
func factorial(int n): int {
    int r = 1;
    while (n > 1) {
        r = r * n;
        n = n - 1;
    }
    return r;
}

print(factorial(5));   // 120
```

## 2. Arquitectura general

```
 programa.src
      │ texto
      ▼
 ┌────────┐ tokens ┌────────┐  AST  ┌────────────┐ AST con tipos ┌──────┐
 │ lexer  │───────►│ parser │──────►│ semántico  │──────────────►│  IR  │
 └────────┘        └────────┘       │ + tabla de │               └──┬───┘
                                    │  símbolos  │                  │ tres direcciones
                                    └────────────┘                  ▼
                                                             ┌─────────────┐
                                                             │ optimizador │
                                                             └──────┬──────┘
                                                                    │ tres direcciones
                                                                    ▼
          salida  ┌─────────┐   código de pila   ┌───────────┐
        ◄─────────│ máquina │◄───────────────────│ generador │
                  └─────────┘                    └───────────┘
```

El compilador sigue la división clásica en tres partes. El front-end (lexer, parser y semántico) entiende el programa y rechaza los incorrectos. El middle-end (código intermedio y optimizador) lo traduce a una forma independiente del lenguaje y de la máquina. El back-end (generador y máquina de pila) produce el código objetivo y lo ejecuta.

| Fase | Entrada | Salida | Módulo |
|---|---|---|---|
| Léxico | texto | lista de tokens y errores | `src/lexer/` |
| Sintáctico | tokens | AST y errores | `src/parser/`, `src/ast/` |
| Semántico | AST | AST anotado con tipos, tabla de símbolos y errores | `src/semantic/` |
| Código intermedio | AST anotado | instrucciones de tres direcciones | `src/ir/` |
| Optimizador | instrucciones | instrucciones equivalentes, menos | `src/optimizer/` |
| Generador | instrucciones | líneas de código de pila | `src/backend/generador.py` |
| Máquina | líneas de código de pila | salida del programa o un error | `src/backend/maquina.py` |

Tres reglas sostienen la integración. Todos los errores son del mismo tipo (`ErrorCompilacion` con fase, mensaje, línea y columna), así que el comando los imprime igual sin importar quién los produjo. Ninguna fase lanza una excepción por un error del programa: lo agrega a una lista y sigue, y por eso un archivo con varios errores los reporta todos. Y el comando único (`src/main.py`) corre las fases en orden y se detiene después de la primera que tenga errores, porque una fase no puede trabajar con la salida incompleta de la anterior: un AST con huecos daría errores semánticos falsos.

El contrato entre fases (los campos de cada nodo del AST, la interfaz de la tabla de símbolos, el formato del código intermedio y el repertorio de la máquina) se escribió en `docs/arquitectura.md` antes de que cada integrante empezara su parte. Eso permitió trabajar en paralelo: el semántico, el código intermedio y el backend se programaron contra el contrato y se integraron después. Los ajustes que salieron en la revisión (por ejemplo, que los nombres internos del código intermedio empiecen con `@` o el valor inicial de una variable declarada sin valor) se acordaron y se anotaron en el mismo contrato.

El comando es:

```
python -m src.main <archivo.src> [--tokens] [--ast] [--simbolos] [--ir] [--ir-opt] [--objetivo] [--todo]
```

Sin opciones compila y ejecuta. Cada opción imprime el artefacto de su fase, y `--todo` los imprime todos. El código de pila se guarda en `build/<nombre>.pila`. El comando termina con `0` si todo salió bien, `1` si hubo errores del programa y `2` si no se pudo leer el archivo.

## 3. Análisis léxico

### 3.1 Estrategia

El lexer (`src/lexer/lexer.py`) está escrito a mano y recorre el texto carácter por carácter. Cada token se reconoce por su primer carácter: un dígito empieza un número, una letra o `_` empieza un identificador, y los operadores y delimitadores se buscan en dos tablas. Las expresiones regulares de la tabla de tokens son la especificación de los patrones. El código las implementa como un autómata escrito con condiciones, que avanza mientras el carácter siguiente siga perteneciendo al patrón.

Se aplica la regla de máxima coincidencia. Para los operadores que pueden tener uno o dos caracteres (`=` y `==`, `!` y `!=`, `<` y `<=`, `>` y `>=`) el lexer mira el carácter siguiente antes de decidir, así que `<=` es un solo token. Para los identificadores consume todas las letras, dígitos y `_` seguidos y solo al final revisa si el lexema es una palabra reservada. Por eso `integer` es un identificador y no `int` seguido de `eger`, y `true` y `false` se reconocen igual, como literales booleanos.

Los espacios, tabuladores, saltos de línea y comentarios se descartan sin producir tokens. El lexer lleva la línea y la columna de cada carácter, y cada token guarda la posición de su primer carácter, que es la que usan todos los mensajes de error del compilador. La lista siempre termina con un token `EOF`, que le permite al parser saber que el programa acabó sin revisar el tamaño de la lista.

Cada token tiene tipo, lexema, valor y posición. Con `int x = 10; // contador` seguido de `if (x >= 5) { print(x); }`, el comando con `--tokens` imprime (línea:columna, tipo y lexema):

```
1:1	INT	'int'
1:5	ID	'x'
1:7	ASIGNAR	'='
1:9	LIT_ENTERO	'10'
1:11	PUNTO_COMA	';'
2:1	IF	'if'
2:4	PAR_IZQ	'('
2:5	ID	'x'
2:7	MAYOR_IGUAL	'>='
2:10	LIT_ENTERO	'5'
2:11	PAR_DER	')'
2:13	LLAVE_IZQ	'{'
2:15	PRINT	'print'
2:20	PAR_IZQ	'('
2:21	ID	'x'
2:22	PAR_DER	')'
2:23	PUNTO_COMA	';'
2:25	LLAVE_DER	'}'
3:1	EOF	''
```

El comentario no aparece y `>=` es un solo token.

### 3.2 Errores léxicos

Un error léxico no detiene el análisis: se registra y el lexer continúa con el carácter siguiente, así que un archivo con varios errores los reporta todos. Los errores que se detectan son:

| Error | Ejemplo | Mensaje |
|---|---|---|
| Carácter que no pertenece al lenguaje | `@`, `$` | `carácter no válido '@'` |
| `&` o `\|` solo | `a & b` | `se esperaba '&&' y se encontró '&' solo` |
| Entero con cero inicial | `007` | `entero con cero inicial: '007'` |
| Entero mayor que el máximo | `2147483648` | `entero fuera de rango (máximo 2147483647): '2147483648'` |
| Número pegado a letras | `9x` | `identificador no puede empezar con dígito: '9x'` |
| Comentario de bloque sin cerrar | `/* ...` | `comentario de bloque sin cerrar` |

Un número pegado a letras (`9x`) se trata como un solo lexema inválido y no como el número `9` seguido del identificador `x`. Si se separara en dos tokens, el error aparecería después, en el parser, con un mensaje confuso sobre un identificador inesperado. Con este archivo:

```
int 9x = 1;
int y = 08;
bool z = a | b;
/* sin cerrar
```

el compilador reporta los cuatro errores en una sola corrida:

```
Error léxico [línea 1, columna 5]: identificador no puede empezar con dígito: '9x'
Error léxico [línea 2, columna 9]: entero con cero inicial: '08'
Error léxico [línea 3, columna 12]: se esperaba '||' y se encontró '|' solo
Error léxico [línea 4, columna 1]: comentario de bloque sin cerrar
```

## 4. Análisis sintáctico

### 4.1 Gramática

La gramática final, en EBNF, es la que implementa el parser (`{ X }` es cero o más veces y `[ X ]` es opcional). Está completa en el anexo A y en `docs/gramatica.md`. La parte de expresiones tiene un no terminal por nivel de precedencia:

```
expresion  → o
o          → y { "||" y }
y          → igualdad { "&&" igualdad }
igualdad   → relacional { ( "==" | "!=" ) relacional }
relacional → suma { ( "<" | "<=" | ">" | ">=" ) suma }
suma       → producto { ( "+" | "-" ) producto }
producto   → unaria { ( "*" | "/" | "%" ) unaria }
unaria     → ( "-" | "!" ) unaria | primaria
primaria   → ENTERO | BOOLEANO | ID | llamada | "(" expresion ")"
```

### 4.2 Transformaciones

La gramática natural de expresiones, `E → E "+" E | E "*" E | "(" E ")" | ID | ENTERO`, es ambigua y recursiva por la izquierda. Para llegar a la de arriba se aplicaron cuatro transformaciones:

1. **Niveles de precedencia.** Un no terminal por nivel, del operador más débil al más fuerte. Así `2 + 3 * 4` tiene un solo árbol posible, con la multiplicación abajo.
2. **Eliminación de la recursión izquierda.** Una regla como `suma → suma "+" producto | producto` hace que un parser descendente se llame a sí mismo sin consumir tokens, para siempre. Se reescribe como `suma → producto suma'` y `suma' → "+" producto suma' | ε`.
3. **Repetición en lugar de recursión.** `suma'` se escribe como `{ "+" producto }`, que en el código es un ciclo `while`. El ciclo construye el árbol hacia la izquierda, y por eso la asociatividad sigue siendo la correcta aunque la gramática transformada sea recursiva por la derecha.
4. **Factorización por la izquierda.** La asignación y la llamada usada como sentencia empiezan con `ID`, igual que una variable y una llamada dentro de una expresión. El parser decide viendo el token siguiente: `=` es asignación y `(` es llamada.

Con eso la gramática es LL(2): toda decisión se toma con el token actual y, solo cuando el actual es un identificador, con el siguiente.

### 4.3 Método de parsing

El parser (`src/parser/parser.py`) es descendente recursivo y está escrito a mano, sin generadores: un método por no terminal. Se eligió así porque cada método se parece a su regla de la gramática y se puede revisar comparando uno con otra, y porque permite mensajes de error escritos para cada caso ("se esperaba ';'", "'}' para cerrar el bloque abierto en la línea 4"). Los seis niveles de operadores binarios comparten un solo método que recibe el nivel como parámetro y recorre la tabla de precedencia, en lugar de seis métodos casi iguales.

El efecto de la precedencia y de la asociatividad se ve en el AST de `print(10 - 3 - 4);` y `print(2 + 3 * 4);`:

```
Programa  (1:1)
├── Print  (1:1)
│   └── Binaria operador='-'  (1:14)
│       ├── Binaria operador='-'  (1:10)
│       │   ├── Entero valor=10  (1:7)
│       │   └── Entero valor=3  (1:12)
│       └── Entero valor=4  (1:16)
└── Print  (2:1)
    └── Binaria operador='+'  (2:9)
        ├── Entero valor=2  (2:7)
        └── Binaria operador='*'  (2:13)
            ├── Entero valor=3  (2:11)
            └── Entero valor=4  (2:15)
```

La primera resta queda abajo, así que se calcula `(10 - 3) - 4 = 3`. En la segunda línea la multiplicación queda debajo de la suma, así que se calcula `2 + (3 * 4) = 14`. Son los valores que imprime el programa.

### 4.4 Recuperación de errores

El parser usa recuperación en modo pánico. Cuando encuentra un token que no esperaba:

1. Registra el error con la línea y la columna del token, lo que esperaba y lo que encontró.
2. Abandona la sentencia que estaba analizando.
3. Descarta tokens hasta un punto seguro: justo después de un `;`, o antes de `{`, `}` o de una palabra que inicia sentencia (`int`, `bool`, `if`, `while`, `print`, `return`, `func`).
4. Sigue analizando desde ahí.

Si el error está en el primer token de la sentencia, ese token se descarta antes de sincronizar. Sin esa regla, un token que no puede iniciar ninguna sentencia (una `}` suelta, por ejemplo) produciría el mismo error una y otra vez sin avanzar. Internamente, el error sube con una excepción privada del parser hasta el método que analiza la sentencia, que la atrapa y sincroniza; hacia afuera el parser nunca lanza excepciones y regresa el AST con las sentencias correctas y la lista de errores.

`examples/error_sintactico.src` tiene tres errores:

```
// Tres errores sintácticos: falta ';', falta ')' y una expresión incompleta
int a = 3
int b = 4;
if (a < b {
    print(a);
}
print(a + );
```

y el compilador reporta los tres:

```
Error sintáctico [línea 3, columna 1]: se esperaba ';' y se encontró 'int'
Error sintáctico [línea 4, columna 11]: se esperaba ')' y se encontró '{'
Error sintáctico [línea 7, columna 11]: se esperaba una expresión (número, true/false, variable, llamada o '(') y se encontró ')'
```

El primer error se reporta en la línea 3 porque ahí está el token que delata la falta del `;`: hasta ver `int` el parser no puede saber que la declaración terminó. Como `int` inicia una sentencia, la recuperación se detiene justo ahí y la declaración de `b` se analiza bien. En el `if`, la recuperación se detiene en la `{` y el bloque se analiza como un bloque suelto, sin reportar nada más. En el último `print`, descarta tokens hasta después del `;`.

## 5. Árbol de sintaxis abstracta

### 5.1 Diseño de los nodos

El AST (`src/ast/nodos.py`) usa una clase por construcción del lenguaje. Todo nodo guarda la línea y la columna donde empieza, que las fases siguientes usan en sus mensajes de error. Toda expresión tiene además un campo `tipo`, vacío al salir del parser y llenado por el análisis semántico con `int` o `bool`; el código intermedio lo usa sin volver a consultar la tabla de símbolos.

| Nodo | Campos | Notas |
|---|---|---|
| `Programa` | `elementos` | funciones y sentencias en el orden del fuente |
| `Funcion` | `nombre`, `parametros`, `tipo_retorno`, `cuerpo` | sin `tipo_retorno` es un procedimiento |
| `Parametro` | `tipo_dato`, `nombre` | |
| `Bloque` | `sentencias` | abre un ámbito |
| `DeclVar` | `tipo_dato`, `nombre`, `inicial` | `inicial` puede faltar |
| `Asignacion` | `nombre`, `valor` | |
| `If` | `condicion`, `entonces`, `sino` | un `If` en `sino` es un `else if` |
| `While` | `condicion`, `cuerpo` | |
| `Print` | `valor` | |
| `Return` | `valor` | puede faltar |
| `SentenciaExpr` | `expresion` | una llamada usada como sentencia |
| `Entero`, `Booleano` | `valor` | literales |
| `Identificador` | `nombre` | |
| `Binaria` | `operador`, `izquierda`, `derecha` | la posición es la del operador |
| `Unaria` | `operador`, `operando` | `-` o `!` |
| `Llamada` | `nombre`, `argumentos` | |

Hay tres decisiones que vale la pena explicar. Los paréntesis no tienen nodo: solo cambian la forma del árbol, y después del parser ya no hacen falta. El `else if` no tiene un nodo propio, porque es un `If` dentro del `sino` de otro, y así ninguna fase necesita una regla aparte para él. Y la posición de una operación binaria es la de su operador y no la de su primer operando, porque es el lugar que conviene señalar cuando la operación tiene tipos incorrectos.

Los nodos se recorren con el patrón visitor (`src/ast/visitor.py`). Cada fase hereda de `Visitor` y define un método `visitar_<Nodo>` para cada nodo que le interesa; los demás se recorren solos, visitando sus hijos. El semántico, el generador de código intermedio y la impresión del árbol usan el mismo mecanismo.

### 5.2 Ejemplo

Para este programa:

```
func doble(int n): int {
    return n * 2;
}
int a = 1 + doble(3) * 2;
if (a > 10 && !false) {
    print(a);
} else {
    print(0);
}
```

el comando con `--ast` imprime el árbol con la posición (línea:columna) de cada nodo:

```
Programa  (1:1)
├── Funcion nombre='doble' tipo_retorno='int'  (1:1)
│   ├── Parametro tipo_dato='int' nombre='n'  (1:12)
│   └── Bloque  (1:24)
│       └── Return  (2:5)
│           └── Binaria operador='*'  (2:14)
│               ├── Identificador nombre='n'  (2:12)
│               └── Entero valor=2  (2:16)
├── DeclVar tipo_dato='int' nombre='a'  (4:1)
│   └── Binaria operador='+'  (4:11)
│       ├── Entero valor=1  (4:9)
│       └── Binaria operador='*'  (4:22)
│           ├── Llamada nombre='doble'  (4:13)
│           │   └── Entero valor=3  (4:19)
│           └── Entero valor=2  (4:24)
└── If  (5:1)
    ├── Binaria operador='&&'  (5:12)
    │   ├── Binaria operador='>'  (5:7)
    │   │   ├── Identificador nombre='a'  (5:5)
    │   │   └── Entero valor=10  (5:9)
    │   └── Unaria operador='!'  (5:15)
    │       └── Booleano valor=False  (5:16)
    ├── Bloque  (5:23)
    │   └── Print  (6:5)
    │       └── Identificador nombre='a'  (6:11)
    └── Bloque  (7:8)
        └── Print  (8:5)
            └── Entero valor=0  (8:11)
```

La llamada `doble(3)` es una expresión más, y por la precedencia queda debajo de la multiplicación y esta debajo de la suma. El `If` tiene tres hijos: la condición, el bloque del `entonces` y el del `sino`. El programa imprime `13`.

## 6. Limitaciones del front-end

- **Sin cadenas, arreglos ni lectura de datos.** El lenguaje solo tiene `int` y `bool`, y la única salida es `print`. La guía pide como mínimo dos tipos e impresión, y agregar cadenas habría exigido otro tipo en todas las fases, incluida la máquina.
- **Un error léxico detiene la compilación después del léxico.** El lexer reporta todos sus errores, pero el parser no corre sobre una lista de tokens con huecos, para no producir errores sintácticos falsos.
- **La recuperación en modo pánico puede saltarse código.** Después de un error se descartan tokens hasta un punto seguro, y un segundo error dentro del tramo descartado no se reporta hasta corregir el primero.
- **Un solo archivo por programa.** No hay módulos ni inclusión de otros archivos.

## 7. Uso de IA

Se usó Claude Code (Anthropic) para esta parte. Generó el lexer, el parser, los nodos del AST con su visitor e impresión, las pruebas léxicas y sintácticas, la especificación, la gramática y el contrato entre fases de `docs/arquitectura.md`, a partir de la guía del proyecto y de las decisiones que tomé sobre el lenguaje. También ayudó a revisar los cambios de los compañeros antes de integrarlos y a redactar esta sección. Revisé el código y las pruebas antes de fusionarlos. Todos los listados de este documento se obtuvieron ejecutando el compilador.

## 8. Conclusión personal

Lo que más me enseñó esta parte fue que la gramática que uno escribe primero casi nunca es la que se puede programar. La versión natural de las expresiones es ambigua y recursiva por la izquierda, y cada transformación para arreglarla parecía cambiar el lenguaje, hasta que vi en el árbol de `10 - 3 - 4` que el ciclo del parser conserva la asociatividad aunque la regla ya no la muestre. La recuperación de errores me costó más de lo que esperaba: reportar el primer error es fácil, pero seguir sin inventar errores falsos depende de elegir bien dónde sincronizar, y sin descartar el primer token una `}` suelta habría dejado al parser repitiendo el mismo error para siempre. Coordinar al equipo me dejó otra lección: escribir el contrato entre fases antes de programar fue lo que permitió que cuatro personas trabajaran en paralelo y que la integración se resolviera con ajustes pequeños y no reescribiendo fases.
