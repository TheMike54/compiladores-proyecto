"""Tabla de símbolos con ámbitos anidados.

Cada ámbito (global, función o bloque) guarda sus símbolos por nombre y conoce a su padre.
Buscar un nombre empieza en el ámbito actual y sube hasta el global, así una declaración
interna oculta a una externa con el mismo nombre.

Los ámbitos cerrados no se borran: se quedan colgados de su padre para poder imprimir la
tabla completa al final del análisis.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Simbolo:
    nombre: str
    categoria: str  # "variable", "parametro" o "funcion"
    tipo: str | None  # en una función es el tipo de retorno; None = procedimiento
    linea: int
    columna: int = 0
    tipos_parametros: list[str] = field(default_factory=list)  # solo funciones
    nombre_unico: str = ""  # el nombre que usa el código intermedio (x, x_1, ...)
    ambito: Ambito | None = field(default=None, repr=False)


@dataclass
class Ambito:
    nombre: str  # "global", "función suma", "bloque (línea 7)"
    nivel: int
    padre: Ambito | None = field(default=None, repr=False)
    simbolos: dict[str, Simbolo] = field(default_factory=dict)
    hijos: list[Ambito] = field(default_factory=list, repr=False)


class TablaSimbolos:
    def __init__(self) -> None:
        self.global_ = Ambito("global", 0)
        self.actual = self.global_

    def abrir(self, nombre: str) -> Ambito:
        nuevo = Ambito(nombre, self.actual.nivel + 1, padre=self.actual)
        self.actual.hijos.append(nuevo)
        self.actual = nuevo
        return nuevo

    def cerrar(self) -> None:
        if self.actual.padre is None:
            raise RuntimeError("no se puede cerrar el ámbito global")
        self.actual = self.actual.padre

    def declarar(self, simbolo: Simbolo) -> Simbolo | None:
        """Agrega el símbolo al ámbito actual.

        Regresa None si se pudo, o el símbolo que ya existía con ese nombre en este mismo
        ámbito (redeclaración); en ese caso no se agrega nada.
        """
        previo = self.actual.simbolos.get(simbolo.nombre)
        if previo is not None:
            return previo
        simbolo.ambito = self.actual
        self.actual.simbolos[simbolo.nombre] = simbolo
        return None

    def buscar(self, nombre: str) -> Simbolo | None:
        """Busca del ámbito actual hacia el global; None si no existe en ninguno."""
        ambito = self.actual
        while ambito is not None:
            if nombre in ambito.simbolos:
                return ambito.simbolos[nombre]
            ambito = ambito.padre
        return None

    def ambitos(self) -> list[Ambito]:
        """Todos los ámbitos en orden de apertura (recorrido en preorden)."""
        resultado: list[Ambito] = []
        por_visitar = [self.global_]
        while por_visitar:
            ambito = por_visitar.pop()
            resultado.append(ambito)
            por_visitar.extend(reversed(ambito.hijos))
        return resultado

    def texto(self) -> str:
        """La tabla por ámbitos, sangrada según el nivel de anidamiento."""
        lineas: list[str] = []
        for ambito in self.ambitos():
            sangria = "    " * ambito.nivel
            lineas.append(f"{sangria}Ámbito {ambito.nombre} (nivel {ambito.nivel})")
            if not ambito.simbolos:
                lineas.append(f"{sangria}  (sin símbolos)")
                continue
            filas = [("nombre", "categoría", "tipo", "línea", "nombre único", "parámetros")]
            for s in ambito.simbolos.values():
                parametros = "(" + ", ".join(s.tipos_parametros) + ")" if s.categoria == "funcion" else ""
                tipo = s.tipo or "ninguno"
                unico = s.nombre_unico if s.categoria != "funcion" else ""
                filas.append((s.nombre, s.categoria, tipo, str(s.linea), unico, parametros))
            anchos = [max(len(fila[i]) for fila in filas) for i in range(len(filas[0]))]
            for fila in filas:
                celdas = "  ".join(celda.ljust(ancho) for celda, ancho in zip(fila, anchos))
                lineas.append(f"{sangria}  {celdas}".rstrip())
        return "\n".join(lineas)
