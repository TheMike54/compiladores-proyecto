"""Compila y ejecuta un programa MiniLang. Detiene el flujo si una fase falla."""

import argparse
import sys
from pathlib import Path

from src.ast import arbol_texto
from src.backend.generador import generar as generar_objetivo
from src.backend.generador import guardar
from src.backend.maquina import ejecutar_archivo
from src.ir import generar as generar_ir
from src.ir import listado
from src.lexer import tokenizar
from src.optimizer import optimizar
from src.parser import analizar as analizar_sintaxis


def main(argv: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(prog="python -m src.main", description="Compilador de MiniLang")
    opciones.add_argument("archivo", type=Path, help="programa fuente (.src)")
    opciones.add_argument("--tokens", action="store_true", help="muestra la lista de tokens")
    opciones.add_argument("--ast", action="store_true", help="muestra el árbol de sintaxis")
    opciones.add_argument("--simbolos", action="store_true", help="muestra la tabla de símbolos")
    opciones.add_argument("--ir", action="store_true", help="muestra el código intermedio")
    opciones.add_argument("--ir-opt", action="store_true", help="muestra el código intermedio optimizado")
    opciones.add_argument("--objetivo", action="store_true", help="muestra el código de la máquina de pila")
    opciones.add_argument("--todo", action="store_true", help="muestra todos los artefactos")
    args = opciones.parse_args(argv)

    try:
        fuente = args.archivo.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        print(f"No se pudo leer {args.archivo}: {error}", file=sys.stderr)
        return 2

    tokens, errores = tokenizar(fuente)
    if args.tokens or args.todo:
        _seccion("TOKENS", "\n".join(str(token) for token in tokens))
    if errores:
        return _reportar(errores)

    programa, errores = analizar_sintaxis(tokens)
    if args.ast or args.todo:
        _seccion("AST", arbol_texto(programa))
    if errores:
        return _reportar(errores)

    try:
        from src.semantic import analizar as analizar_semantica
    except ModuleNotFoundError as error:
        if error.name != "src.semantic":
            raise
        print("El compilador requiere la fase src.semantic para continuar.", file=sys.stderr)
        return 1

    # El semántico anota el mismo AST con los tipos y nombres que necesita el IR.
    tabla, errores = analizar_semantica(programa)
    if args.simbolos or args.todo:
        _seccion("TABLA DE SÍMBOLOS", tabla.texto())
    if errores:
        return _reportar(errores)

    instrucciones = generar_ir(programa)
    if args.ir or args.todo:
        _seccion("IR", listado(instrucciones))

    instrucciones_optimizadas = optimizar(instrucciones)
    if args.ir_opt or args.todo:
        _seccion("IR OPTIMIZADO", listado(instrucciones_optimizadas))

    codigo_objetivo = generar_objetivo(instrucciones_optimizadas)
    if args.objetivo or args.todo:
        _seccion("CÓDIGO OBJETIVO", "\n".join(codigo_objetivo))

    destino = Path("build") / args.archivo.with_suffix(".pila").name
    try:
        destino.parent.mkdir(exist_ok=True)
        guardar(codigo_objetivo, destino)
    except OSError as error:
        print(f"No se pudo guardar {destino}: {error}", file=sys.stderr)
        return 1

    try:
        error = ejecutar_archivo(destino)
    except (OSError, UnicodeError) as error:
        print(f"No se pudo leer {destino}: {error}", file=sys.stderr)
        return 1
    if error is not None:
        return _reportar([error])
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
    # Windows puede elegir cp1252 al redirigir la salida, que no admite el dibujo del AST.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
