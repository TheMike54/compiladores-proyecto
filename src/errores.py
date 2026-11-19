"""Errores compartidos por todas las fases.

Ninguna fase lanza excepciones por un error del programa fuente: lo agrega a una lista
y sigue, para poder reportar varios errores en una sola corrida.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCompilacion:
    fase: str  # "léxico", "sintáctico", "semántico", "ejecución"
    mensaje: str
    linea: int
    columna: int

    def __str__(self) -> str:
        return f"Error {self.fase} [línea {self.linea}, columna {self.columna}]: {self.mensaje}"
