# Especificación del lenguaje MiniLang

MiniLang es un lenguaje imperativo pequeño con tipos estáticos, pensado para mostrar todas las fases de un
compilador. Los programas se guardan con extensión `.src`.

## 1. Léxico

| Categoría | Definición | Ejemplos |
|---|---|---|
| Identificador | `[A-Za-z_][A-Za-z0-9_]*`, que no sea palabra reservada | `x`, `_total`, `valor2` |
| Entero | `0 \| [1-9][0-9]*`, de 0 a 2 147 483 647 | `0`, `42` |
| Booleano | `true \| false` | `true` |
| Palabras reservadas | `int bool if else while print func return` | |
| Operadores | `+ - * / % == != < <= > >= && \|\| ! =` | |
| Delimitadores | `( ) { } ; , :` | |
| Comentarios | `// hasta el fin de línea` y `/* de bloque */` (no se anidan) | |
| Espacios | espacio, tabulador, retorno y salto de línea | |

- Se usa **máxima coincidencia**: `<=` es un solo token y `integer` es un identificador, no `int` + `eger`.
- Los enteros negativos se escriben con el operador unario: `-5`.
- No hay cadenas de texto.

## 2. Tipos

| Tipo | Valores | Valor inicial si se declara sin asignar |
|---|---|---|
| `int` | enteros con signo de 32 bits | `0` |
| `bool` | `true`, `false` | `false` |

No hay conversiones implícitas entre `int` y `bool`.

## 3. Operadores

De **menor a mayor** precedencia:

| Nivel | Operadores | Asociatividad | Operandos → resultado |
|---|---|---|---|
| 1 | `\|\|` | izquierda | `bool, bool → bool` |
| 2 | `&&` | izquierda | `bool, bool → bool` |
| 3 | `==` `!=` | izquierda | dos del mismo tipo → `bool` |
| 4 | `<` `<=` `>` `>=` | izquierda | `int, int → bool` |
| 5 | `+` `-` | izquierda | `int, int → int` |
| 6 | `*` `/` `%` | izquierda | `int, int → int` |
| 7 | `-` `!` (unarios) | derecha | `-`: `int → int`; `!`: `bool → bool` |

- `/` es división entera truncada hacia cero y `%` el residuo con el signo del dividendo (como en C):
  `-7 / 2 = -3`, `-7 % 2 = -1`. Dividir entre cero es un error en tiempo de ejecución.
- `&&` y `||` evalúan sus dos operandos (no hay cortocircuito). Como las expresiones del lenguaje no tienen
  efectos laterales salvo las llamadas, esto solo se nota si un operando llama a una función que imprime.
- `a < b < c` es sintácticamente válido, pero el semántico lo rechaza: `(a < b)` es `bool` y no se compara con `<`.

## 4. Sentencias

```
int x;                    // declaración, x vale 0
bool listo = true;        // declaración con valor inicial
x = x + 1;                // asignación
{ int y = 2; }            // bloque: abre un ámbito nuevo
if (x > 0) { ... }        // condicional
if (x > 0) { ... } else { ... }
if (x > 0) { ... } else if (x < 0) { ... } else { ... }
while (x < 10) { ... }    // ciclo
print(x);                 // imprime un int o un bool y un salto de línea
saludar(3);               // llamada a procedimiento como sentencia
return x;                 // dentro de una función
```

- El cuerpo de `if`, `else` y `while` siempre lleva llaves.
- La condición de `if` y `while` debe ser `bool`.

## 5. Funciones

```
func suma(int a, int b): int {   // función: regresa int
    return a + b;
}

func saludar(int veces) {        // procedimiento: no regresa valor
    print(veces);
}
```

- Se declaran solo en el nivel superior, no dentro de bloques ni de otras funciones.
- Los parámetros se pasan por valor. Se permite la recursión.
- Una función con tipo de retorno debe terminar con `return <expresión>;` en todos los caminos; un procedimiento
  usa `return;` o termina al llegar a su `}`.
- Una función se puede llamar antes de su declaración en el texto (el semántico registra todas primero).

## 6. Estructura de un programa

Un programa es una secuencia de declaraciones de función y de sentencias. Las sentencias del nivel superior forman
el programa principal y se ejecutan en orden; sus variables son globales.

## 7. Ámbitos

- Global: funciones y variables del nivel superior.
- Cada función abre un ámbito con sus parámetros; cada bloque `{ }` abre uno nuevo.
- Un nombre se busca del ámbito más interno al global. Declarar dos veces el mismo nombre en el mismo ámbito es
  error; en un ámbito interno puede ocultar a uno externo.
- Una variable se usa solo después de su declaración.

## 8. Errores

Cada error indica fase, línea, columna y mensaje:

```
Error léxico [línea 2, columna 11]: carácter no válido '@'
Error sintáctico [línea 3, columna 1]: se esperaba ';' y se encontró 'int'
```

Cada fase reporta todos los errores que encuentra; si una fase tiene errores, las siguientes no se ejecutan.

## 9. Ejemplo

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
