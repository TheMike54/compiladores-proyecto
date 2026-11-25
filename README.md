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


## Pruebas

```
python -m unittest discover -s tests -t . -v
```
