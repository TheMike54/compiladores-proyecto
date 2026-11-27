"""Ejecuta el código objetivo de MiniLang, una instrucción por línea."""

import argparse
import operator
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from src.errores import ErrorCompilacion, Ubicacion

Valor = int | bool
_MAXIMO_DE_LLAMADAS = 1000


def _division_entera(dividendo: int, divisor: int) -> int:
    """Trunca hacia cero, incluidos los cocientes negativos."""
    cociente = abs(dividendo) // abs(divisor)
    if (dividendo < 0) != (divisor < 0):
        return -cociente
    return cociente


def _residuo(dividendo: int, divisor: int) -> int:
    return dividendo - divisor * _division_entera(dividendo, divisor)


_OPERACIONES_BINARIAS = {
    "ADD": operator.add,
    "SUB": operator.sub,
    "MUL": operator.mul,
    "DIV": _division_entera,
    "MOD": _residuo,
    "EQ": operator.eq,
    "NE": operator.ne,
    "LT": operator.lt,
    "LE": operator.le,
    "GT": operator.gt,
    "GE": operator.ge,
    "AND": operator.and_,
    "OR": operator.or_,
}
_OPERACIONES_UNARIAS = {"NEG": operator.neg, "NOT": operator.not_}


@dataclass
class _Marco:
    variables: dict[str, Valor] = field(default_factory=dict)
    pila: list[Valor] = field(default_factory=list)
    direccion_de_regreso: int = 0


def _constante(texto: str) -> Valor:
    if texto == "true":
        return True
    if texto == "false":
        return False
    return int(texto)


def _texto(valor: Valor) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return str(valor)


def _apilar_resultado(pila: list[Valor], resultado: Valor) -> None:
    if not isinstance(resultado, bool) and not -(2**31) <= resultado < 2**31:
        raise OverflowError("el resultado no cabe en un entero de 32 bits")
    pila.append(resultado)


def ejecutar(
    codigo: Iterable[str],
    mostrar: Callable[[str], None] = print,
    *,
    ubicaciones: Sequence[Ubicacion] = (),
) -> ErrorCompilacion | None:
    """Ejecuta las líneas. Devuelve el primer error, si lo hay."""
    instrucciones = [
        (indice, linea.split())
        for indice, linea in enumerate(codigo)
        if linea.strip()
    ]
    etiquetas: dict[str, int] = {}
    funciones: dict[str, tuple[int, list[str]]] = {}

    # Se registran los destinos antes de ejecutar para permitir saltos hacia adelante.
    for posicion, (_, instruccion) in enumerate(instrucciones):
        match instruccion:
            case ["LABEL", nombre]:
                etiquetas[nombre] = posicion + 1
            case ["FUNC", nombre, *parametros]:
                funciones[nombre] = (posicion + 1, parametros)

    globales: dict[str, Valor] = {}
    marcos = [_Marco(variables=globales)]
    if "@main" not in etiquetas:
        return ErrorCompilacion("ejecución", "falta LABEL @main", 0, 0)

    siguiente = etiquetas["@main"]
    instruccion = []
    indice_archivo = None
    try:
        while siguiente < len(instrucciones):
            marco = marcos[-1]
            pila = marco.pila
            indice_archivo, instruccion = instrucciones[siguiente]
            siguiente += 1

            match instruccion:
                case ["PUSH", literal]:
                    _apilar_resultado(pila, _constante(literal))

                case ["LOAD", nombre]:
                    if nombre in marco.variables:
                        pila.append(marco.variables[nombre])
                    elif nombre in globales:
                        pila.append(globales[nombre])
                    else:
                        raise ValueError(f"la variable '{nombre}' se usó antes de tener valor")

                case ["STORE", nombre]:
                    valor = pila.pop()
                    # Un parámetro o una variable local tiene prioridad sobre una global.
                    if nombre not in marco.variables and nombre in globales:
                        globales[nombre] = valor
                    else:
                        marco.variables[nombre] = valor

                case [operacion] if operacion in _OPERACIONES_BINARIAS:
                    # El operando derecho se apiló al final.
                    derecho = pila.pop()
                    izquierdo = pila.pop()
                    resultado = _OPERACIONES_BINARIAS[operacion](izquierdo, derecho)
                    _apilar_resultado(pila, resultado)

                case [operacion] if operacion in _OPERACIONES_UNARIAS:
                    resultado = _OPERACIONES_UNARIAS[operacion](pila.pop())
                    _apilar_resultado(pila, resultado)

                case ["LABEL", _]:
                    pass

                case ["JMP", destino]:
                    siguiente = etiquetas[destino]

                case ["JZ", destino]:
                    if not pila.pop():
                        siguiente = etiquetas[destino]

                case ["CALL", nombre, cantidad]:
                    inicio, parametros = funciones[nombre]
                    numero_de_argumentos = int(cantidad)
                    if numero_de_argumentos != len(parametros) or numero_de_argumentos > len(pila):
                        raise ValueError(f"cantidad de argumentos incorrecta para '{nombre}'")
                    if len(marcos) - 1 >= _MAXIMO_DE_LLAMADAS:
                        raise ValueError("desbordamiento de la pila de llamadas")

                    # Se toman los últimos argumentos conservando su orden original.
                    primer_argumento = len(pila) - numero_de_argumentos
                    argumentos = pila[primer_argumento:]
                    del pila[primer_argumento:]
                    variables = dict(zip(parametros, argumentos))
                    marcos.append(_Marco(variables=variables, direccion_de_regreso=siguiente))
                    siguiente = inicio

                case ["RET"]:
                    if len(marcos) == 1:
                        raise ValueError("RET fuera de una función")
                    marcos.pop()
                    siguiente = marco.direccion_de_regreso
                    if pila:
                        marcos[-1].pila.append(pila.pop())

                case ["PRINT"]:
                    mostrar(_texto(pila.pop()))

                case ["HALT"]:
                    return None

                case _:
                    raise ValueError(f"instrucción inválida: {' '.join(instruccion)}")

    except ZeroDivisionError:
        mensaje = "módulo entre cero" if instruccion[0] == "MOD" else "división entre cero"
    except IndexError:
        mensaje = f"faltan valores en la pila para {instruccion[0]}"
    except KeyError as error:
        mensaje = f"destino de salto o función desconocido: {error.args[0]}"
    except (ValueError, OverflowError) as error:
        mensaje = str(error)
    else:
        mensaje = "el programa terminó sin HALT"

    linea, columna = 0, 0
    if indice_archivo is not None and indice_archivo < len(ubicaciones):
        linea, columna = ubicaciones[indice_archivo]
    return ErrorCompilacion("ejecución", mensaje, linea, columna)


def ejecutar_archivo(
    archivo: Path, *, ubicaciones: Sequence[Ubicacion] = ()
) -> ErrorCompilacion | None:
    """Lee las instrucciones guardadas y las ejecuta en orden."""
    codigo = archivo.read_text(encoding="utf-8-sig")
    return ejecutar(codigo.splitlines(), ubicaciones=ubicaciones)


def main(argv: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description="Ejecuta un archivo de la máquina de pila")
    opciones.add_argument("archivo", type=Path, help="archivo de instrucciones de pila")
    args = opciones.parse_args(argv)

    try:
        error_de_ejecucion = ejecutar_archivo(args.archivo)
    except (OSError, UnicodeError) as error:
        print(f"No se pudo leer {args.archivo}: {error}", file=sys.stderr)
        return 2

    if error_de_ejecucion is not None:
        print(error_de_ejecucion, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
