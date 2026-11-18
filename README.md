# Compilador — Proyecto integrador de Compiladores

ESCOM-IPN · C501 Compiladores · 5CV4 · Prof. Enrique Alfonso Carmona García

Compilador para un lenguaje educativo de tamaño controlado, construido por fases: análisis léxico, análisis
sintáctico con AST, tabla de símbolos, análisis semántico, código intermedio de tres direcciones, optimización y
generación de código para una máquina de pila simulada.

## Integrantes
- Miguel Ángel Rodríguez Candelario
- Iván López García
- Aldo Manuel Díaz Pineda

## Estructura

```
docs/        especificación del lenguaje, gramática y arquitectura
src/         una carpeta por fase: lexer, parser, ast, semantic, ir, optimizer, backend
tests/       pruebas por fase y de extremo a extremo
examples/    programas de ejemplo
```

## Requisitos
- Python 3.12 o superior, sin dependencias externas.

## Pruebas

```
python -m unittest discover -s tests -t . -v
```
