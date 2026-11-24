"""Traduce el IR a instrucciones de texto para la máquina de pila."""

from collections.abc import Iterable
from pathlib import Path

from src.ir.instrucciones import (
    OPERACIONES_BINARIAS,
    OPERACIONES_UNARIAS,
    Instruccion,
    Operando,
)

_BINARIAS = frozenset(OPERACIONES_BINARIAS.values())
_UNARIAS = frozenset(OPERACIONES_UNARIAS.values())


def _apilar(operando: Operando) -> str:
    if isinstance(operando, str):
        return f"LOAD {operando}"
    if isinstance(operando, bool):
        return "PUSH true" if operando else "PUSH false"
    return f"PUSH {operando}"


def generar(instrucciones: Iterable[Instruccion]) -> list[str]:
    """Devuelve las instrucciones objetivo, en el orden del IR."""
    codigo: list[str] = []
    en_funcion = False

    for instruccion in instrucciones:
        op = instruccion.op
        arg1, arg2 = instruccion.arg1, instruccion.arg2
        destino, etiqueta = instruccion.destino, instruccion.etiqueta

        if op in _BINARIAS:
            codigo.extend((_apilar(arg1), _apilar(arg2), op.upper(), f"STORE {destino}"))
        elif op in _UNARIAS:
            codigo.extend((_apilar(arg1), op.upper(), f"STORE {destino}"))
        else:
            match op:
                case "copy":
                    codigo.extend((_apilar(arg1), f"STORE {destino}"))
                case "label":
                    codigo.append(f"LABEL {etiqueta}")
                case "goto":
                    codigo.append(f"JMP {etiqueta}")
                case "if_false":
                    codigo.extend((_apilar(arg1), f"JZ {etiqueta}"))
                case "param":
                    codigo.append(_apilar(arg1))
                case "call":
                    codigo.append(f"CALL {arg1} {arg2}")
                    if destino is not None:
                        codigo.append(f"STORE {destino}")
                case "return":
                    if arg1 is not None:
                        codigo.append(_apilar(arg1))
                    codigo.append("RET" if en_funcion else "HALT")
                case "print":
                    codigo.extend((_apilar(arg1), "PRINT"))
                case "func":
                    en_funcion = True
                    codigo.append(" ".join(("FUNC", arg1, *instruccion.params)))
                case "endfunc":
                    en_funcion = False
                case _:
                    raise ValueError(f"Operación de IR desconocida: {op}")

    return codigo


def guardar(codigo: Iterable[str], destino: Path) -> None:
    """Escribe una instrucción por línea en un archivo UTF-8."""
    with destino.open("w", encoding="utf-8", newline="\n") as archivo:
        for linea in codigo:
            archivo.write(f"{linea}\n")
