"""Comando único del compilador: python -m src.main <archivo.src> [opciones].

Corre las fases en orden y se detiene después de la primera fase que reporte errores,
mostrando todos los errores de esa fase.
"""

import argparse
import sys
from pathlib import Path

from src.ast import arbol_texto
from src.lexer import tokenizar
from src.parser import analizar


def main(argv: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(prog="python -m src.main", description="Compilador de MiniLang")
    opciones.add_argument("archivo", type=Path, help="programa fuente (.src)")
    opciones.add_argument("--tokens", action="store_true", help="muestra la lista de tokens")
    opciones.add_argument("--ast", action="store_true", help="muestra el árbol de sintaxis")
    args = opciones.parse_args(argv)

    try:
        fuente = args.archivo.read_text(encoding="utf-8")
    except OSError as e:
        print(f"No se pudo leer {args.archivo}: {e.strerror}", file=sys.stderr)
        return 2

    tokens, errores = tokenizar(fuente)
    if args.tokens:
        _seccion("TOKENS", "\n".join(str(t) for t in tokens))
    if errores:
        return _reportar(errores)

    programa, errores = analizar(tokens)
    if args.ast:
        _seccion("AST", arbol_texto(programa))
    if errores:
        return _reportar(errores)

    print("Análisis léxico y sintáctico sin errores.")
    return 0


def _seccion(titulo: str, contenido: str) -> None:
    print(f"== {titulo} ==")
    print(contenido)
    print()


def _reportar(errores) -> int:
    for error in errores:
        print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    # En Windows, al redirigir la salida a un archivo Python usa cp1252, que no tiene los caracteres del árbol.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
