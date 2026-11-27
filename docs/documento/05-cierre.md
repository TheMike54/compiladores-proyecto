# Pruebas, conclusiones y anexos

## 1. Estrategia de pruebas

Cada fase tiene sus propias pruebas automatizadas, escritas con `unittest` de la biblioteca estándar, y además hay pruebas de extremo a extremo que corren el comando completo. Las pruebas de una fase la llaman directamente con una entrada pequeña y revisan su salida: los tokens que produce el lexer, la forma del AST, el código del error semántico, las instrucciones del código intermedio o el valor que deja la máquina en la pila. Así, cuando algo falla, la prueba señala la fase responsable y no solo que el programa imprimió otra cosa.

Cada fase prueba casos válidos y casos inválidos. En las fases de análisis, los casos inválidos comprueban el mensaje, la línea y la columna, y que un archivo con varios errores los reporte todos. El optimizador se prueba de dos maneras: con casos pequeños para cada regla y ejecutando programas completos antes y después de optimizar con un intérprete de código intermedio independiente de la máquina de pila (`tests/ir/interprete.py`), para comprobar que la salida no cambia. La integración continua de GitHub corre toda la suite en cada pull request, y ningún cambio entró a la rama principal sin pasarla.

Los artefactos de `examples/salidas/` (tokens, AST, tabla de símbolos, código intermedio antes y después de optimizar, código objetivo y salida de los tres programas válidos, y los mensajes de los tres programas con errores) también están bajo prueba: `tests/end_to_end/test_salidas.py` los vuelve a generar con el compilador y falla si alguno ya no coincide. Así los archivos entregados corresponden siempre a la versión que se demuestra.

Para correr todo desde un clon limpio:

```powershell
git clone https://github.com/TheMike54/compiladores-proyecto.git
cd compiladores-proyecto
python -m unittest discover -s tests -t . -v
python -m src.main examples/completo.src --todo
```

## 2. Matriz de casos y resultados

### 2.1 Resumen por fase

| Fase | Carpeta | Pruebas | Válidos que se prueban | Inválidos que se prueban | Resultado |
|---|---|---|---|---|---|
| Léxico | `tests/lexical/` | 14 | palabras reservadas, literales, operadores dobles, comentarios, posiciones | carácter no válido, `&` solo, cero inicial, número pegado a letras, comentario sin cerrar, entero fuera de rango, varios errores | 14 de 14 |
| Sintáctico | `tests/syntax/` | 20 | precedencia, asociatividad, paréntesis, unarios, llamadas, sentencias, funciones, posiciones, ejemplos | falta `;`, bloque sin cerrar, función dentro de bloque, sentencia inválida, varios errores, `}` suelta | 20 de 20 |
| Semántico | `tests/semantic/` | 73 | tabla de símbolos, alcance, ocultamiento, llamada antes de declarar | S01 a S16, cada uno con su código y línea | 73 de 73 |
| Código intermedio y optimizador | `tests/ir/` | 63 | traducción de cada construcción, cada regla del optimizador, programas antes y después de optimizar | división entre cero y desbordamiento sin plegar | 63 de 63 |
| Extremo a extremo y máquina | `tests/end_to_end/` | 14 | comando sobre los ejemplos, código objetivo, máquina, artefactos versionados | errores de compilación, cinco errores de ejecución, archivo inexistente | 14 de 14 |
| **Total** | | **184** | | | **184 de 184** |

Resultado de la última corrida, sobre la versión entregada: `Ran 184 tests` y `OK`.

Las tablas de casos del análisis semántico, del código intermedio y del backend están en la sección «Casos de prueba» de cada una de esas partes. Las del front-end y las de los programas completos son las siguientes.

### 2.2 Análisis léxico

| Caso | Válido o inválido | Resultado esperado |
|---|---|---|
| `int bool if else while print func return` y un identificador | Válido | Cada palabra reservada con su tipo; el resto como `ID` |
| `integer iff` | Válido | Dos identificadores, no palabra reservada más resto |
| `<= >= == != && \|\|` | Válido | Un token por operador, por máxima coincidencia |
| Comentarios de línea y de bloque entre tokens | Válido | No producen tokens |
| `a` en la línea 2, columna 3 | Válido | El token guarda la línea y la columna de su primer carácter |
| `int a = 3 @ 4;` | Inválido | `carácter no válido '@'` en la línea y columna del `@` |
| `true & false` | Inválido | `se esperaba '&&' y se encontró '&' solo` |
| `007` | Inválido | `entero con cero inicial` |
| `12abc` | Inválido | Un solo error: `identificador no puede empezar con dígito` |
| `/* sin cerrar` | Inválido | `comentario de bloque sin cerrar` |
| `2147483648` | Inválido | `entero fuera de rango` |
| Tres errores en un archivo | Inválido | Se reportan los tres, en orden |

### 2.3 Análisis sintáctico

| Caso | Válido o inválido | Resultado esperado |
|---|---|---|
| `2 + 3 * 4` | Válido | La multiplicación queda debajo de la suma |
| `10 - 3 - 4` | Válido | Se agrupa como `(10 - 3) - 4` |
| `(2 + 3) * 4` | Válido | Los paréntesis cambian el árbol y no dejan nodo |
| `a + 1 < b \|\| c == d && e` | Válido | `(a + 1 < b) \|\| ((c == d) && e)`, según la tabla de operadores |
| `-a * !b` y `--a` | Válido | El unario se aplica antes que el producto; `--a` es `-(-a)` |
| `if / else if / else` | Válido | El segundo `if` queda en el `sino` del primero |
| Función con parámetros y retorno | Válido | Nodo `Funcion` con sus `Parametro` y su `Bloque` |
| Procedimiento llamado como sentencia | Válido | `SentenciaExpr` con la `Llamada` |
| Ejemplos de `examples/` | Válido | Sin errores |
| `int a = 3` sin `;` | Inválido | `se esperaba ';'` en el token siguiente |
| Bloque sin `}` | Inválido | `se esperaba '}' para cerrar el bloque abierto en la línea N` |
| `func` dentro de un bloque | Inválido | `las funciones solo se declaran fuera de cualquier bloque` |
| `a;` | Inválido | `se esperaba '=' o '(' después de 'a'` |
| Tres errores en un archivo | Inválido | Se reportan los tres y el análisis sigue |
| `} } print(1);` | Inválido | Dos errores, uno por llave, y el parser avanza sin ciclo infinito |

### 2.4 Programas completos

| Programa | Válido o inválido | Resultado esperado | Resultado obtenido |
|---|---|---|---|
| `examples/factorial.src` | Válido | Imprime `120` | `120` |
| `examples/completo.src` | Válido | Fibonacci de 0 a 10, luego `55`, `true` y `3` | `0 1 1 2 3 5 8 13 21 34 55`, `55`, `true`, `3` |
| `examples/optimizacion.src` | Válido | Imprime `20` y `17`; el IR baja de 27 a 23 instrucciones | `20`, `17`; 27 → 23 |
| `examples/error_lexico.src` | Inválido | Tres errores léxicos (líneas 2, 3 y 4) | Los tres, código de salida 1 |
| `examples/error_sintactico.src` | Inválido | Tres errores sintácticos (líneas 3, 4 y 7) | Los tres, código de salida 1 |
| `examples/error_semantico.src` | Inválido | Tres errores semánticos (líneas 5, 6 y 7) | Los tres, código de salida 1 |
| `int cero = 0;` y, en la línea 2, `print(7 / cero);` | Inválido (ejecución) | `Error de ejecución [línea 2, …]: división entre cero` | Igual, código de salida 1 |
| Recursión sin caso base | Inválido (ejecución) | `desbordamiento de la pila de llamadas` | Igual, código de salida 1 |
| `print(2147483647 + 1);` | Inválido (ejecución) | `el resultado no cabe en un entero de 32 bits` | Igual, con y sin optimizar |

En los tres programas válidos, el código intermedio sin optimizar y el optimizado producen la misma salida.

## 3. Limitaciones conocidas

Cada sección explica las limitaciones de su fase. Las más importantes del compilador en conjunto son:

- **Lenguaje mínimo.** Solo `int` y `bool`, sin cadenas, arreglos ni lectura de datos.
- **Sin cortocircuito.** `&&` y `||` evalúan sus dos operandos. Solo se nota cuando un operando llama a una función que imprime.
- **Optimización solo local.** Lo que el optimizador sabe se olvida al llegar a una etiqueta, un salto o una llamada, así que no mejora el interior de los ciclos.
- **Máquina simulada.** El código objetivo es para la máquina de pila del proyecto y no para un procesador real.
- **Ubicación de errores de ejecución solo desde el comando.** El archivo `.pila` no guarda posiciones del fuente; ejecutado por separado, un error se muestra en la línea 0.

## 4. Trabajo futuro

- Agregar cadenas y lectura de datos, que exigen un tipo nuevo en todas las fases y nuevas instrucciones en la máquina.
- Evaluar `&&` y `||` en cortocircuito, traduciéndolos con saltos en el código intermedio.
- Extender el optimizador con un análisis de flujo de datos entre bloques básicos, para propagar constantes dentro de los ciclos y eliminar código muerto.
- Guardar en el archivo `.pila` la posición del fuente de cada instrucción, para que la máquina reporte la línea también cuando se ejecuta sola.
- Generar código para una arquitectura real (por ejemplo, ensamblador x86-64 o RISC-V) a partir del mismo código intermedio, con asignación de registros.

## 5. Conclusiones

El proyecto mostró en la práctica algo que en clase parecía teórico: cada fase de un compilador resuelve un problema distinto, y lo que la hace manejable es que la interfaz entre una y otra esté bien definida. El contrato que escribimos antes de programar (los nodos del AST, la tabla de símbolos, el formato del código intermedio y el repertorio de la máquina) fue lo que permitió repartir el trabajo entre cuatro personas e integrarlo después. Cuando algo no encajaba, como los nombres internos del código intermedio que podían chocar con variables del programa, el arreglo se hizo primero en el contrato y después en el código.

Cada parte dejó su propia lección. En el front-end, la gramática que se escribe primero no es la que se puede programar, y la recuperación de errores depende de elegir bien dónde sincronizar. En el análisis semántico, la tabla de símbolos no puede borrar los ámbitos que cierra si al final se quiere mostrar completa, y el ocultamiento de nombres obliga a renombrar variables que el lenguaje no deja ver. En el código intermedio, un `while` deja de ser una sentencia y se vuelve dos etiquetas y dos saltos, y el orden de los `param` decide si una llamada anidada se puede leer. En el backend, el orden en que se apilan los operandos es lo que conserva el sentido de una resta o una división.

También aprendimos que un optimizador tiene que justificar que no cambia el programa, no solo que lo hace más corto. Por eso el nuestro olvida lo que sabe cada vez que duda, no pliega una división entre cero y se comprueba ejecutando el programa antes y después de optimizar. Y las pruebas por fase, junto con la integración continua, hicieron posible cambiar una parte sin miedo a romper otra: cuando una corrección tocó el código intermedio y la máquina a la vez, las 184 pruebas dijeron enseguida si algo se había roto.

## 6. Referencias y atribuciones

1. A. V. Aho, M. S. Lam, R. Sethi y J. D. Ullman, *Compiladores: principios, técnicas y herramientas*, 2.ª ed. México: Pearson Educación, 2008.
2. J. Ruiz Catalán, *Compiladores: teoría e implementación*. Madrid: RC Libros, 2010.
3. Python Software Foundation, *The Python Standard Library*, versión 3.12. Disponible en https://docs.python.org/3.12/library/.

**Atribuciones.** El compilador usa solo la biblioteca estándar de Python. Se usaron asistentes de IA, declarados en la sección «Uso de IA» de cada parte: Claude Code (Anthropic) en el front-end, el análisis semántico, el código intermedio, el optimizador y la documentación, y Codex (OpenAI) en el generador de código objetivo, la máquina de pila y el comando único. Cada integrante revisó, probó y puede explicar la parte que entregó.

## Anexo A. Gramática completa

`{ X }` es cero o más veces, `[ X ]` es opcional y los terminales van entre comillas.

```
programa       → { elemento } EOF
elemento       → funcion | sentencia

funcion        → "func" ID "(" [ parametros ] ")" [ ":" tipo ] bloque
parametros     → parametro { "," parametro }
parametro      → tipo ID
tipo           → "int" | "bool"

sentencia      → declaracion | asignacion | llamada_sent | si
               | mientras | imprimir | retorno | bloque
bloque         → "{" { sentencia } "}"
declaracion    → tipo ID [ "=" expresion ] ";"
asignacion     → ID "=" expresion ";"
llamada_sent   → llamada ";"
si             → "if" "(" expresion ")" bloque [ "else" ( si | bloque ) ]
mientras       → "while" "(" expresion ")" bloque
imprimir       → "print" "(" expresion ")" ";"
retorno        → "return" [ expresion ] ";"

expresion      → o
o              → y { "||" y }
y              → igualdad { "&&" igualdad }
igualdad       → relacional { ( "==" | "!=" ) relacional }
relacional     → suma { ( "<" | "<=" | ">" | ">=" ) suma }
suma           → producto { ( "+" | "-" ) producto }
producto       → unaria { ( "*" | "/" | "%" ) unaria }
unaria         → ( "-" | "!" ) unaria | primaria
primaria       → ENTERO | BOOLEANO | ID | llamada | "(" expresion ")"
llamada        → ID "(" [ argumentos ] ")"
argumentos     → expresion { "," expresion }
```

## Anexo B. Instrucciones del código intermedio

| Operación | Forma en texto | Significado |
|---|---|---|
| `add sub mul div mod` | `@t1 = a + b` | aritmética entera |
| `eq ne lt le gt ge` | `@t1 = a < b` | comparación, resultado `bool` |
| `and or` | `@t1 = a && b` | lógica |
| `neg not` | `@t1 = -a`, `@t1 = !a` | unarios |
| `copy` | `x = @t1` | copia |
| `label` | `@L1:` | marca |
| `goto` | `goto @L1` | salto incondicional |
| `if_false` | `if_false @t1 goto @L2` | salta si es falso |
| `param` | `param @t1` | argumento, de izquierda a derecha |
| `call` | `@t2 = call f, 2` | llama a `f` con los últimos 2 `param`; sin destino si es procedimiento |
| `return` | `return @t1` / `return` | regresa, con o sin valor |
| `print` | `print @t1` | imprime |
| `func` / `endfunc` | `func suma(a, b)` … `endfunc suma` | límites de una función |

## Anexo C. Instrucciones de la máquina de pila

| Instrucción | Efecto |
|---|---|
| `PUSH c` | apila la constante `c` (`5`, `true`, `false`) |
| `LOAD x` | apila el valor de `x` (local si existe en el marco actual, si no global) |
| `STORE x` | desapila y guarda en `x` |
| `ADD SUB MUL DIV MOD` | desapila `b`, desapila `a`, apila `a op b` |
| `EQ NE LT LE GT GE` | igual, resultado `true` o `false` |
| `AND OR` | igual, con booleanos |
| `NEG NOT` | desapila `a`, apila `-a` o `!a` |
| `LABEL L` | marca, no hace nada al ejecutarse |
| `JMP L` | salta a `L` |
| `JZ L` | desapila; si es `false`, salta a `L` |
| `FUNC f p1 p2 …` | inicio de la función `f` y nombres de sus parámetros |
| `CALL f n` | crea un marco, pasa los últimos `n` valores a los parámetros de `f`, salta a `f` |
| `RET` | regresa al llamador con el valor de la cima, si lo hay |
| `PRINT` | desapila e imprime |
| `HALT` | termina |

## Anexo D. Evidencia: artefactos del factorial

Estos son los artefactos de `examples/factorial.src`, guardados en `examples/salidas/factorial/`. El programa:

```
// Factorial iterativo de 5: imprime 120
int n = 5;
int resultado = 1;
while (n > 1) {
    resultado = resultado * n;
    n = n - 1;
}
print(resultado);
```

Tabla de símbolos (`simbolos.txt`):

```
Ámbito global (nivel 0)
  nombre     categoría  tipo  línea  nombre único  parámetros
  n          variable   int   2      n
  resultado  variable   int   3      resultado
    Ámbito bloque (línea 4) (nivel 1)
      (sin símbolos)
```

Código intermedio (`ir.txt`). El optimizado (`ir-opt.txt`) es idéntico: no hay operaciones entre constantes ni copias que propagar dentro de un mismo bloque, y el ejemplo que sí cambia es `optimizacion.src`, en la parte de optimización.

```
@main:
    n = 5
    resultado = 1
@L1:
    @t1 = n > 1
    if_false @t1 goto @L2
    @t2 = resultado * n
    resultado = @t2
    @t3 = n - 1
    n = @t3
    goto @L1
@L2:
    print resultado
    return
```

Código objetivo (`objetivo.pila`):

```
LABEL @main
PUSH 5
STORE n
PUSH 1
STORE resultado
LABEL @L1
LOAD n
PUSH 1
GT
STORE @t1
LOAD @t1
JZ @L2
LOAD resultado
LOAD n
MUL
STORE @t2
LOAD @t2
STORE resultado
LOAD n
PUSH 1
SUB
STORE @t3
LOAD @t3
STORE n
JMP @L1
LABEL @L2
LOAD resultado
PRINT
HALT
```

Salida (`salida.txt`): `120`.
