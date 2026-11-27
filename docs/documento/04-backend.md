# Generación de código objetivo y máquina de pila

El backend recibe el código intermedio optimizado (IR) y lo convierte en un programa que la máquina de pila puede ejecutar. El generador escribe una instrucción por línea en un archivo de texto con extensión `.pila`. El simulador abre ese archivo, ejecuta las instrucciones y muestra la salida del programa MiniLang.

## 1. Generación de código objetivo

El IR indica los operandos y el destino de una operación. La máquina toma los operandos de la pila. Por eso, el generador primero coloca los valores en la pila, emite la operación y guarda el resultado en el destino. Emite `PUSH` para una constante y `LOAD` para una variable o un temporal. En una operación binaria coloca primero el valor izquierdo y luego el derecho. En una operación unaria coloca un solo valor. En ambos casos, `STORE` recoge el resultado.

En `examples/factorial.src`, la multiplicación `@t2 = resultado * n` del IR se traduce a este fragmento real del código objetivo:

```text
LOAD resultado
LOAD n
MUL
STORE @t2
```

Así se traduce el resto del IR:

| Instrucción del IR | Código objetivo |
| --- | --- |
| Copia o asignación | `PUSH` o `LOAD` para obtener el valor, seguido de `STORE`. |
| Operación binaria | Dos operandos, la operación correspondiente y `STORE`. |
| Operación unaria | Un operando, `NEG` o `NOT`, y `STORE`. |
| Etiqueta y salto incondicional | `LABEL` marca el destino y `JMP` salta a él. |
| Salto condicional | Se coloca la condición en la pila y `JZ` salta si es falsa. |
| Inicio y fin de función | `FUNC` registra el nombre y los parámetros. La marca de fin delimita la función en el IR. |
| Parámetro y llamada | Cada argumento se coloca en la pila en orden. `CALL` indica la función y el número de argumentos. Si la llamada tiene destino, se guarda el resultado con `STORE`. |
| Retorno | Dentro de una función, se coloca el valor si existe y se emite `RET`. El retorno del programa principal se traduce a `HALT`. |
| Impresión | Se coloca el valor en la pila y se emite `PRINT`. |

## 2. Máquina de pila

El simulador registra las etiquetas y funciones antes de ejecutar para que los saltos puedan apuntar a instrucciones que aparecen después. La ejecución empieza en `LABEL @main`. La pila de operandos guarda los valores que se están usando: el último en entrar es el primero en salir. Para una resta, `SUB` saca primero el operando derecho y luego el izquierdo. Con los valores 7 y 2 apilados en ese orden, la operación deja 5.

Cada llamada crea un marco con su propia pila, sus variables locales y la dirección de regreso. `CALL` retira los argumentos de la pila del llamador y los asigna a los parámetros en orden. `RET` restaura el marco anterior y le entrega el valor de retorno si lo hay. Las variables globales se comparten entre los marcos. `LOAD` busca primero en las variables del marco actual y después en las globales. `STORE` actualiza una variable global existente si el marco actual no tiene una variable con ese nombre.

El repertorio incluye `PUSH`, `LOAD` y `STORE` para mover valores, `ADD`, `SUB`, `MUL`, `DIV`, `MOD` y `NEG` para aritmética, `EQ`, `NE`, `LT`, `LE`, `GT` y `GE` para comparaciones, y `AND`, `OR` y `NOT` para lógica. El flujo se controla con `LABEL`, `JMP`, `JZ`, `FUNC`, `CALL` y `RET`. `PRINT` muestra el valor de la cima y lo retira. `HALT` termina el programa.

El simulador reporta división o módulo entre cero, resultados fuera del rango de enteros con signo de 32 bits, lectura de variables sin valor y exceso de llamadas al superar los 1000 marcos de función. Si hay un error, el comando informa el motivo y devuelve código de salida 1.

## 3. Reproducción

Desde PowerShell, con Git y Python 3.12 o superior:

```powershell
git clone https://github.com/TheMike54/compiladores-proyecto.git
cd compiladores-proyecto
python -m src.main examples/factorial.src --todo
python -m unittest discover -s tests -t . -v
```

El compilador usa la biblioteca estándar de Python. `--todo` muestra los tokens, el AST, la tabla de símbolos, el IR original, el IR optimizado y el código objetivo. También puedes seleccionar artefactos con `--tokens`, `--ast`, `--simbolos`, `--ir`, `--ir-opt` y `--objetivo`. Sin opciones, el comando compila y ejecuta, y la consola muestra la salida del programa.

Estas son las últimas líneas de la salida real del factorial con `--todo`:

```text
JMP @L1
LABEL @L2
LOAD resultado
PRINT
HALT

120
```

`JMP @L1` vuelve a comprobar la condición del ciclo. Cuando la condición es falsa, el salto condicional lleva la ejecución a `@L2`, donde se imprime el resultado. El archivo generado es `build/factorial.pila` y se puede volver a ejecutar con `python -m src.backend.maquina build/factorial.pila`.

## 4. Limitaciones

El código objetivo está diseñado para el simulador de MiniLang y requiere ese simulador para ejecutarse. Esto permite guardar y leer las instrucciones en un formato de texto sencillo. El archivo `.pila` carece de ubicaciones del código fuente, por lo que al ejecutarlo directamente una posición desconocida se muestra como línea y columna 0.

## 5. Casos de prueba

| Caso | Válido o inválido | Resultado esperado |
| --- | --- | --- |
| `examples/factorial.src` | Válido | Genera `build/factorial.pila` e imprime `120`. |
| Llamada a una función que resta 7 y 2 | Válido | Los argumentos conservan su orden y se imprime `5`. |
| División y residuo de −7 entre 2 | Válido | Se imprimen `-3` y `-1`, respectivamente. |
| División o módulo entre cero | Inválido | Se informa el error de ejecución correspondiente. |
| Lectura de una variable sin valor | Inválido | El mensaje identifica la variable. |
| Suma de 2147483647 y 1 | Inválido | Se informa que el resultado no cabe en un entero de 32 bits. |
| Recursión que supera el límite de llamadas | Inválido | Se informa un desbordamiento de la pila de llamadas. |

## 6. Uso de IA

Se usó Codex como apoyo para implementar el generador, el simulador y la integración del comando único, y para preparar las pruebas y revisar la redacción de esta sección. Los fragmentos del factorial se obtuvieron ejecutando el compilador.

## 7. Conclusión personal

Al trabajar con este backend entendí por qué importa el orden de los valores en la pila. En una resta, sacar primero el operando derecho ayuda a conservar la operación tal como se escribió. Seguir el factorial desde el IR hasta la salida también me permitió ver cómo un ciclo que parece una sola instrucción en MiniLang se convierte en comparaciones, saltos y operaciones más sencillas.
