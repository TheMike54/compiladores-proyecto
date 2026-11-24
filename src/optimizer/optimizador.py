"""Optimizador local sobre el código de tres direcciones: plegado de constantes, propagación de copias y
eliminación de temporales que nadie lee.

Trabaja dentro de bloques básicos: un tramo de instrucciones que se ejecuta siempre de principio a fin. Lo que se
sabe de las variables vale solo dentro del bloque, así que al llegar a una etiqueta, a un salto, a un `return` o a
una llamada se olvida todo. Las optimizaciones no cambian lo que imprime el programa porque solo usan hechos que
son ciertos en todas las ejecuciones posibles que llegan a ese punto.
"""

from dataclasses import replace

from src.ir.instrucciones import Instruccion, Operando

MINIMO, MAXIMO = -(2**31), 2**31 - 1  # rango de `int` (especificación del lenguaje, sección 2)


def _dividir(a: int, b: int) -> int:
    """División entera truncada hacia cero, como en C (`//` de Python redondea hacia abajo)."""
    cociente = abs(a) // abs(b)
    return cociente if (a < 0) == (b < 0) else -cociente


def _residuo(a: int, b: int) -> int:
    """Residuo con el signo del dividendo: a == b * (a / b) + (a % b)."""
    return a - b * _dividir(a, b)


_BINARIAS = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": _dividir,
    "mod": _residuo,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
}
_UNARIAS = {"neg": lambda a: -a, "not": lambda a: not a}

# Instrucciones que leen `arg1` como un operando (en `call`, `func` y `endfunc` es un nombre de función).
_LEEN_ARG1 = {"copy", "if_false", "param", "return", "print"} | _BINARIAS.keys() | _UNARIAS.keys()
# Instrucciones que, además, leen `arg2` como operando (en `call` es el número de argumentos).
_LEEN_ARG2 = _BINARIAS.keys()
# Después de estas instrucciones empieza otro bloque básico: no se arrastra nada.
_CORTAN_BLOQUE = {"label", "func", "endfunc", "goto", "if_false", "return", "call"}


def _es_constante(operando: Operando | None) -> bool:
    return isinstance(operando, (int, bool))


def _cabe_en_int(valor: Operando) -> bool:
    return isinstance(valor, bool) or MINIMO <= valor <= MAXIMO


def _sustituir(instruccion: Instruccion, copias: dict[str, Operando]) -> Instruccion:
    """Cambia cada operando leído por el valor que se sabe que tiene (otra variable o una constante)."""
    cambios: dict[str, Operando] = {}
    if instruccion.op in _LEEN_ARG1 and isinstance(instruccion.arg1, str):
        cambios["arg1"] = copias.get(instruccion.arg1, instruccion.arg1)
    if instruccion.op in _LEEN_ARG2 and isinstance(instruccion.arg2, str):
        cambios["arg2"] = copias.get(instruccion.arg2, instruccion.arg2)
    return replace(instruccion, **cambios)


def _plegar(instruccion: Instruccion) -> Instruccion:
    """Si todos los operandos son constantes, calcula el resultado ahora y lo deja como una copia."""
    if instruccion.op in _BINARIAS and _es_constante(instruccion.arg1) and _es_constante(instruccion.arg2):
        if instruccion.op in ("div", "mod") and instruccion.arg2 == 0:
            return instruccion  # el error de división entre cero debe seguir ocurriendo al ejecutar
        resultado = _BINARIAS[instruccion.op](instruccion.arg1, instruccion.arg2)
    elif instruccion.op in _UNARIAS and _es_constante(instruccion.arg1):
        resultado = _UNARIAS[instruccion.op](instruccion.arg1)
    else:
        return instruccion
    if not _cabe_en_int(resultado):
        return instruccion  # fuera de 32 bits: se deja para la ejecución
    return Instruccion("copy", destino=instruccion.destino, arg1=resultado)


def _olvidar(copias: dict[str, Operando], variable: str) -> None:
    """`variable` cambió de valor: ya no se sabe qué vale ella ni las variables que eran copia de ella."""
    copias.pop(variable, None)
    for nombre in [n for n, valor in copias.items() if valor == variable]:
        del copias[nombre]


def propagar_y_plegar(instrucciones: list[Instruccion]) -> list[Instruccion]:
    """Primera pasada: propagación de copias y plegado de constantes. Devuelve una lista nueva."""
    resultado: list[Instruccion] = []
    copias: dict[str, Operando] = {}  # variable -> constante o variable que se sabe que vale lo mismo

    for original in instrucciones:
        instruccion = _plegar(_sustituir(original, copias))

        if instruccion.op == "copy" and instruccion.arg1 == instruccion.destino:
            continue  # `x = x` no hace nada

        resultado.append(instruccion)
        if instruccion.op in _CORTAN_BLOQUE:
            copias.clear()
        elif instruccion.destino is not None:
            _olvidar(copias, instruccion.destino)
            if instruccion.op == "copy":
                copias[instruccion.destino] = instruccion.arg1

    return resultado


def _es_temporal(nombre: str | None) -> bool:
    return nombre is not None and nombre.startswith("@t")


def _sin_efectos(instruccion: Instruccion) -> bool:
    """Calcular y descartar el resultado no tiene otro efecto (no imprime, no salta, no puede fallar)."""
    if instruccion.op in ("div", "mod"):
        return _es_constante(instruccion.arg2) and instruccion.arg2 != 0  # si no, puede dividir entre cero
    return instruccion.op in _BINARIAS or instruccion.op in _UNARIAS or instruccion.op == "copy"


def _operandos_leidos(instruccion: Instruccion) -> list[Operando]:
    leidos: list[Operando] = []
    if instruccion.op in _LEEN_ARG1:
        leidos.append(instruccion.arg1)
    if instruccion.op in _LEEN_ARG2:
        leidos.append(instruccion.arg2)
    return leidos


def quitar_temporales_muertos(instrucciones: list[Instruccion]) -> list[Instruccion]:
    """Segunda pasada: borra las instrucciones que solo calculan un temporal que nadie lee.

    Solo toca temporales (`@t1`, ...), nunca variables del programa, y solo instrucciones sin efectos. Se repite
    hasta que no haya cambios, porque borrar una puede dejar sin uso a la que calculaba su operando.
    """
    while True:
        usados = {o for i in instrucciones for o in _operandos_leidos(i) if isinstance(o, str)}
        vivas = [
            i for i in instrucciones if not (_es_temporal(i.destino) and i.destino not in usados and _sin_efectos(i))
        ]
        if len(vivas) == len(instrucciones):
            return vivas
        instrucciones = vivas


def optimizar(instrucciones: list[Instruccion]) -> list[Instruccion]:
    """Devuelve una lista nueva con las mismas instrucciones, mejoradas. No modifica la de entrada."""
    return quitar_temporales_muertos(propagar_y_plegar(instrucciones))
