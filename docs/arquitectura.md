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
