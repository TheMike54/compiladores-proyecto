"""Formato del código intermedio de tres direcciones (contrato entre el generador de IR,
el optimizador y el backend). La explicación completa está en docs/arquitectura.md.

Un operando es:
- `str`: nombre de una variable del programa o de un temporal (`@t1`, `@t2`, ...);
- `int` o `bool`: una constante.
Las etiquetas son `str` (`@L1`, `@L2`, ..., y `@main`) y viven en el campo `etiqueta`. Los nombres internos
empiezan con `@` para no chocar con los del programa.
"""

from dataclasses import dataclass

Operando = str | int | bool

# Operadores binarios del lenguaje -> nombre de la operación en el IR.
OPERACIONES_BINARIAS = {
    "+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod",
    "==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge",
    "&&": "and", "||": "or",
}
OPERACIONES_UNARIAS = {"-": "neg", "!": "not"}

SIMBOLO = {v: k for k, v in OPERACIONES_BINARIAS.items()} | {"neg": "-", "not": "!"}


@dataclass
class Instruccion:
    """Una instrucción de tres direcciones.

    | op                     | campos usados          | significado                        |
    |------------------------|------------------------|------------------------------------|
    | add sub mul div mod    | destino, arg1, arg2    | destino = arg1 <op> arg2           |
    | eq ne lt le gt ge      | destino, arg1, arg2    | destino = arg1 <op> arg2 (bool)    |
    | and or                 | destino, arg1, arg2    | destino = arg1 <op> arg2 (bool)    |
    | neg not                | destino, arg1          | destino = <op> arg1                |
    | copy                   | destino, arg1          | destino = arg1                     |
    | label                  | etiqueta               | marca un punto de salto            |
    | goto                   | etiqueta               | salta siempre                      |
    | if_false               | arg1, etiqueta         | salta si arg1 es falso             |
    | param                  | arg1                   | apila un argumento para la llamada |
    | call                   | destino?, arg1, arg2   | destino = arg1(...) con arg2 args  |
    | return                 | arg1?                  | regresa (con valor o sin él)       |
    | print                  | arg1                   | imprime arg1                       |
    | func                   | arg1, params           | inicio de la función arg1          |
    | endfunc                | arg1                   | fin de la función arg1             |
    """

    op: str
    destino: str | None = None
    arg1: Operando | None = None
    arg2: Operando | None = None
    etiqueta: str | None = None
    params: tuple[str, ...] = ()

    def __str__(self) -> str:
        a1, a2 = _texto(self.arg1), _texto(self.arg2)
        match self.op:
            case "copy":
                return f"    {self.destino} = {a1}"
            case "neg" | "not":
                return f"    {self.destino} = {SIMBOLO[self.op]}{a1}"
            case "label":
                return f"{self.etiqueta}:"
            case "goto":
                return f"    goto {self.etiqueta}"
            case "if_false":
                return f"    if_false {a1} goto {self.etiqueta}"
            case "param":
                return f"    param {a1}"
            case "call":
                llamada = f"call {a1}, {a2}"
                return f"    {self.destino} = {llamada}" if self.destino else f"    {llamada}"
            case "return":
                return "    return" if self.arg1 is None else f"    return {a1}"
            case "print":
                return f"    print {a1}"
            case "func":
                return f"func {a1}({', '.join(self.params)})"
            case "endfunc":
                return f"endfunc {a1}"
            case _ if self.op in SIMBOLO:
                return f"    {self.destino} = {a1} {SIMBOLO[self.op]} {a2}"
        return f"    {self.op} {self.destino} {a1} {a2} {self.etiqueta}"


def _texto(operando: Operando | None) -> str:
    if isinstance(operando, bool):
        return "true" if operando else "false"
    return str(operando)


def listado(instrucciones: list[Instruccion]) -> str:
    return "\n".join(str(i) for i in instrucciones)
