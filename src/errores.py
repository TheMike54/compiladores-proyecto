"""Errores compartidos por todas las fases.

Ninguna fase lanza excepciones por un error del programa fuente: lo agrega a una lista
y sigue, para poder reportar varios errores en una sola corrida.
"""

from dataclasses import dataclass

Ubicacion = tuple[int, int]


@dataclass(frozen=True)
class ErrorCompilacion:
    fase: str  # "léxico", "sintáctico", "semántico", "ejecución"
    mensaje: str
    linea: int
    columna: int

    def __str__(self) -> str:
        fase = "de ejecución" if self.fase == "ejecución" else self.fase
        return f"Error {fase} [línea {self.linea}, columna {self.columna}]: {self.mensaje}"
