# Arquitectura y contrato entre fases

## 1. Diagrama de fases

```
 programa.src
      │  texto
      ▼
 ┌──────────┐ tokens  ┌──────────┐  AST   ┌─────────────┐ AST con tipos ┌──────────┐
 │  lexer   │────────▶│  parser  │───────▶│  semántico  │──────────────▶│    ir    │
 └──────────┘         └──────────┘        │ + tabla de  │ + tabla       └────┬─────┘
  src/lexer/           src/parser/        │  símbolos   │                    │ tres direcciones
                       src/ast/           └─────────────┘                    ▼
                                           src/semantic/              ┌────────────┐
                                                                      │ optimizador│
                                                                      └────┬───────┘
                                                                           │ tres direcciones
                                                                           ▼
                                                    salida  ┌──────────┐ código de pila ┌───────────┐
                                                  ◀─────────│ máquina  │◀───────────────│ generador │
                                                            └──────────┘                └───────────┘
                                                              src/backend/
```

Front-end: lexer, parser, semántico. Middle-end: IR y optimizador. Back-end: generador y máquina de pila.

| Fase | Entrada | Salida | Función de entrada | Responsable |
|---|---|---|---|---|
| Léxico | `str` | `list[Token]`, errores | `src.lexer.tokenizar(fuente)` | Miguel |
| Sintáctico | `list[Token]` | `Programa`, errores | `src.parser.analizar(tokens)` | Miguel |
| Semántico | `Programa` | `Programa` con `tipo` en cada expresión, `TablaSimbolos`, errores | `src.semantic.analizar(programa)` | Iván |
| IR | `Programa` anotado | `list[Instruccion]` | `src.ir.generar(programa)` | Aldo |
| Optimizador | `list[Instruccion]` | `list[Instruccion]` | `src.optimizer.optimizar(instrucciones)` | Aldo |
| Generador | `list[Instruccion]` | `list[str]` (código de pila) | `src.backend.generar(instrucciones)` | Zareth |
| Máquina | `list[str]` | salida impresa, errores | `src.backend.ejecutar(codigo)` | Zareth |

Reglas comunes:
- Todos los errores son `src.errores.ErrorCompilacion(fase, mensaje, linea, columna)`. Ninguna fase lanza excepciones
  por un error del programa: los junta en una lista y sigue.
- Cada fase devuelve una tupla `(resultado, errores)` si puede fallar (léxico, sintáctico, semántico, máquina).
- `src/main.py` corre las fases en orden y se detiene después de la primera que tenga errores.
- Ninguna fase modifica la entrada de otra salvo el semántico, que solo llena el campo `tipo` de las expresiones
  y el campo `nombre_unico` (sección 4).

## 2. Tokens

`Token(tipo: TipoToken, lexema: str, valor: int | bool | None, linea: int, columna: int)`, en `src/lexer/tokens.py`.
`valor` solo se llena en `LIT_ENTERO` y `LIT_BOOL`. La lista siempre termina en un token `EOF`.

## 3. AST

Definido en `src/ast/nodos.py`. Todo nodo tiene `linea` y `columna`. Toda expresión tiene además `tipo`
(`None` al salir del parser, `"int"` o `"bool"` después del semántico).

| Nodo | Campos | Notas |
|---|---|---|
| `Programa` | `elementos: list[Funcion \| sentencia]` | en el orden del fuente |
| `Funcion` | `nombre`, `parametros: list[Parametro]`, `tipo_retorno: str \| None`, `cuerpo: Bloque` | `None` = procedimiento |
| `Parametro` | `tipo_dato`, `nombre` | |
| `Bloque` | `sentencias: list` | abre un ámbito |
| `DeclVar` | `tipo_dato`, `nombre`, `inicial: Expresion \| None` | |
| `Asignacion` | `nombre`, `valor` | |
| `If` | `condicion`, `entonces: Bloque`, `sino: Bloque \| If \| None` | un `If` en `sino` es un `else if` |
| `While` | `condicion`, `cuerpo: Bloque` | |
| `Print` | `valor` | |
| `Return` | `valor: Expresion \| None` | |
| `SentenciaExpr` | `expresion: Llamada` | llamada usada como sentencia |
| `Entero` | `valor: int` | expresión |
| `Booleano` | `valor: bool` | expresión |
| `Identificador` | `nombre` | expresión |
| `Binaria` | `operador`, `izquierda`, `derecha` | posición = la del operador |
| `Unaria` | `operador` (`-` o `!`), `operando` | |
| `Llamada` | `nombre`, `argumentos: list` | expresión |

**Recorrido:** heredar de `src.ast.Visitor` y definir `visitar_<Nodo>(self, nodo)`; los nodos sin método propio se
recorren solos (`visitar_generico`). `src.ast.arbol_texto(programa, mostrar_tipos=True)` imprime el árbol.

## 4. Tabla de símbolos y semántico (Iván)

Lo que necesitan las fases siguientes de `TablaSimbolos`:
- Por cada símbolo: `nombre`, `categoria` (`"variable"`, `"parametro"`, `"funcion"`), `tipo`, `linea`, el ámbito donde
  vive y, para funciones, la lista de tipos de sus parámetros y el tipo de retorno.
- Un método para imprimirla por ámbitos (artefacto obligatorio).

El IR no necesita la tabla: le basta el campo `tipo` de las expresiones. Por eso **los nombres de variable no se
renombran** en el campo `nombre`: si un bloque interno oculta una variable externa, el semántico llena el campo
`nombre_unico` de `Identificador`, `DeclVar`, `Asignacion` y `Parametro` (por ejemplo `x` y `x_1`). Aldo usa
`nombre_unico` si no es `None`, y si no, `nombre`.

Catálogo mínimo de errores semánticos: variable no declarada, redeclaración en el mismo ámbito, función no declarada,
número o tipo de argumentos incorrecto, tipos incompatibles en asignación, declaración, operador o `print`, condición
que no es `bool`, `return` con tipo incorrecto o fuera de función, función con retorno sin `return` en todos los
caminos, usar un procedimiento como valor.

### 4.1 Interfaz

`src.semantic.analizar(programa) -> (TablaSimbolos, list[ErrorCompilacion])`. El `Programa` se anota en su lugar
(campos `tipo` y `nombre_unico`), por eso no se regresa. Para probar la fase sola sobre un archivo:
`python -m src.semantic <archivo.src> [--ast]`, que imprime la tabla (y el AST con tipos) o los errores.

- `TablaSimbolos`: `abrir(nombre)`, `cerrar()`, `declarar(simbolo)` (regresa el símbolo previo si es redeclaración),
  `buscar(nombre)` (del ámbito actual al global), `ambitos()` y `texto()`. Los ámbitos cerrados se conservan para
  poder imprimir la tabla completa al final.
- `Simbolo(nombre, categoria, tipo, linea, columna, tipos_parametros, nombre_unico, ambito)`. En una función, `tipo`
  es el tipo de retorno (`None` = procedimiento) y `tipos_parametros` la lista de tipos de sus parámetros.
- Cada error es un `ErrorSemantico`, subclase de `ErrorCompilacion` con el campo extra `codigo` del catálogo.

### 4.2 Reglas de alcance

- Primero se registran todas las funciones en el ámbito global; después se recorre el programa en orden. Por eso una
  función se puede llamar antes de su declaración, pero una variable global solo después de la suya.
- El cuerpo de una función comparte ámbito con sus parámetros: `func f(int a) { int a; }` es redeclaración. Un bloque
  dentro del cuerpo sí puede ocultar un parámetro.
- El valor inicial se revisa antes de declarar la variable: en `int x = x + 1;` la `x` de la derecha es otra (una
  externa) o un error.
- `nombre_unico`: la primera variable o parámetro con un nombre lo conserva (`nombre_unico = None`); cada declaración
  posterior con el mismo nombre, en cualquier ámbito, recibe `x_1`, `x_2`, …, saltando los nombres que ya existan en
  el programa. Así cada variable del IR es distinta aunque la máquina busque primero en el marco y luego en globales.
- La llamada a un procedimiento usada como sentencia (`SentenciaExpr`) queda con `tipo = None`; toda otra expresión
  de un programa sin errores tiene `tipo`.

### 4.3 Catálogo de errores semánticos

Todos son de fase `"semántico"` y se imprimen como `Error semántico [línea L, columna C]: mensaje`. El análisis no se
detiene en el primero: junta todos y los entrega ordenados por línea y columna. Una expresión con error queda sin tipo
y las que la contienen no reportan otro error por ella (un error del programa = un mensaje).

| Código | Error | Posición | Ejemplo de mensaje |
|---|---|---|---|
| S01 | Variable no declarada (o usada fuera de su ámbito, o antes de declararse) | el identificador | `la variable 'y' no está declarada` |
| S02 | Redeclaración en el mismo ámbito (variable, parámetro o función) | la segunda declaración | `'x' ya está declarado en este ámbito (línea 1)` |
| S03 | Función no declarada | la llamada | `la función 'triple' no está declarada` |
| S04 | Número de argumentos incorrecto | la llamada | `'f' espera 2 argumento(s) y recibió 1` |
| S05 | Tipo de argumento incorrecto | el argumento | `el argumento 2 de 'f' debe ser bool y es int` |
| S06 | Tipos incompatibles en asignación | el valor | `no se puede asignar un valor bool a 'x', que es int` |
| S07 | Tipos incompatibles en declaración | el valor inicial | `'b' es bool y se inicializa con un valor int` |
| S08 | Operador con operandos de tipo incorrecto | el operador | `el operador '+' necesita int y int, y recibió int y bool` |
| S09 | Condición de `if` o `while` que no es `bool` | la condición | `la condición del 'if' debe ser bool y es int` |
| S10 | `return` fuera de una función | el `return` | `'return' fuera de una función` |
| S11 | `return` con valor de tipo incorrecto | el valor | `'f' debe regresar bool y regresa int` |
| S12 | `return` sin valor en una función, o con valor en un procedimiento | el `return` | `'f' debe regresar un valor int` |
| S13 | Función con tipo de retorno que no regresa en todos los caminos | la función | `la función 'f' no regresa un valor en todos los caminos` |
| S14 | Procedimiento usado como valor (en una expresión o en `print`) | la llamada | `'p' es un procedimiento: no regresa un valor que se pueda usar` |
| S15 | Función usada como variable | el identificador | `'f' es una función, no una variable` |
| S16 | Variable llamada como función | la llamada | `'x' es una variable, no una función` |

Para S13, un `return` cuenta si está directo en el cuerpo o en un bloque, o si es un `if` con `else` en el que las dos
ramas regresan. Un `while` nunca cuenta, porque su condición puede ser falsa desde el inicio.

## 5. Código intermedio de tres direcciones (Aldo)

Definido en `src/ir/instrucciones.py`: `Instruccion(op, destino, arg1, arg2, etiqueta, params)`. Un operando es un
`str` (variable o temporal) o una constante `int`/`bool`. Temporales: `@t1`, `@t2`, … Etiquetas: `@L1`, `@L2`, …

**Nombres internos:** los temporales y las etiquetas que crea el compilador, incluida `@main`, empiezan con `@`. Ese
carácter no puede aparecer en un identificador del lenguaje, así que nunca chocan con una variable o una función del
programa, aunque se llame `t1`, `L1` o `main`. Las variables y funciones del programa conservan su nombre (o su
`nombre_unico`) sin `@`.

| `op` | Forma en texto | Significado |
|---|---|---|
| `add sub mul div mod` | `@t1 = a + b` | aritmética entera |
| `eq ne lt le gt ge` | `@t1 = a < b` | comparación, resultado `bool` |
| `and or` | `@t1 = a && b` | lógica |
| `neg not` | `@t1 = -a`, `@t1 = !a` | unarios |
| `copy` | `x = @t1` | copia |
| `label` | `@L1:` | marca |
| `goto` | `goto @L1` | salto incondicional |
| `if_false` | `if_false @t1 goto @L2` | salta si es falso |
| `param` | `param @t1` | argumento, en orden de izquierda a derecha |
| `call` | `@t2 = call f, 2` | llama a `f` con los últimos 2 `param`; sin destino si es procedimiento |
| `return` | `return @t1` / `return` | |
| `print` | `print @t1` | |
| `func` / `endfunc` | `func suma(a, b)` … `endfunc suma` | límites de una función |

**Orden del programa:** primero todas las funciones (cada una entre `func` y `endfunc`), luego la etiqueta `@main:` y
las sentencias globales, y al final un `return` sin valor.

**Declaración sin valor inicial:** `int x;` se traduce como `x = 0` y `bool b;` como `b = false` (el valor inicial de
la especificación del lenguaje, sección 2), según el `tipo_dato` de `DeclVar`. Así toda variable tiene valor desde
que se ejecuta su declaración.

Traducción esperada (ejemplo):

```
while (i < n) { i = i + 1; }        @L1:
                                         @t1 = i < n
                                         if_false @t1 goto @L2
                                         @t2 = i + 1
                                         i = @t2
                                         goto @L1
                                    @L2:
```

`listado(instrucciones)` imprime la lista en este formato (artefacto obligatorio, antes y después de optimizar).

## 6. Máquina de pila (Zareth)

El código objetivo es una lista de líneas de texto, una instrucción por línea. La máquina tiene una **pila de
operandos**, una **pila de marcos** (cada llamada crea un marco con sus variables locales) y las variables globales.

| Instrucción | Efecto en la pila |
|---|---|
| `PUSH c` | apila la constante `c` (`5`, `true`, `false`) |
| `LOAD x` | apila el valor de la variable `x` (local si existe en el marco actual, si no global); si no existe en ninguno, es error de ejecución |
| `STORE x` | desapila y guarda en `x` |
| `ADD SUB MUL DIV MOD` | desapila `b`, desapila `a`, apila `a op b` |
| `EQ NE LT LE GT GE` | igual, resultado `true`/`false` |
| `AND OR` | igual, con booleanos |
| `NEG NOT` | desapila `a`, apila `-a` o `!a` |
| `LABEL L` | marca, no hace nada al ejecutarse |
| `JMP L` | salta a `L` |
| `JZ L` | desapila; si es `false`, salta a `L` |
| `CALL f n` | crea un marco, desapila `n` argumentos y los asigna a los parámetros de `f` en orden, salta a `f` |
| `RET` | regresa al llamador; si la pila del marco tiene un valor, ese es el resultado y queda en la pila del llamador |
| `FUNC f p1 p2 ...` | inicio de la función `f` y nombres de sus parámetros |
| `PRINT` | desapila e imprime (`true`/`false` para booleanos) |
| `HALT` | termina |

La ejecución empieza en `LABEL @main`. Errores en tiempo de ejecución (fase `"ejecución"`): división o módulo entre
cero, desbordamiento de la pila de llamadas (más de 1000 marcos) y `LOAD` de una variable que todavía no tiene valor
(`la variable 'g' se usó antes de tener valor`). Este último pasa cuando una función lee una variable global cuya
declaración aún no se ejecuta: en `int a = f(); int g = 5;`, con `f` regresando `g`, el semántico acepta el programa
porque `g` está declarada antes de `f` en el texto, pero al llamar a `f` todavía no tiene valor. La línea y columna de estos errores son las de la
instrucción del programa fuente si se conocen; si no, `0`.

## 7. Comando único

```
python -m src.main <archivo.src> [--tokens] [--ast] [--simbolos] [--ir] [--ir-opt] [--objetivo] [--todo]
```

Sin opciones, compila y ejecuta. Cada opción imprime el artefacto de su fase antes de seguir. Código de salida: `0` si
todo salió bien, `1` si hubo errores del programa, `2` si no se pudo leer el archivo. Hoy existen `--tokens` y
`--ast`; las demás las agrega Zareth conforme se integran las fases.
