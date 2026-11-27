"""Traduce el código intermedio (IR) a instrucciones para la máquina de pila."""

from collections.abc import Iterable
from pathlib import Path

from src.errores import Ubicacion

from src.ir.instrucciones import (
    OPERACIONES_BINARIAS,
    OPERACIONES_UNARIAS,
    Instruccion,
    Operando,
)

_OPERACIONES_DE_DOS_OPERANDOS = frozenset(OPERACIONES_BINARIAS.values())
_OPERACIONES_DE_UN_OPERANDO = frozenset(OPERACIONES_UNARIAS.values())


def _instruccion_para_apilar(operando: Operando) -> str:
    """Genera una instrucción para poner una variable o constante en la pila."""
    # El IR representa los nombres de variables y temporales como texto.
    if isinstance(operando, str):
        return f"LOAD {operando}"
    if isinstance(operando, bool):
        return "PUSH true" if operando else "PUSH false"
    return f"PUSH {operando}"


def generar(
    instrucciones: Iterable[Instruccion], *, ubicaciones: list[Ubicacion] | None = None
) -> list[str]:
    """Traduce el IR y, si se solicita, agrega una ubicación por línea emitida."""
    codigo_objetivo: list[str] = []
    dentro_de_funcion = False

    for instruccion in instrucciones:
        inicio = len(codigo_objetivo)
        match instruccion.op:
            case operacion if operacion in _OPERACIONES_DE_DOS_OPERANDOS:
                # Apila primero el operando izquierdo. El orden importa en SUB y DIV.
                codigo_objetivo.append(_instruccion_para_apilar(instruccion.arg1))
                codigo_objetivo.append(_instruccion_para_apilar(instruccion.arg2))
                codigo_objetivo.append(operacion.upper())
                codigo_objetivo.append(f"STORE {instruccion.destino}")

            case operacion if operacion in _OPERACIONES_DE_UN_OPERANDO:
                codigo_objetivo.append(_instruccion_para_apilar(instruccion.arg1))
                codigo_objetivo.append(operacion.upper())
                codigo_objetivo.append(f"STORE {instruccion.destino}")

            case "copy":
                codigo_objetivo.append(_instruccion_para_apilar(instruccion.arg1))
                codigo_objetivo.append(f"STORE {instruccion.destino}")

            case "label":
                codigo_objetivo.append(f"LABEL {instruccion.etiqueta}")

            case "goto":
                codigo_objetivo.append(f"JMP {instruccion.etiqueta}")

            case "if_false":
                # JZ toma de la pila el valor con el que decide si debe saltar.
                codigo_objetivo.append(_instruccion_para_apilar(instruccion.arg1))
                codigo_objetivo.append(f"JZ {instruccion.etiqueta}")

            case "param":
                codigo_objetivo.append(_instruccion_para_apilar(instruccion.arg1))

            case "call":
                nombre_funcion = instruccion.arg1
                cantidad_argumentos = instruccion.arg2
                codigo_objetivo.append(f"CALL {nombre_funcion} {cantidad_argumentos}")

                # El IR solo indica un destino cuando la llamada devuelve un valor.
                if instruccion.destino is not None:
                    codigo_objetivo.append(f"STORE {instruccion.destino}")

            case "return":
                if instruccion.arg1 is not None:
                    codigo_objetivo.append(_instruccion_para_apilar(instruccion.arg1))

                # En una función se vuelve al llamador. En @main termina el programa.
                if dentro_de_funcion:
                    codigo_objetivo.append("RET")
                else:
                    codigo_objetivo.append("HALT")

            case "print":
                codigo_objetivo.append(_instruccion_para_apilar(instruccion.arg1))
                codigo_objetivo.append("PRINT")

            case "func":
                dentro_de_funcion = True
                encabezado = ("FUNC", instruccion.arg1, *instruccion.params)
                codigo_objetivo.append(" ".join(encabezado))

            case "endfunc":
                # Esta marca del IR solo indica dónde acaba la función.
                dentro_de_funcion = False

            case _:
                raise ValueError(f"Operación de IR desconocida: {instruccion.op}")

        if ubicaciones is not None:
            lineas_emitidas = len(codigo_objetivo) - inicio
            ubicaciones.extend([instruccion.ubicacion] * lineas_emitidas)

    return codigo_objetivo


def guardar(codigo: Iterable[str], destino: Path) -> None:
    """Escribe una instrucción por línea en un archivo UTF-8."""
    with destino.open("w", encoding="utf-8", newline="\n") as archivo:
        for linea in codigo:
            archivo.write(f"{linea}\n")
