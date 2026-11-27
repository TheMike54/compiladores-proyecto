# Compilador — Proyecto integrador de Compiladores

ESCOM-IPN · C501 Compiladores · 5CV4 · Prof. Enrique Alfonso Carmona García

Compilador para un lenguaje educativo de tamaño controlado, construido por fases: análisis léxico, análisis
sintáctico con AST, tabla de símbolos, análisis semántico, código intermedio de tres direcciones, optimización y
generación de código para una máquina de pila simulada.

## Integrantes
- Miguel Ángel Rodríguez Candelario
- Iván López García
- Aldo Manuel Díaz Pineda
- Zareth Samai Santiago Acosta

## Estructura

```
docs/        especificación del lenguaje, gramática y arquitectura
src/         una carpeta por fase: lexer, parser, ast, semantic, ir, optimizer, backend
tests/       pruebas por fase y de extremo a extremo
examples/    programas de ejemplo
```

## Requisitos
- Python 3.12 o superior, sin dependencias externas.

## Instalación y ejecución

Desde PowerShell, clona el repositorio y entra en su carpeta. Python 3.12 o
superior es el único requisito.

```powershell
git clone https://github.com/TheMike54/compiladores-proyecto.git
cd compiladores-proyecto
python -m src.main examples/factorial.src
```

El ejemplo imprime `120` y guarda las instrucciones de pila en
`build/factorial.pila`. Otro ejemplo, `python -m src.main examples/completo.src`,
imprime los primeros once números de Fibonacci y termina con `55`, `true` y `3`,
cada valor en su propia línea.

Para ver todas las etapas junto con la salida del programa:

```powershell
python -m src.main examples/factorial.src --todo
```

Puedes ver etapas individuales con `--tokens`, `--ast`, `--simbolos`, `--ir`,
`--ir-opt` o `--objetivo`. El comando devuelve `0` al terminar correctamente,
`1` si falla una fase y `2` si el archivo fuente no se puede leer.


## Ejemplo con errores

```powershell
python -m src.main examples/error_semantico.src
```

El comando identifica, entre otros, una variable sin declarar. La salida completa es:

```text
Error semántico [línea 5, columna 1]: la variable 'contador' no está declarada
Error semántico [línea 6, columna 15]: el operador '+' necesita int y int, y recibió int y bool
Error semántico [línea 7, columna 5]: la condición del 'if' debe ser bool y es int
```

Un error que ocurre al ejecutar el programa, como una división entre cero,
se muestra con el prefijo `Error de ejecución` y la ubicación de la sentencia
en el archivo fuente.

## Artefactos de ejemplo

`examples/salidas/` guarda lo que produce cada fase para tres programas válidos (`factorial`, `completo` y
`optimizacion`): tokens, AST, tabla de símbolos, IR, IR optimizado, código objetivo (`objetivo.pila`) y la salida del
programa. Para los tres ejemplos con errores guarda los mensajes (`errores.txt`). Una prueba comprueba que estos
archivos siguen iguales a lo que imprime el compilador; después de un cambio intencional se regeneran con:

```powershell
python -m tests.end_to_end.test_salidas
```

## Pruebas

```powershell
python -m unittest discover -s tests -t . -v
```

Hay pruebas por fase en `tests/lexical/`, `tests/syntax/`, `tests/semantic/` e `tests/ir/`, y pruebas del comando
completo y de la máquina de pila en `tests/end_to_end/`.

## Documentación

- `docs/especificacion-lenguaje.md`: tokens, tipos, operadores, sentencias y reglas de alcance de MiniLang.
- `docs/gramatica.md`: gramática final, transformaciones, método de parsing y recuperación de errores.
- `docs/arquitectura.md`: diagrama de fases y contrato entre ellas (AST, tabla de símbolos, IR, optimizador y
  máquina de pila).
- `docs/documento/`: secciones del documento técnico entregado en PDF.

## Uso de IA

El equipo usó asistentes de IA y declara para qué:

- Claude Code (Anthropic): análisis léxico y sintáctico, AST, especificación, gramática y contrato entre fases; apoyo
  en el análisis semántico (revisión de la lógica y de las pruebas); generador de código intermedio, optimizador y sus
  pruebas; redacción y revisión de la documentación.
- Codex (OpenAI): generador de código objetivo, máquina de pila, comando único y sus pruebas, y la sección del
  documento sobre el backend.

Cada integrante revisó, probó y puede explicar la parte que entregó. El detalle está en la sección «Uso de IA» de cada
parte del documento técnico.
