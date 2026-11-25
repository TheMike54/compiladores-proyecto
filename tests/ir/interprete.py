"""Intérprete mínimo del código de tres direcciones, solo para las pruebas.

Ejecuta una lista de instrucciones y devuelve las líneas que imprime. Sirve para comprobar que el programa
imprime lo mismo antes y después de optimizar. No comparte código con el optimizador a propósito: así un error
de cálculo en uno no se repite en el otro.
"""

from src.ir import Instruccion

LIMITE_DE_PASOS = 200_000


def _dividir(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("división entre cero")
    cociente = abs(a) // abs(b)
    return cociente if (a < 0) == (b < 0) else -cociente


_OPERACIONES = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": _dividir,
    "mod": lambda a, b: a - b * _dividir(a, b),
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
}


def _texto(valor) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return str(valor)


def ejecutar(instrucciones: list[Instruccion]) -> list[str]:
    etiquetas = {i.etiqueta: n for n, i in enumerate(instrucciones) if i.op == "label"}
    funciones = {i.arg1: (n, i.params) for n, i in enumerate(instrucciones) if i.op == "func"}
    globales: dict[str, object] = {}
    salida: list[str] = []
    pasos = 0

    def correr(inicio: int, locales: dict[str, object]):
        nonlocal pasos
        apilados: list[object] = []  # argumentos de `param` que aún no se consumen con un `call`

        def leer(operando):
            if not isinstance(operando, str):
                return operando
            if operando in locales:
                return locales[operando]
            if operando in globales:
                return globales[operando]
            raise NameError(f"la variable '{operando}' se usó antes de tener valor")

        def escribir(nombre: str, valor) -> None:
            # Una variable que no es local pero existe como global se escribe en la global.
            if nombre not in locales and nombre in globales:
                globales[nombre] = valor
            else:
                locales[nombre] = valor

        pc = inicio
        while True:
            pasos += 1
            if pasos > LIMITE_DE_PASOS:
                raise RuntimeError("demasiados pasos: posible ciclo infinito")
            i = instrucciones[pc]
            pc += 1
            if i.op in _OPERACIONES:
                escribir(i.destino, _OPERACIONES[i.op](leer(i.arg1), leer(i.arg2)))
            elif i.op == "neg":
                escribir(i.destino, -leer(i.arg1))
            elif i.op == "not":
                escribir(i.destino, not leer(i.arg1))
            elif i.op == "copy":
                escribir(i.destino, leer(i.arg1))
            elif i.op == "goto":
                pc = etiquetas[i.etiqueta]
            elif i.op == "if_false":
                if not leer(i.arg1):
                    pc = etiquetas[i.etiqueta]
            elif i.op == "param":
                apilados.append(leer(i.arg1))
            elif i.op == "call":
                inicio_funcion, nombres = funciones[i.arg1]
                argumentos = apilados[len(apilados) - i.arg2 :]
                del apilados[len(apilados) - i.arg2 :]
                resultado = correr(inicio_funcion + 1, dict(zip(nombres, argumentos)))
                if i.destino is not None:
                    escribir(i.destino, resultado)
            elif i.op == "return":
                return None if i.arg1 is None else leer(i.arg1)
            elif i.op == "print":
                salida.append(_texto(leer(i.arg1)))
            # label, func y endfunc no hacen nada al ejecutarse

    correr(etiquetas["@main"], globales)
    return salida
