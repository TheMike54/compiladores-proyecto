"""Recorrido del AST con el patrón visitor.

Una fase hereda de `Visitor` y define `visitar_<NombreDeClase>` para cada nodo que le
interesa, por ejemplo `visitar_While(self, nodo)`. Los nodos sin método propio caen en
`visitar_generico`, que recorre sus hijos en orden.
"""

from dataclasses import fields

from .nodos import Nodo


class Visitor:
    def visitar(self, nodo: Nodo):
        metodo = getattr(self, f"visitar_{type(nodo).__name__}", self.visitar_generico)
        return metodo(nodo)

    def visitar_generico(self, nodo: Nodo):
        for hijo in hijos(nodo):
            self.visitar(hijo)


def hijos(nodo: Nodo) -> list[Nodo]:
    """Los nodos hijos directos, en el orden en que se declararon sus campos."""
    resultado: list[Nodo] = []
    for campo in fields(nodo):
        valor = getattr(nodo, campo.name)
        if isinstance(valor, Nodo):
            resultado.append(valor)
        elif isinstance(valor, list):
            resultado.extend(v for v in valor if isinstance(v, Nodo))
    return resultado
