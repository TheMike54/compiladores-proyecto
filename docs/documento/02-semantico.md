# Tabla de símbolos y análisis semántico

Esta sección explica la segunda mitad de la fase semántica del compilador: la tabla de símbolos que guarda lo que existe en el programa, y las reglas que revisan que el programa tenga sentido. Recibe el árbol de sintaxis que produce el parser y devuelve ese mismo árbol con el tipo de cada expresión anotado, la tabla de símbolos y la lista de errores. Los ejemplos de salida se obtuvieron ejecutando `python -m src.main <archivo> --simbolos` y `python -m src.main <archivo>` sobre los programas de `examples/` y sobre los fragmentos que aparecen aquí.

## 1. La tabla de símbolos

La tabla guarda, para cada nombre declarado, lo que el resto del compilador necesita saber: su categoría (variable, parámetro o función), su tipo, la línea donde se declaró y el ámbito al que pertenece. En una función, el tipo es el de retorno, y se guarda también la lista de tipos de sus parámetros para poder revisar las llamadas. Un procedimiento (una función sin tipo de retorno) se marca con `ninguno`.

Los ámbitos son de tres clases: el global, el de cada función (que contiene sus parámetros) y el de cada bloque `{ }`. Cada ámbito es un diccionario que va de nombre a símbolo y sabe cuál es su padre. Así, la tabla es un árbol de ámbitos: el global es la raíz y cada función o bloque es un hijo del ámbito donde aparece.

La tabla ofrece cuatro operaciones. `abrir` crea un ámbito hijo del actual y entra en él. `cerrar` regresa al padre. `declarar` agrega un símbolo al ámbito actual y, si ya había otro con ese nombre en ese mismo ámbito, no lo agrega y regresa el anterior, que es lo que necesita el analizador para reportar una redeclaración. `buscar` empieza en el ámbito actual y sube hasta el global, de modo que un nombre interno oculta a uno externo con el mismo nombre.

Los ámbitos cerrados no se borran. Al cerrar un bloque solo se mueve el puntero del ámbito actual a su padre, y el bloque queda colgado de su padre. Esto permite imprimir la tabla completa al final del análisis, cuando ya se cerraron todos los ámbitos. Se usó un diccionario por ámbito porque la búsqueda es directa y porque una pila de diccionarios es la forma clásica de manejar ámbitos anidados.

Esta es la tabla del programa `examples/completo.src`, impresa por el compilador:

```
== TABLA DE SÍMBOLOS ==
Ámbito global (nivel 0)
  nombre         categoría  tipo     línea  nombre único  parámetros
  fibonacci      funcion    int      4                    (int)
  es_par         funcion    bool     11                   (int)
  mostrar_serie  funcion    ninguno  15                   (int)
  total          variable   int      25     total
  par            variable   bool     26     par
    Ámbito función fibonacci (nivel 1)
      nombre  categoría  tipo  línea  nombre único  parámetros
      n       parametro  int   4      n
        Ámbito bloque (línea 5) (nivel 2)
          (sin símbolos)
    Ámbito función es_par (nivel 1)
      nombre  categoría  tipo  línea  nombre único  parámetros
      x       parametro  int   11     x
    Ámbito función mostrar_serie (nivel 1)
      nombre  categoría  tipo  línea  nombre único  parámetros
      limite  parametro  int   15     limite
      i       variable   int   16     i
        Ámbito bloque (línea 17) (nivel 2)
          (sin símbolos)
    Ámbito bloque (línea 29) (nivel 1)
      (sin símbolos)
    Ámbito bloque (línea 31) (nivel 1)
      (sin símbolos)
    Ámbito bloque (línea 33) (nivel 1)
      (sin símbolos)
    Ámbito bloque (línea 37) (nivel 1)
      nombre  categoría  tipo  línea  nombre único  parámetros
      resta   variable   int   38     resta
```

Se ve que `fibonacci`, `es_par` y `mostrar_serie` están en el global aunque aparezcan antes o después de su uso, que `n` y `x` pertenecen a sus funciones, y que el bloque de la línea 37 contiene `resta`, que deja de existir al cerrarse el bloque.

## 2. Reglas de alcance

**Orden de registro.** Antes de revisar el cuerpo de nada, el analizador registra todas las funciones del programa en el ámbito global. Por eso una función puede llamarse antes de estar declarada en el texto, como en `print(doble(2));` seguido de `func doble(int n): int { ... }`. Las variables globales, en cambio, solo existen desde su declaración en adelante. Usar `print(g);` antes de `int g = 1;` es el error S01, y es una decisión de la especificación: una función solo ve las globales declaradas antes de ella en el texto.

**Parámetros y cuerpo.** El cuerpo de una función comparte ámbito con sus parámetros, como en C. Por eso `func f(int a) { int a = 2; }` es una redeclaración (S02). Un bloque dentro del cuerpo sí puede declarar otra vez el nombre de un parámetro, porque ahí se trata de un ámbito distinto. Si el cuerpo fuera otro ámbito, la variable ocultaría al parámetro sin avisar, y casi siempre eso es un error de quien escribe el programa.

**Valor inicial.** En una declaración, el valor inicial se revisa antes de que la variable exista. En `int x = x + 1;` la `x` de la derecha no es la que se está declarando: si hay una `x` en un ámbito externo, se usa esa; si no, es el error S01.

**Ocultamiento y nombres únicos.** Un bloque puede declarar una variable con el mismo nombre que una externa, y dentro del bloque gana la interna. El código intermedio, sin embargo, usa un solo espacio de nombres por función. Si las dos variables conservaran su nombre, la máquina confundiría una con la otra. Por eso el analizador asigna a cada variable un `nombre_único`: la primera declaración de un nombre conserva el suyo y cada declaración posterior, en cualquier ámbito, recibe `x_1`, `x_2`, … saltando los nombres que ya existen en el programa. Así `int x = 1; { int x = 2; print(x); } print(x);` produce este código intermedio:

```
@main:
    x = 1
    x_1 = 2
    print x_1
    print x
    return
```

El segundo `print` usa `x`, la variable global, porque el bloque ya se cerró. La salida del programa es `2` y después `1`.

## 3. Análisis semántico

El análisis recorre el árbol con un visitante, un método por cada tipo de nodo. Los nodos de sentencia (declaraciones, asignaciones, `if`, `while`, `return`) revisan sus reglas. Los nodos de expresión (enteros, booleanos, identificadores, operadores y llamadas) regresan su tipo, que es `int` o `bool`, y lo guardan en el nodo. Si el tipo no se puede saber, por ejemplo porque la variable no existe, la expresión regresa `None`.

El análisis tiene cuatro pasos. Primero junta todos los nombres que se declaran en el programa, para que los nombres únicos no choquen con ellos. Después registra las funciones en el global. Luego recorre el programa en orden. Al final ordena los errores por línea y columna, porque las funciones se revisan en el momento de su aparición y el reporte debe seguir el orden del archivo.

**Cómo no se encadenan los errores.** Ninguna regla lanza excepciones. Cada error se agrega a una lista y el recorrido continúa, así se reportan todos los errores que haya en el programa. Para evitar mensajes en cadena, una expresión con error queda sin tipo y las reglas que la contienen no reportan nada por ella. Los operadores regresan siempre su tipo de resultado, aunque sus operandos estén mal: `+` da `int` y `<` da `bool`. Por eso en `int x = (nada + 1) * 2;` solo sale el error S01 de `nada`.

**Sin conversiones implícitas.** La especificación no permite convertir `int` a `bool`. Por eso `if (x)` con `x` entera es el error S09, y `1 == true` es el error S08.

**Retorno en todos los caminos.** Una función con tipo de retorno debe regresar un valor en todos sus caminos. La regla se revisa con una función que dice si una lista de sentencias siempre regresa. Un `return` cuenta. Un bloque cuenta si alguna de sus sentencias regresa. Un `if` cuenta solo si tiene `else` y las dos ramas regresan. Un `while` nunca cuenta, porque su condición puede ser falsa desde la primera vez y entonces el cuerpo no se ejecuta.

**Procedimientos.** Una llamada a un procedimiento puede usarse como sentencia, porque no regresa nada, pero no puede usarse como valor (S14). En la sentencia, la llamada queda sin tipo.

### Catálogo de errores S01 a S16

Cada error es un `ErrorSemantico`, una subclase del error de compilación del proyecto con un campo `codigo`. Así el mensaje puede cambiar de redacción sin que cambie el código, y las pruebas comparan códigos. Todos se imprimen como `Error semántico [línea L, columna C]: mensaje`. A continuación está cada código con un programa que lo produce y la salida real del compilador.

**S01. Variable no declarada.** Se reporta en el identificador.

```
print(y);
```
```
Error semántico [línea 1, columna 7]: la variable 'y' no está declarada
```

**S02. Redeclaración en el mismo ámbito.** Aplica a variables, parámetros y funciones. Se reporta en la segunda declaración del archivo y cita la primera.

```
int x;
bool x;
```
```
Error semántico [línea 2, columna 1]: 'x' ya está declarado en este ámbito (línea 1)
```

**S03. Función no declarada.** Se reporta en la llamada.

```
print(triple(2));
```
```
Error semántico [línea 1, columna 7]: la función 'triple' no está declarada
```

**S04. Número de argumentos incorrecto.**

```
func f(int a, bool b) { }
f(1);
```
```
Error semántico [línea 2, columna 1]: 'f' espera 2 argumento(s) y recibió 1
```

**S05. Tipo de argumento incorrecto.** Se reporta en el argumento.

```
func f(int a, bool b) { }
f(1, 2);
```
```
Error semántico [línea 2, columna 6]: el argumento 2 de 'f' debe ser bool y es int
```

**S06. Tipos incompatibles en asignación.** Se reporta en el valor.

```
int x = 1;
x = true;
```
```
Error semántico [línea 2, columna 5]: no se puede asignar un valor bool a 'x', que es int
```

**S07. Tipos incompatibles en declaración.** Se reporta en el valor inicial.

```
bool b = 1;
```
```
Error semántico [línea 1, columna 10]: 'b' es bool y se inicializa con un valor int
```

**S08. Operador con operandos de tipo incorrecto.** Se reporta en el operador. Cubre también `!` con un entero, la comparación encadenada `1 < 2 < 3` y la igualdad entre `int` y `bool`.

```
print(1 + true);
```
```
Error semántico [línea 1, columna 9]: el operador '+' necesita int y int, y recibió int y bool
```

**S09. Condición que no es `bool`.** Aplica a `if` y a `while`. Se reporta en la condición.

```
if (1) { print(1); }
```
```
Error semántico [línea 1, columna 5]: la condición del 'if' debe ser bool y es int
```

**S10. `return` fuera de una función.**

```
return 1;
```
```
Error semántico [línea 1, columna 1]: 'return' fuera de una función
```

**S11. `return` con un valor de tipo incorrecto.** Se reporta en el valor.

```
func f(): bool { return 1; }
```
```
Error semántico [línea 1, columna 25]: 'f' debe regresar bool y regresa int
```

**S12. `return` sin valor en una función con tipo, o con valor en un procedimiento.** Se reporta en el `return`.

```
func f(): int { return; }
```
```
Error semántico [línea 1, columna 17]: 'f' debe regresar un valor int
```

**S13. Función que no regresa en todos los caminos.** Se reporta en la función.

```
func f(int n): int { if (n > 0) { return 1; } }
```
```
Error semántico [línea 1, columna 1]: la función 'f' no regresa un valor en todos los caminos
```

**S14. Procedimiento usado como valor.** Se reporta en la llamada.

```
func p() { }
print(p());
```
```
Error semántico [línea 2, columna 7]: 'p' es un procedimiento: no regresa un valor que se pueda usar
```

**S15. Función usada como variable.** Se reporta en el identificador.

```
func f(): int { return 1; }
print(f);
```
```
Error semántico [línea 2, columna 7]: 'f' es una función, no una variable
```

**S16. Variable llamada como función.** Se reporta en la llamada.

```
int x = 1;
print(x(2));
```
```
Error semántico [línea 2, columna 7]: 'x' es una variable, no una función
```

### Un programa con varios errores

El archivo `examples/error_semantico.src` tiene tres errores de tipos distintos. El análisis los reporta todos, en orden:

```
Error semántico [línea 5, columna 1]: la variable 'contador' no está declarada
Error semántico [línea 6, columna 15]: el operador '+' necesita int y int, y recibió int y bool
Error semántico [línea 7, columna 5]: la condición del 'if' debe ser bool y es int
```

El comando termina con código de salida 1 cuando hay errores, y 0 cuando el programa es correcto.

## 4. Limitaciones

- **Sin cadenas ni flotantes.** El lenguaje solo tiene `int` y `bool`. Cualquier otro tipo no se reconoce.
- **Sin conversiones de tipo.** Por especificación, no hay conversión entre `int` y `bool`. Esto obliga a escribir comparaciones explícitas, pero evita errores silenciosos.
- **Las globales solo existen desde su declaración.** Una función solo ve las variables globales declaradas antes de ella en el texto. Así lo fija la especificación del lenguaje, y a diferencia de las funciones, que sí pueden llamarse antes de su declaración.
- **Un solo ámbito global.** No hay módulos ni archivos múltiples; todo el programa vive en un único archivo.
- **Sin inferencia de tipos.** Cada declaración escribe su tipo. Esto simplifica la tabla y los mensajes de error.
- **Sin optimización de la tabla.** La búsqueda sube por los ámbitos uno a uno. Para programas del tamaño del curso es suficiente.

## 5. Casos de prueba

Las pruebas viven en `tests/semantic/`. Hay pruebas de la tabla (declarar, buscar, redeclarar, ocultar, niveles e impresión) y pruebas del analizador: por cada regla S01 a S16 hay al menos un caso válido y uno inválido, y se comprueba el código y la línea esperados.

| Caso | Válido o inválido | Resultado esperado |
|---|---|---|
| `int x = 1; print(x);` | Válido | Sin errores |
| `print(doble(2));` seguido de `func doble(int n): int { return n * 2; }` | Válido | Sin errores; la función se usa antes de declararse |
| `func f(int a) { { int a = 2; print(a); } }` | Válido | Sin errores; el bloque oculta al parámetro |
| `print(y);` | Inválido | S01 en la línea 1 |
| `int x;` seguido de `bool x;` | Inválido | S02 en la línea 2 |
| `print(triple(2));` | Inválido | S03 |
| `func f(int a, bool b) { }` seguido de `f(1);` | Inválido | S04 |
| `func f(int a, bool b) { }` seguido de `f(1, 2);` | Inválido | S05 en el argumento 2 |
| `int x = 1;` seguido de `x = true;` | Inválido | S06 |
| `bool b = 1;` | Inválido | S07 |
| `print(1 + true);` | Inválido | S08 |
| `if (1) { print(1); }` | Inválido | S09 |
| `return 1;` | Inválido | S10 |
| `func f(): bool { return 1; }` | Inválido | S11 |
| `func f(): int { return; }` | Inválido | S12 |
| `func f(int n): int { if (n > 0) { return 1; } }` | Inválido | S13 |
| `func p() { }` seguido de `print(p());` | Inválido | S14 |
| `func f(): int { return 1; }` seguido de `print(f);` | Inválido | S15 |
| `int x = 1;` seguido de `print(x(2));` | Inválido | S16 |
| `examples/error_semantico.src` | Inválido | Tres errores: líneas 5, 6 y 7 |
| `examples/completo.src` | Válido | Sin errores; todas las expresiones con tipo |

## 6. Uso de IA

Se usó Claude (Anthropic) para revisar la lógica del analizador, proponer la forma de la prueba de cada regla y ayudar a redactar esta sección. Los programas de los ejemplos y las salidas de este documento se obtuvieron ejecutando el compilador, no se escribieron a mano. Cada regla y cada prueba se revisó leyendo el código y ejecutando la suite completa antes de darla por buena.

## 7. Conclusión personal

Lo que más costó fue entender por qué la tabla no puede borrar los ámbitos al cerrarlos. Al principio parecía un desperdicio guardar bloques que ya no se usan, pero al imprimir la tabla completa al final quedó claro que hace falta conservarlos. Otra parte difícil fue el nombre único: la regla de ocultamiento parece sencilla hasta que se ve que el código intermedio usa un solo espacio de nombres, y entonces la variable interna tiene que cambiar de nombre aunque el lenguaje no lo muestre.
