"""Representación del AST como árbol de texto, para los artefactos y la depuración."""

from dataclasses import fields

from .nodos import Expresion, Nodo

OMITIDOS = {"linea", "columna", "tipo"}


def arbol_texto(nodo: Nodo, mostrar_tipos: bool = False) -> str:
    lineas: list[str] = []
    _imprimir(nodo, "", "", lineas, mostrar_tipos)
    return "\n".join(lineas)


def _etiqueta(nodo: Nodo, mostrar_tipos: bool) -> str:
    atributos = []
    for campo in fields(nodo):
        valor = getattr(nodo, campo.name)
        if campo.name in OMITIDOS or isinstance(valor, (Nodo, list)) or valor is None:
            continue
        atributos.append(f"{campo.name}={valor!r}")
    if mostrar_tipos and isinstance(nodo, Expresion) and nodo.tipo:
        atributos.append(f": {nodo.tipo}")
    texto = type(nodo).__name__
    if atributos:
        texto += " " + " ".join(atributos)
    return f"{texto}  ({nodo.linea}:{nodo.columna})"


def _imprimir(nodo: Nodo, prefijo: str, conector: str, lineas: list[str], mostrar_tipos: bool) -> None:
    lineas.append(prefijo + conector + _etiqueta(nodo, mostrar_tipos))
    if conector:
        prefijo += "│   " if conector == "├── " else "    "
    secciones = []
    for campo in fields(nodo):
        valor = getattr(nodo, campo.name)
        if isinstance(valor, Nodo):
            secciones.append((campo.name, [valor]))
        elif isinstance(valor, list) and valor:
            secciones.append((campo.name, [v for v in valor if isinstance(v, Nodo)]))
    hijos = [(nombre, h) for nombre, lista in secciones for h in lista]
    for i, (nombre, hijo) in enumerate(hijos):
        ultimo = i == len(hijos) - 1
        _imprimir(hijo, prefijo, "└── " if ultimo else "├── ", lineas, mostrar_tipos)
