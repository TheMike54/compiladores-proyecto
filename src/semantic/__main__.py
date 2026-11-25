"""Corre el front-end completo (léxico, sintáctico y semántico) sobre un archivo.

    python -m src.semantic <archivo.src> [--ast]

Sin errores imprime la tabla de símbolos por ámbitos (y el AST con tipos si se pide);
con errores los imprime todos. Códigos de salida como en src.main: 0, 1 o 2.
"""

import argparse
import sys
from pathlib import Path

from src.ast import arbol_texto
from src.lexer import tokenizar
from src.parser import analizar as analizar_sintaxis

from .analizador import analizar


def main(argv: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(prog="python -m src.semantic", description="Análisis semántico de MiniLang")
    opciones.add_argument("archivo", type=Path, help="programa fuente (.src)")
    opciones.add_argument("--ast", action="store_true", help="muestra el árbol con el tipo de cada expresión")
    args = opciones.parse_args(argv)

    try:
        fuente = args.archivo.read_text(encoding="utf-8")
    except OSError as e:
        print(f"No se pudo leer {args.archivo}: {e.strerror}", file=sys.stderr)
        return 2

    tokens, errores = tokenizar(fuente)
    if not errores:
        programa, errores = analizar_sintaxis(tokens)
    if not errores:
        tabla, errores = analizar(programa)
    if errores:
        for error in errores:
            print(error, file=sys.stderr)
        return 1

    if args.ast:
        print("== AST CON TIPOS ==")
        print(arbol_texto(programa, mostrar_tipos=True))
        print()
    print("== TABLA DE SÍMBOLOS ==")
    print(tabla.texto())
    return 0


if __name__ == "__main__":
    # Al redirigir la salida a un archivo, Windows usa cp1252, que no tiene los caracteres del árbol (├──).
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
