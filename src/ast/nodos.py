"""Nodos del AST.

Contrato con las demás fases (ver docs/arquitectura.md):
- Todo nodo trae `linea` y `columna` del token donde empieza, para los mensajes de error.
- Toda expresión trae `tipo`, que el parser deja en None y el análisis semántico llena con
  "int" o "bool". Las fases siguientes pueden confiar en él si el semántico no reportó errores.
- Identificador, DeclVar, Asignacion y Parametro traen `nombre_unico`, que llena el semántico para
  distinguir variables con el mismo nombre en ámbitos distintos (x, x_1). None = usar `nombre`.
- Los paréntesis no tienen nodo: su efecto queda en la forma del árbol.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class Nodo:
    linea: int = 0
    columna: int = 0


# --- Expresiones -------------------------------------------------------------


@dataclass(kw_only=True)
class Expresion(Nodo):
    tipo: str | None = None


@dataclass
class Entero(Expresion):
    valor: int


@dataclass
class Booleano(Expresion):
    valor: bool


@dataclass
class Identificador(Expresion):
    nombre: str
    nombre_unico: str | None = field(default=None, kw_only=True)


@dataclass
class Binaria(Expresion):
    operador: str  # + - * / % == != < <= > >= && ||
    izquierda: Expresion
    derecha: Expresion


@dataclass
class Unaria(Expresion):
    operador: str  # - !
    operando: Expresion


@dataclass
class Llamada(Expresion):
    nombre: str
    argumentos: list[Expresion] = field(default_factory=list)


# --- Sentencias --------------------------------------------------------------


@dataclass
class Bloque(Nodo):
    sentencias: list[Nodo] = field(default_factory=list)


@dataclass
class DeclVar(Nodo):
    tipo_dato: str  # "int" | "bool"
    nombre: str
    inicial: Expresion | None = None
    nombre_unico: str | None = field(default=None, kw_only=True)


@dataclass
class Asignacion(Nodo):
    nombre: str
    valor: Expresion
    nombre_unico: str | None = field(default=None, kw_only=True)


@dataclass
class If(Nodo):
    condicion: Expresion
    entonces: Bloque
    sino: Bloque | If | None = None  # un If aquí es un "else if"


@dataclass
class While(Nodo):
    condicion: Expresion
    cuerpo: Bloque


@dataclass
class Print(Nodo):
    valor: Expresion


@dataclass
class Return(Nodo):
    valor: Expresion | None = None


@dataclass
class SentenciaExpr(Nodo):
    """Una llamada usada como sentencia: `saludar(3);`."""

    expresion: Llamada


# --- Nivel superior ----------------------------------------------------------


@dataclass
class Parametro(Nodo):
    tipo_dato: str
    nombre: str
    nombre_unico: str | None = field(default=None, kw_only=True)


@dataclass
class Funcion(Nodo):
    nombre: str
    parametros: list[Parametro]
    tipo_retorno: str | None  # None = procedimiento, no regresa valor
    cuerpo: Bloque


@dataclass
class Programa(Nodo):
    """Funciones y sentencias globales, en el orden del fuente.

    Las sentencias globales forman el programa principal y se ejecutan en orden.
    """

    elementos: list[Nodo] = field(default_factory=list)
