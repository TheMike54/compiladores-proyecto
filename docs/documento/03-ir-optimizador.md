# Código intermedio y optimización

Esta sección explica la fase intermedia del compilador. Recibe el árbol de sintaxis que ya revisó el análisis semántico, con el tipo de cada expresión anotado, y lo convierte en una lista de instrucciones muy simples, llamada código intermedio de tres direcciones. Después, un optimizador mejora esa lista sin cambiar lo que el programa hace. La salida de esta fase es la entrada de la generación de código para la máquina de pila. Los listados de este documento se obtuvieron ejecutando `python -m src.main <archivo> --ir` (código intermedio), `--ir-opt` (código optimizado) o `--todo` (todas las etapas) sobre los programas de `examples/` y sobre los fragmentos que aparecen aquí.

## 1. Representación intermedia

### 1.1 Qué es y para qué sirve

Después del análisis semántico, el programa sigue siendo un árbol. Antes de generar código para la máquina de pila se traduce a una lista lineal de instrucciones donde cada una hace a lo más una operación y tiene a lo más tres direcciones: un destino y dos operandos. Por ejemplo, `x = (a + b) * 2` se convierte en tres instrucciones:

```
@t1 = a + b
@t2 = @t1 * 2
x = @t2
```

Esta forma intermedia se eligió por tres razones. La primera es que separa el lenguaje de la máquina: el generador de código de pila no necesita conocer el árbol, solo leer una lista, y el generador de código intermedio no necesita saber cómo es la máquina. La segunda es que hace explícito el flujo de control: los `if` y los `while` desaparecen y en su lugar quedan etiquetas y saltos, que es lo que una máquina sabe ejecutar. La tercera es que es el lugar natural para optimizar, porque es más fácil razonar sobre una lista de instrucciones simples que sobre un árbol. La referencia que se siguió es el capítulo 6 de Aho, Lam, Sethi y Ullman (código intermedio).

### 1.2 Formato de las instrucciones

Cada instrucción es un objeto `Instruccion(op, destino, arg1, arg2, etiqueta, params)`, definido en `src/ir/instrucciones.py`. El campo `op` dice qué operación es, y los demás se usan según la operación. Un operando es el nombre de una variable o de un temporal, o bien una constante entera o booleana. La siguiente tabla muestra cada operación con su forma en texto:

| `op` | Forma en texto | Significado |
|---|---|---|
| `add sub mul div mod` | `@t1 = a + b` | aritmética entera |
| `eq ne lt le gt ge` | `@t1 = a < b` | comparación, el resultado es `bool` |
| `and or` | `@t1 = a && b` | lógica |
| `neg not` | `@t1 = -a`, `@t1 = !a` | operadores unarios |
| `copy` | `x = @t1` | copia un valor a una variable |
| `label` | `@L1:` | marca un punto al que se puede saltar |
| `goto` | `goto @L1` | salto incondicional |
| `if_false` | `if_false @t1 goto @L2` | salta si el operando es falso |
| `param` | `param @t1` | deja un argumento para la próxima llamada |
| `call` | `@t2 = call f, 2` | llama a `f` con los últimos 2 `param`; sin destino si es un procedimiento |
| `return` | `return @t1` o `return` | regresa al llamador, con valor o sin él |
| `print` | `print @t1` | imprime un valor |
| `func` / `endfunc` | `func suma(a, b)` … `endfunc suma` | inicio y fin de una función |

Las operaciones aritméticas, de comparación y lógicas siempre tienen la misma forma: un destino y dos operandos. Los saltos no necesitan destino, solo la etiqueta a la que van. Se eligió que `if_false` salte cuando la condición es falsa, y no cuando es verdadera, porque así el código del cuerpo del `if` queda inmediatamente después de la condición y solo se salta cuando hay que omitirlo.

### 1.3 Temporales, etiquetas y nombres internos

Para guardar resultados intermedios, el generador crea temporales numerados (`@t1`, `@t2`, …). Para marcar puntos de salto crea etiquetas numeradas (`@L1`, `@L2`, …). Ambos contadores son únicos en todo el programa, así que ningún nombre se repite, ni siquiera entre funciones distintas.

Todos los nombres que crea el compilador empiezan con `@`: los temporales, las etiquetas y también `@main`, que marca el inicio del programa principal. Ese carácter no puede aparecer en un identificador del lenguaje, así que los nombres internos nunca chocan con los del programa. Esto importa porque un programa puede tener una variable llamada `t1`, o `L1`, o una función llamada `main`. Si el compilador usara esos mismos nombres para sus temporales o etiquetas, las dos cosas se confundirían y el programa daría resultados incorrectos. Con el `@` delante, el compilador puede inventar cuantos nombres necesite sin tener que revisar los del programa.

Las variables y funciones del programa conservan su nombre, sin `@`. La única excepción son las variables que comparten nombre en ámbitos distintos: el análisis semántico les asigna un nombre único (`x` y `x_1`, por ejemplo), y el generador usa ese nombre en lugar del original. Así el código intermedio no necesita consultar la tabla de símbolos, y cada variable queda distinta de las demás.

### 1.4 Un ejemplo completo

El siguiente programa define una función, declara variables sin valor inicial, incluye una variable llamada `t1` y llama a la función:

```
func suma(int a, int b): int {
    return a + b;
}
int x;
bool listo;
int t1 = 1;
print(suma(t1, 2));
```

Su código intermedio es:

```
func suma(a, b)
    @t1 = a + b
    return @t1
endfunc suma
@main:
    x = 0
    listo = false
    t1 = 1
    param t1
    param 2
    @t2 = call suma, 2
    print @t2
    return
```

En el listado se ve cada convención. La variable del programa `t1` y el temporal `@t1` de la función conviven sin confundirse. El contador de temporales sigue en `@t2` dentro de `@main` y no vuelve a empezar, porque es único para todo el programa. Las funciones aparecen primero, cada una entre `func` y `endfunc`, y después viene la etiqueta `@main:` con las sentencias globales y, al final, un `return` sin valor.

Las declaraciones sin valor inicial también se traducen: `int x;` queda como `x = 0` y `bool listo;` como `listo = false`, que son los valores iniciales que fija la especificación del lenguaje. Así toda variable tiene valor desde que se ejecuta su declaración, y las fases siguientes no necesitan tratar ese caso aparte. Para llamar a la función, primero se dejan los argumentos con `param`, de izquierda a derecha, y después `call suma, 2` indica cuántos de los últimos `param` le corresponden. El resultado se guarda en `@t2` y de ahí lo toma el `print`.

## 2. Traducción de las construcciones

El generador (`src/ir/generador.py`) recorre el árbol con un visitante, un método por cada tipo de nodo, y construye la lista de instrucciones. Los métodos se dividen en dos grupos. Los de expresión devuelven un operando: una constante devuelve su valor, un identificador devuelve su nombre, y una operación visita primero el operando izquierdo y después el derecho, crea un temporal nuevo, emite la instrucción y devuelve ese temporal. Los de sentencia solo emiten instrucciones y no devuelven nada. Esta división explica la forma de todos los listados: una expresión anidada se aplana de adentro hacia afuera, y el temporal que produce una parte es el operando de la siguiente.

### 2.1 Expresiones y asignación

Cada operación binaria o unaria produce una instrucción con un temporal como destino, y la asignación copia el último temporal a la variable. Con el programa

```
int a = 2;
int b = 3;
int x = (a + b) * 2;
x = x - 1;
bool ok = a < b && !(b == 3);
print(x);
print(ok);
```

el código intermedio es:

```
@main:
    a = 2
    b = 3
    @t1 = a + b
    @t2 = @t1 * 2
    x = @t2
    @t3 = x - 1
    x = @t3
    @t4 = a < b
    @t5 = b == 3
    @t6 = !@t5
    @t7 = @t4 && @t6
    ok = @t7
    print x
    print ok
    return
```

Los paréntesis no generan ninguna instrucción: ya están reflejados en la forma del árbol, y por eso `(a + b) * 2` calcula primero la suma. Una declaración con valor inicial y una asignación se traducen igual, con una copia al final. Una constante que se declara directamente, como `a = 2`, no necesita temporal, porque una constante ya es un operando. La salida de este programa es `9` y `false`.

Los operadores lógicos `&&` y `||` siempre evalúan sus dos operandos, como fija la especificación del lenguaje: no hay evaluación en cortocircuito. En el ejemplo, `@t5` y `@t6` se calculan aunque `a < b` fuera falso y el resultado ya estuviera decidido. Como las expresiones no tienen efectos laterales, salvo las llamadas a función, calcular las dos partes da el mismo resultado que calcular solo una. La diferencia solo se notaría si un operando llamara a una función que imprime, y entonces la impresión ocurriría en ambos casos. Esta decisión simplifica el código intermedio: `&&` y `||` son una instrucción como cualquier otra, sin saltos.

### 2.2 `if` y `if/else`

Un `if` sin `else` necesita una sola etiqueta: si la condición es falsa se salta el cuerpo y se continúa justo después. Con `if (x > 5) { print(1); } print(x);` el código es:

```
@main:
    x = 7
    @t1 = x > 5
    if_false @t1 goto @L1
    print 1
@L1:
    print x
    return
```

Un `if` con `else` necesita dos etiquetas. Al terminar el cuerpo del `entonces` hay que saltar por encima del `sino`, y eso es lo que agrega el `goto`. Un `else if` no necesita una regla propia: en el árbol, el `sino` de un `if` es otro `if`, y se traduce con el mismo método, anidado. Con

```
int x = 7;
if (x > 5) {
    print(1);
} else if (x > 2) {
    print(2);
} else {
    print(3);
}
```

el código es:

```
@main:
    x = 7
    @t1 = x > 5
    if_false @t1 goto @L1
    print 1
    goto @L2
@L1:
    @t2 = x > 2
    if_false @t2 goto @L3
    print 2
    goto @L4
@L3:
    print 3
@L4:
@L2:
    return
```

`@L1` es el inicio del primer `sino`, que es el segundo `if`, y `@L2` es el final de toda la cadena. `@L3` y `@L4` hacen lo mismo para el `if` interior. Las etiquetas `@L4` y `@L2` quedan seguidas porque los dos `if` terminan en el mismo punto. No estorba: una etiqueta no hace nada al ejecutarse, y el programa imprime `1`.

### 2.3 `while`

Un `while` necesita una etiqueta al inicio, para volver a evaluar la condición, y otra al final, para salir cuando es falsa. Con

```
int i = 0;
while (i < 3) {
    print(i);
    i = i + 1;
}
```

el código es:

```
@main:
    i = 0
@L1:
    @t1 = i < 3
    if_false @t1 goto @L2
    print i
    @t2 = i + 1
    i = @t2
    goto @L1
@L2:
    return
```

La condición se calcula después de `@L1`, y no antes, porque tiene que volver a evaluarse en cada vuelta. Si estuviera antes de la etiqueta, el ciclo usaría siempre el valor de la primera vuelta. El `goto @L1` del final cierra el ciclo y `if_false` lo abre por el otro lado. El programa imprime `0`, `1` y `2`.

### 2.4 `print`

`print` evalúa su expresión y emite una sola instrucción con el operando resultante. Si el valor ya es una variable o una constante, no se crea ningún temporal: en los ejemplos anteriores se ve `print x`, `print 1` y `print i`. Si es una expresión, primero se calcula en un temporal, como en `print(doble(r) + 1)` de la sección siguiente. La máquina imprime los booleanos como `true` y `false`.

### 2.5 Funciones, llamadas y `return`

Cada función se traduce entre `func nombre(parámetros)` y `endfunc nombre`, y el cuerpo se traduce como cualquier otra lista de sentencias. Las funciones van antes de `@main`, sin importar en qué parte del texto se hayan escrito. Con

```
func doble(int n): int {
    return n * 2;
}
func saludar(int veces) {
    print(veces);
}
int r = doble(4);
saludar(r);
print(doble(r) + 1);
```

el código es:

```
func doble(n)
    @t1 = n * 2
    return @t1
endfunc doble
func saludar(veces)
    print veces
    return
endfunc saludar
@main:
    param 4
    @t2 = call doble, 1
    r = @t2
    param r
    call saludar, 1
    param r
    @t3 = call doble, 1
    @t4 = @t3 + 1
    print @t4
    return
```

Una llamada se traduce en dos pasos. Primero se evalúan todos los argumentos, de izquierda a derecha, y solo después se emite un `param` por cada uno. Al final se emite `call f, n`, donde `n` es el número de argumentos que le corresponden a la llamada, que son los últimos `n` `param`. Si la función regresa un valor, el `call` tiene un temporal como destino (`@t2 = call doble, 1`). Si es un procedimiento, el `call` no tiene destino (`call saludar, 1`), porque no hay nada que guardar.

El orden importa cuando un argumento es otra llamada. Con `print(suma(1, doble(2)));` el código de `@main` es:

```
@main:
    param 2
    @t3 = call doble, 1
    param 1
    param @t3
    @t4 = call suma, 2
    print @t4
    return
```

La llamada a `doble` se resuelve por completo antes de que empiecen los `param` de `suma`. Así, los `param` de cada llamada quedan juntos, justo antes de su `call`, y los de una llamada anidada no se mezclan con los de la exterior. Esto permite leer el código sin llevar la cuenta de qué `param` estaban pendientes: `call suma, 2` toma los dos `param` que tiene inmediatamente antes. Si cada `param` se emitiera en cuanto se evalúa su argumento, el `param 1` de `suma` quedaría separado de su `call` por toda la llamada a `doble`. La salida de este programa es `5`.

Un `return` con valor evalúa la expresión y emite `return` con ese operando, y un `return` sin valor emite solo `return`. Al final de cada procedimiento, y al final del programa principal, el generador agrega un `return` sin valor. Se ve en `saludar`, que no escribe ningún `return` y termina con uno. Así el procedimiento siempre regresa al llamador al llegar al final de su cuerpo, aunque quien escribió el programa no lo haya puesto. Una función con tipo de retorno no lleva ese `return` extra, como se ve en `doble`: el análisis semántico ya comprobó que todos sus caminos terminan en un `return` con valor. La salida del programa es `8` y `17`.

## 3. Optimización

### 3.1 Qué se optimiza y cómo

El optimizador recibe la lista de instrucciones del código intermedio y devuelve otra lista, más corta o igual, que hace exactamente lo mismo: imprime lo mismo, en el mismo orden, y falla en los mismos casos. Solo cambia cómo lo logra. La entrada no se modifica, se construye una lista nueva. Las referencias que se siguieron son el capítulo 8.5 y la sección 9.1 de Aho, Lam, Sethi y Ullman (optimización local).

Se implementaron tres optimizaciones, repartidas en dos pasadas. La primera recorre la lista una vez y aplica dos: el plegado de constantes y la propagación de copias. La segunda aplica la tercera, la eliminación de temporales muertos, y se repite hasta que ya no cambia nada. El orden importa: la primera pasada es la que deja instrucciones inútiles, y la segunda las limpia.

Son optimizaciones locales: cada una usa solo lo que se sabe dentro de un tramo del programa, y no intenta razonar sobre todos los caminos posibles de ejecución. Se eligió así porque es lo que pide la guía del proyecto y porque es la forma más fácil de justificar que el resultado no cambia.

### 3.2 Bloques básicos

Un bloque básico es un tramo de instrucciones que se ejecuta siempre de principio a fin: no se puede entrar por la mitad ni salir antes. Lo que el optimizador sabe de las variables, por ejemplo que `limite` vale 5, solo es seguro dentro de un bloque, porque ahí no hay otro camino que llegue con un valor distinto. Por eso olvida todo lo aprendido al pasar por alguna de estas instrucciones:

| Instrucción | Por qué se olvida lo aprendido |
|---|---|
| `label` | a una etiqueta pueden llegar saltos desde otros puntos del programa, con otros valores |
| `goto`, `if_false` | después de un salto empieza otro camino |
| `return`, `func`, `endfunc` | terminan o empiezan una función |
| `call` | la función llamada puede cambiar variables globales |

Olvidar de más solo hace que se pierda alguna optimización, nunca cambia el resultado del programa. Por eso el optimizador prefiere olvidar cuando tiene duda.

### 3.3 Las tres optimizaciones

**Plegado de constantes.** Si una instrucción aritmética, de comparación o lógica tiene todos sus operandos constantes, su resultado ya se conoce sin ejecutar el programa, y se reemplaza por una copia de ese valor. Con `int x = 2 + 3 * 4; print(x);`:

```
IR                          IR optimizado
@main:                      @main:
    @t1 = 3 * 4                 x = 14
    @t2 = 2 + @t1               print 14
    x = @t2                     return
    print x
    return
```

`@t1 = 3 * 4` se pliega a `@t1 = 12`. La propagación de copias, que se explica a continuación, sustituye `@t1` en la instrucción siguiente, que queda `@t2 = 2 + 12` y se pliega a `@t2 = 14`, y así hasta `print 14`. Los temporales `@t1` y `@t2` quedan sin uso y los borra la segunda pasada. `x = 14` se conserva porque `x` es una variable del programa y el optimizador nunca las borra.

Una operación entre constantes siempre da el mismo resultado, y por eso calcularla antes no cambia lo que imprime el programa. Hay tres casos en los que el resultado de ejecutar no es simplemente el valor aritmético, y en ellos el plegado tiene cuidado:

- **División o módulo entre cero.** No se pliega. `print(1 / 0);` queda igual después de optimizar, y el programa sigue terminando con el error de ejecución `división entre cero`, que la especificación define como error en tiempo de ejecución. El optimizador no debe inventar un valor para esa operación ni hacer que el error ocurra al compilar.
- **Resultado fuera de 32 bits.** No se pliega. Un `int` es un entero con signo de 32 bits, así que el resultado de `print(2147483647 + 1);` no es representable. Queda igual después de optimizar y la máquina lo reporta al ejecutarse (`el resultado no cabe en un entero de 32 bits`), igual que sin optimizar.
- **División entera.** Se calcula truncando hacia cero, igual que la máquina de pila, y no con `//` de Python, que redondea hacia abajo. `print(-7 / 2); print(-7 % 2);` se pliega a `print -3` y `print -1`, los mismos valores que imprime sin optimizar (con `//` saldría `-4`).

**Propagación de copias.** Después de `b = a`, las dos variables valen lo mismo hasta que una cambie. El optimizador recuerda esa igualdad dentro del bloque y sustituye cada lectura posterior por el valor que se sabe que tiene. Con `int a = 3; int b = a; a = 10; print(b); print(a);`:

```
IR                          IR optimizado
@main:                      @main:
    a = 3                       a = 3
    b = a                       b = 3
    a = 10                      a = 10
    print b                     print 3
    print a                     print 10
    return                      return
```

`b = a` queda como `b = 3` porque se sabe que `a` vale 3, y `print b` como `print 3`. La instrucción `a = 10` cambia `a`, así que el optimizador olvida lo que sabía de ella y `print a` pasa a `print 10`.

La propagación no cambia lo que imprime el programa porque solo usa una igualdad mientras sigue siendo cierta. Una copia deja de valer en cuanto cambia cualquiera de sus dos lados: si cambia `a`, ya no se sabe qué vale `a` ni se sigue pensando que `b` es igual a ella. Si el optimizador se quedara con la idea de que `b` es `a`, el programa de arriba imprimiría `10` en lugar de `3`. Lo mismo ocurre dentro de un `while`: en `while (n < 3) { int x = n; n = n + 1; print(x); }`, la variable `x` debe conservar el valor que `n` tenía al copiarlo, aunque `n` cambie después. Y como se olvida todo al llegar a una etiqueta, un salto o una llamada, nunca se usa una igualdad que otro camino del programa pueda haber roto.

**Eliminación de temporales muertos.** Una instrucción que solo calcula un temporal (`@t1`, `@t2`, …) que ninguna otra instrucción lee no sirve para nada, y se borra. Con `int a = 2 + 3; print(a);`:

```
IR                          IR optimizado
@main:                      @main:
    @t1 = 2 + 3                 a = 5
    a = @t1                     print 5
    print a                     return
    return
```

Primero el plegado deja `@t1 = 5` y la propagación cambia `a = @t1` por `a = 5` y `print a` por `print 5`. Desde ese momento nadie lee `@t1` y la segunda pasada lo borra. Borrar una instrucción puede dejar sin uso a la que calculaba su operando, por eso la pasada se repite hasta que no cambia nada.

Esta optimización no cambia el resultado porque borra solo lo que no se puede notar. Tiene tres límites:

- **Solo temporales.** Las variables del programa nunca se borran, aunque no se vuelvan a leer, porque pueden leerse desde una función o desde otro punto del programa que el optimizador no sigue. Los temporales los crea el compilador y solo las instrucciones del código intermedio los leen. Además, para decidir si un temporal se lee se revisa toda la lista, no solo su bloque: un uso después de una etiqueta también cuenta.
- **Solo instrucciones sin efectos.** Se borran las operaciones aritméticas, de comparación, lógicas, unarias y las copias. Nunca se borra un `print`, un salto, una llamada (aunque no se use su resultado, la función puede imprimir o cambiar variables globales) ni un `return`.
- **Una división puede fallar.** `@t1 = a / b` se conserva aunque nadie lea `@t1`, porque si `b` vale 0 el programa debe terminar con el error de ejecución. Solo se borra una división o un módulo cuando el divisor es una constante distinta de cero, ya que entonces no puede fallar.

### 3.4 Ejemplo antes y después

El archivo `examples/optimizacion.src` junta las tres optimizaciones en un programa con un `while`, un `if/else` y expresiones constantes:

```
int i = 0;
int suma = 0;
int limite = 2 + 3;
while (i < limite) {
    suma = suma + i * 2;
    i = i + 1;
}
if (suma > 10) {
    print(suma);
} else {
    print(0);
}
print(4 * 5 - 6 / 2);
```

El código intermedio sin optimizar tiene 27 instrucciones:

```
@main:
    i = 0
    suma = 0
    @t1 = 2 + 3
    limite = @t1
@L1:
    @t2 = i < limite
    if_false @t2 goto @L2
    @t3 = i * 2
    @t4 = suma + @t3
    suma = @t4
    @t5 = i + 1
    i = @t5
    goto @L1
@L2:
    @t6 = suma > 10
    if_false @t6 goto @L3
    print suma
    goto @L4
@L3:
    print 0
@L4:
    @t7 = 4 * 5
    @t8 = 6 / 2
    @t9 = @t7 - @t8
    print @t9
    return
```

Después de optimizar quedan 23:

```
@main:
    i = 0
    suma = 0
    limite = 5
@L1:
    @t2 = i < limite
    if_false @t2 goto @L2
    @t3 = i * 2
    @t4 = suma + @t3
    suma = @t4
    @t5 = i + 1
    i = @t5
    goto @L1
@L2:
    @t6 = suma > 10
    if_false @t6 goto @L3
    print suma
    goto @L4
@L3:
    print 0
@L4:
    print 17
    return
```

Cambian cuatro instrucciones, las de los temporales `@t1`, `@t7`, `@t8` y `@t9`. `@t1 = 2 + 3` se pliega a `5`, la propagación convierte `limite = @t1` en `limite = 5` y `@t1` queda sin uso. `@t7 = 4 * 5` y `@t8 = 6 / 2` se pliegan a `20` y `3`, la propagación convierte `@t9 = @t7 - @t8` en `@t9 = 20 - 3`, que se pliega a `17`, y `print @t9` pasa a `print 17`. Los tres temporales quedan sin uso y se borran.

El ciclo y la condición del `if` no cambian, y es correcto que así sea. Al llegar a `@L1` el optimizador olvida todo lo aprendido, porque a esa etiqueta se vuelve desde el final del ciclo con `i` y `suma` cambiados. Por eso `i < limite` sigue comparando con la variable `limite` y no con el `5` que se había visto antes del ciclo. Las etiquetas y los saltos quedan exactamente iguales. Los dos listados imprimen lo mismo: `20` y `17`.

### 3.5 Por qué el programa hace lo mismo

Las tres optimizaciones comparten la misma idea: solo se usa un hecho sobre el programa cuando es cierto en todas las ejecuciones posibles que llegan a ese punto, y solo se borra una instrucción cuando nadie puede notar que falta. Cada regla de las secciones anteriores es una forma de cumplirlo:

- **Los hechos son ciertos.** Lo que se aprende sobre una variable vale solo dentro de un bloque básico, se olvida en cuanto la variable cambia, y se olvida todo al llegar a una etiqueta, un salto o una llamada.
- **Calcular antes no cambia el valor.** El plegado usa las mismas reglas de división y el mismo rango de 32 bits que la máquina, y deja sin tocar lo que fallaría al ejecutarse.
- **Lo que se borra no se nota.** Solo se eliminan temporales que nadie lee, y solo mediante instrucciones que no imprimen, no saltan, no llaman y no pueden fallar.

Esto se comprobó de dos maneras. Las pruebas del optimizador revisan cada regla con casos pequeños, incluidos los de cuidado: una variable que cambia después de copiarse, una división entre cero, un desbordamiento y una función que modifica una global. Además, las pruebas de punta a punta ejecutan el código intermedio antes y después de optimizar, con un intérprete independiente de la máquina de pila, y comprueban que la salida es idéntica en `factorial.src`, `completo.src` y `optimizacion.src`.

## 4. Limitaciones

- **La optimización es solo local.** Lo que se aprende se olvida al llegar a una etiqueta, un salto o una llamada, así que nada cruza de un bloque a otro. En `optimizacion.src`, el `limite = 5` de antes del ciclo no se propaga adentro, y `i < limite` sigue leyendo la variable. Razonar entre bloques exige un análisis del flujo de datos de todo el programa. Se dejó fuera porque la guía pide al menos una transformación local con su justificación, y porque una optimización que se puede justificar completa vale más que una más amplia que no se entiende bien.
- **Una condición constante no simplifica el salto.** Con `if (true) { print(1); } else { print(2); }` el código optimizado conserva `if_false true goto @L1` y las dos ramas, aunque la segunda nunca se ejecuta. El programa imprime `1` igual que sin optimizar.
- **No se elimina código inalcanzable ni asignaciones que se pisan.** En `int x = 5; x = 6;` se conservan las dos asignaciones. Borrar una asignación a una variable del programa exigiría saber que nadie la lee después, incluidas las funciones, y esa decisión no se tomó (por eso solo se borran temporales).
- **No hay identidades algebraicas ni reutilización de subexpresiones.** Cuando los valores no se conocen, como dentro de una función, `n * 1` y `n + 0` se calculan tal cual, y `n + n` escrito dos veces se calcula dos veces con dos temporales distintos. Se quedó fuera para limitar el alcance a tres transformaciones sencillas y bien probadas.
- **Las funciones se optimizan por separado.** Una llamada hace que el optimizador olvide lo aprendido, y no se sustituye el cuerpo de una función en el lugar de la llamada. En `h(2)`, el valor `2` no se propaga al cuerpo de `h`.
- **No se pliega lo que fallaría o no cabría en 32 bits.** Una división entre cero o un resultado fuera de rango se dejan para la ejecución, donde la máquina reporta el error. Es una decisión a propósito, no una carencia: plegar esas operaciones cambiaría cuándo y cómo falla el programa.
- **`&&` y `||` evalúan siempre los dos lados.** Así lo fija la especificación del lenguaje. Por eso no generan saltos en el código intermedio, a costa de calcular una parte que a veces sobra.
- **El código intermedio es poco compacto.** Cada operación usa un temporal nuevo y los temporales nunca se reutilizan. En el `else if` quedan dos etiquetas seguidas en el mismo punto. Ninguna de las dos cosas afecta el resultado, y se aceptaron para que el generador sea simple y cada instrucción se pueda entender sola.
- **Se asume un programa correcto.** El generador espera un árbol con todos los tipos anotados. El comando no lo ejecuta si el análisis semántico encontró errores.

## 5. Casos de prueba

Las pruebas viven en `tests/ir/` y son 63. `test_generador.py` comprueba el código intermedio que produce cada construcción, `test_optimizador.py` comprueba cada regla del optimizador con casos pequeños, y `test_criterio.py` compila programas completos y los ejecuta antes y después de optimizar, con un intérprete de código intermedio (`tests/ir/interprete.py`) que no depende de la máquina de pila.

Esta fase no rechaza programas: asume que el análisis semántico ya los aprobó, y por eso casi todos los casos de la tabla son programas válidos. Los casos marcados como límite son programas válidos donde una operación falla al ejecutarse, y la prueba comprueba que el optimizador no oculta ese fallo.

| Caso | Válido o inválido | Resultado esperado |
|---|---|---|
| `int x = (a + b) * 2;` | Válido | `@t1 = a + b`, `@t2 = @t1 * 2`, `x = @t2` |
| `b = !(a < 3) && true;` | Válido | `@t1 = a < 3`, `@t2 = !@t1`, `@t3 = @t2 && true` y `b = @t3`; se calculan los dos lados |
| `x = -y;` | Válido | `@t1 = -y` y `x = @t1` |
| `int x;` y `bool b;` | Válido | `x = 0` y `b = false` |
| Variable llamada `t1` sumada con otra llamada `main` | Válido | `@t1 = t1 + main` y `t1 = @t1`; los nombres del programa no chocan con los internos |
| `int x = 1;` con `nombre_unico` `x_1` | Válido | `x_1 = 1` y `print x_1` |
| `if` sin `else` | Válido | Una sola etiqueta; el salto cae justo después del cuerpo |
| `if` con `else` | Válido | Dos etiquetas y un `goto` que salta el `sino` |
| `else if` | Válido | El segundo `if` queda anidado en la rama `sino` |
| `while (i < 3) { ... }` | Válido | `@L1` al inicio, `if_false` hacia `@L2` y `goto @L1` al final |
| Llamada antes de declarar la función | Válido | Las funciones van antes de `@main` |
| `suma(1, suma(2, 3))` | Válido | Los `param` de la llamada interna quedan antes de los de la externa |
| Procedimiento llamado como sentencia | Válido | `call saludar, 0` sin destino y `return` al final de `saludar` |
| Función con valor llamada como sentencia | Válido | El resultado se descarta, no se guarda en ninguna variable |
| `int a = 2 + 3;` | Válido | `a = 5`, sin temporales |
| `print(-7 / 2); print(-7 % 2);` | Válido | `print -3` y `print -1`, división truncada hacia cero |
| `print(1 / 0);` | Límite | No se pliega; falla igual con y sin optimizar |
| `print(2147483647 + 1);` | Límite | No se pliega, porque el resultado no cabe en 32 bits |
| `int b = a; a = 10; print(b);` | Válido | `print 3`: reasignar `a` invalida la copia |
| `x = n` dentro de un `while` donde `n` cambia | Válido | Imprime `0`, `1`, `2`; `x` conserva el valor viejo |
| Una etiqueta, un salto o una llamada entre dos usos | Válido | Se olvida lo aprendido y no se sustituye |
| Una función que cambia una global | Válido | Imprime `6`; la llamada hace olvidar `g = 5` |
| Temporal que ninguna instrucción lee | Válido | Se borra; el que sí se lee se conserva |
| Variable del programa que nadie lee | Válido | No se borra |
| `@t1 = a / b` sin lectores | Límite | Se conserva, porque `b` podría valer 0; con divisor constante distinto de cero se borra |
| `@t1 = call f, 0` sin lectores | Válido | La llamada se conserva |
| Una lista de instrucciones optimizada | Válido | La lista original no cambia |
| `examples/optimizacion.src` | Válido | 27 instrucciones bajan a 23, con las mismas etiquetas y saltos; imprime `20` y `17` |
| `examples/factorial.src` | Válido | Imprime `120` antes y después de optimizar |
| `examples/completo.src` | Válido | Misma serie de Fibonacci y mismos `55`, `true` y `3` antes y después de optimizar |

## 6. Uso de IA

Se usó Claude (Anthropic) como asistente en esta fase. Claude Code propuso y explicó, paso a paso, el generador de código intermedio, el optimizador y sus pruebas (`src/ir/`, `src/optimizer/` y `tests/ir/`). Yo revisé y entendí cada parte, ejecuté las pruebas e hice los commits desde mi cuenta. También ayudó con la documentación: a escribir esta sección y la del optimizador en `docs/arquitectura.md`, a proponer el programa `examples/optimizacion.src` y su prueba en `tests/ir/test_criterio.py`, y a revisar que cada afirmación del texto coincidiera con el código y con la especificación del lenguaje. Esa revisión corrigió varias frases: una decía que todas las funciones terminan con un `return` agregado por el generador, cuando solo lo reciben los procedimientos y el programa principal, y otra decía que evaluar los dos lados de `&&` nunca se nota, cuando la especificación dice que se nota si un operando llama a una función que imprime.

Los programas y los listados de código intermedio de este documento se obtuvieron ejecutando `python -m src.main`, no se escribieron a mano. Las pruebas nuevas y la suite completa se ejecutaron antes de dar el trabajo por bueno. Todo el texto se leyó y se revisó contra los listados antes de entregarlo.

## 7. Conclusión personal

Lo que más me costó de esta fase fue el `while` y las llamadas con `param`. Del `while` lo difícil es que no es una sola instrucción: son dos etiquetas y dos saltos, y la condición tiene que calcularse después de la etiqueta del inicio y no antes, porque si no el ciclo usaría siempre el valor de la primera vuelta. En el código intermedio un ciclo es solo un salto hacia atrás. De las llamadas me costó el orden: los argumentos se evalúan todos primero y solo después se emiten los `param`, de modo que en `suma(1, doble(2))` los `param` de cada llamada quedan juntos, justo antes de su `call`. Entender esos dos casos me ayudó a ver que el código intermedio vuelve explícito lo que el lenguaje deja implícito.
