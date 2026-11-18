# Gramática de MiniLang

## 1. Gramática en EBNF (la que implementa el parser)

`{ X }` = cero o más veces, `[ X ]` = opcional, terminales entre comillas.

```
programa       → { elemento } EOF
elemento       → funcion | sentencia

funcion        → "func" ID "(" [ parametros ] ")" [ ":" tipo ] bloque
parametros     → parametro { "," parametro }
parametro      → tipo ID
tipo           → "int" | "bool"

sentencia      → declaracion
               | asignacion
               | llamada_sent
               | si
               | mientras
               | imprimir
               | retorno
               | bloque
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

## 2. De dónde sale: gramática original y transformaciones

La gramática natural de expresiones es ambigua y recursiva por la izquierda, por ejemplo:

```
E → E "+" E | E "*" E | "(" E ")" | ID | ENTERO
```

Transformaciones aplicadas:

1. **Quitar la ambigüedad con niveles de precedencia.** Un no terminal por nivel, del operador más débil (`||`) al
   más fuerte (unarios), como en la tabla de la especificación. Así `1 + 2 * 3` solo tiene un árbol.
2. **Eliminar la recursión izquierda.** Cada nivel quedaría `suma → suma "+" producto | producto`, que un parser
   descendente no puede usar (entraría en un ciclo infinito). Se transforma en
   `suma → producto suma'` y `suma' → "+" producto suma' | ε`.
3. **Escribir `suma'` como repetición.** `suma → producto { "+" producto }`. En el código es un `while` que va
   construyendo el árbol hacia la izquierda, de modo que `10 - 3 - 4` se agrupa como `(10 - 3) - 4`: la recursión por
   la derecha de la gramática transformada no cambia la asociatividad.
4. **Factorizar por la izquierda** las producciones que empiezan igual:
   - `asignacion`, `llamada_sent` empiezan con `ID`: se decide viendo el token siguiente (`=` o `(`).
   - En `primaria`, `ID` y `llamada` también: se decide igual.
   - `si` con y sin `else`: el `else` es opcional al final, y se asocia al `if` más cercano (no hay ambigüedad
     porque los cuerpos llevan llaves obligatorias).

Con eso la gramática es **LL(2)**: toda decisión se toma con el token actual y, solo para `ID`, con el siguiente.

## 3. Método de parsing

Descendente recursivo escrito a mano (`src/parser/parser.py`): un método por no terminal. No se usaron
generadores de parsers.

## 4. Recuperación de errores (modo pánico)

Cuando un token no es el esperado:

1. Se registra el error con línea, columna, lo esperado y lo encontrado.
2. Se abandona la sentencia que se estaba analizando.
3. Se descartan tokens hasta un punto de sincronización: justo después de un `;`, o antes de `}`, `{` o de una palabra
   que inicia sentencia (`int`, `bool`, `if`, `while`, `print`, `return`, `func`).
4. Se sigue analizando desde ahí.

Si el error ocurre en el primer token de la sentencia, ese token se descarta para garantizar avance.
