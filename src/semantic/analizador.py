"""Análisis semántico: alcance de los nombres y comprobación de tipos.

Recorre el AST con el visitor. Los métodos de sentencia no regresan nada; los de expresión
regresan el tipo de la expresión ("int", "bool") o None si no se puede saber (por ejemplo,
una variable no declarada) y además lo guardan en `nodo.tipo`.

Cuando un operando ya tiene un error, su tipo es None y la expresión que lo contiene no
reporta otro error por él: así un solo error del programa produce un solo mensaje. Los
operadores siempre regresan su tipo de resultado (`+` da int, `<` da bool), aunque sus
operandos estén mal, para que el error no se propague hacia arriba.

El catálogo de errores (códigos S01 a S16) está en docs/arquitectura.md, sección 4.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ast import (
    Asignacion,
    Binaria,
    Bloque,
    Booleano,
    DeclVar,
    Entero,
    Funcion,
    Identificador,
    If,
    Llamada,
    Nodo,
    Parametro,
    Print,
    Programa,
    Return,
    SentenciaExpr,
    Unaria,
    Visitor,
    While,
    hijos,
)
from src.errores import ErrorCompilacion

from .tabla_simbolos import Simbolo, TablaSimbolos

ARITMETICOS = {"+", "-", "*", "/", "%"}
RELACIONALES = {"<", "<=", ">", ">="}
IGUALDAD = {"==", "!="}
LOGICOS = {"&&", "||"}


@dataclass(frozen=True)
class ErrorSemantico(ErrorCompilacion):
    """Un ErrorCompilacion de fase "semántico" con su código del catálogo (S01, S02, ...)."""

    codigo: str = ""


class Analizador(Visitor):
    def __init__(self) -> None:
        self.tabla = TablaSimbolos()
        self.errores: list[ErrorCompilacion] = []
        self.funcion_actual: Funcion | None = None
        self.nombres_fuente: set[str] = set()  # todo nombre declarado en el programa
        self.nombres_unicos: set[str] = set()  # los nombres únicos ya repartidos

    def analizar(self, programa: Programa) -> tuple[TablaSimbolos, list[ErrorCompilacion]]:
        self.nombres_fuente = _nombres_declarados(programa)
        # Primero se registran todas las funciones para poder llamarlas antes de su declaración.
        for elemento in programa.elementos:
            if isinstance(elemento, Funcion):
                self._registrar_funcion(elemento)
        for elemento in programa.elementos:
            self.visitar(elemento)
        self.errores.sort(key=lambda e: (e.linea, e.columna))
        return self.tabla, self.errores

    # --- utilidades ---------------------------------------------------------------

    def _error(self, codigo: str, nodo: Nodo, mensaje: str) -> None:
        self.errores.append(ErrorSemantico("semántico", mensaje, nodo.linea, nodo.columna, codigo))

    def _declarar(self, simbolo: Simbolo, nodo: Nodo) -> bool:
        previo = self.tabla.declarar(simbolo)
        if previo is not None:
            self._error("S02", nodo, f"'{simbolo.nombre}' ya está declarado en este ámbito (línea {previo.linea})")
            return False
        return True

    def _nombre_unico(self, nombre: str) -> str:
        """El nombre tal cual la primera vez; después x_1, x_2, ... sin chocar con nombres del fuente."""
        candidato = nombre
        n = 0
        while candidato in self.nombres_unicos or (n > 0 and candidato in self.nombres_fuente):
            n += 1
            candidato = f"{nombre}_{n}"
        self.nombres_unicos.add(candidato)
        return candidato

    def _declarar_variable(self, nodo: DeclVar | Parametro, categoria: str) -> None:
        simbolo = Simbolo(nodo.nombre, categoria, nodo.tipo_dato, nodo.linea, nodo.columna)
        if self._declarar(simbolo, nodo):
            simbolo.nombre_unico = self._nombre_unico(nodo.nombre)
            if simbolo.nombre_unico != nodo.nombre:
                nodo.nombre_unico = simbolo.nombre_unico

    def _registrar_funcion(self, nodo: Funcion) -> None:
        tipos = [p.tipo_dato for p in nodo.parametros]
        simbolo = Simbolo(nodo.nombre, "funcion", nodo.tipo_retorno, nodo.linea, nodo.columna, tipos)
        if self._declarar(simbolo, nodo):
            simbolo.nombre_unico = nodo.nombre
            self.nombres_unicos.add(nodo.nombre)

    def _variable(self, nombre: str, nodo: Nodo) -> Simbolo | None:
        """Busca una variable o parámetro; reporta S01 o S15 si no lo es."""
        simbolo = self.tabla.buscar(nombre)
        if simbolo is None:
            self._error("S01", nodo, f"la variable '{nombre}' no está declarada")
            return None
        if simbolo.categoria == "funcion":
            self._error("S15", nodo, f"'{nombre}' es una función, no una variable")
            return None
        return simbolo

    def _esperar(self, tipo: str | None, esperado: str, codigo: str, nodo: Nodo, mensaje: str) -> None:
        """Reporta el error si el tipo se conoce y no es el esperado (None ya se reportó antes)."""
        if tipo is not None and tipo != esperado:
            self._error(codigo, nodo, mensaje)

    # --- nivel superior -------------------------------------------------------------

    def visitar_Funcion(self, nodo: Funcion) -> None:
        # Se guarda el nodo y no el símbolo: si la función está repetida (S02), el símbolo es el de
        # la primera declaración y sus returns se revisarían contra el tipo equivocado.
        self.funcion_actual = nodo
        self.tabla.abrir(f"función {nodo.nombre}")
        for parametro in nodo.parametros:
            self._declarar_variable(parametro, "parametro")
        # El cuerpo comparte el ámbito de los parámetros: `func f(int a) { int a; }` es redeclaración.
        for sentencia in nodo.cuerpo.sentencias:
            self.visitar(sentencia)
        self.tabla.cerrar()
        if nodo.tipo_retorno is not None and not _siempre_regresa(nodo.cuerpo.sentencias):
            self._error("S13", nodo, f"la función '{nodo.nombre}' no regresa un valor en todos los caminos")
        self.funcion_actual = None

    # --- sentencias -------------------------------------------------------------------

    def visitar_Bloque(self, nodo: Bloque) -> None:
        self.tabla.abrir(f"bloque (línea {nodo.linea})")
        for sentencia in nodo.sentencias:
            self.visitar(sentencia)
        self.tabla.cerrar()

    def visitar_DeclVar(self, nodo: DeclVar) -> None:
        # El valor inicial se revisa antes de declarar: en `int x = x;` la x de la derecha
        # no puede ser la que se está declarando.
        if nodo.inicial is not None:
            tipo = self.visitar(nodo.inicial)
            self._esperar(tipo, nodo.tipo_dato, "S07", nodo.inicial,
                          f"'{nodo.nombre}' es {nodo.tipo_dato} y se inicializa con un valor {tipo}")
        self._declarar_variable(nodo, "variable")

    def visitar_Asignacion(self, nodo: Asignacion) -> None:
        tipo = self.visitar(nodo.valor)
        simbolo = self._variable(nodo.nombre, nodo)
        if simbolo is None:
            return
        if simbolo.nombre_unico != nodo.nombre:
            nodo.nombre_unico = simbolo.nombre_unico
        self._esperar(tipo, simbolo.tipo, "S06", nodo.valor,
                      f"no se puede asignar un valor {tipo} a '{nodo.nombre}', que es {simbolo.tipo}")

    def visitar_If(self, nodo: If) -> None:
        self._condicion(nodo.condicion, "if")
        self.visitar(nodo.entonces)
        if nodo.sino is not None:
            self.visitar(nodo.sino)  # un Bloque abre su ámbito; un If (else if) se revisa igual que este

    def visitar_While(self, nodo: While) -> None:
        self._condicion(nodo.condicion, "while")
        self.visitar(nodo.cuerpo)

    def _condicion(self, condicion, palabra: str) -> None:
        tipo = self.visitar(condicion)
        self._esperar(tipo, "bool", "S09", condicion, f"la condición del '{palabra}' debe ser bool y es {tipo}")

    def visitar_Print(self, nodo: Print) -> None:
        self.visitar(nodo.valor)  # int y bool se pueden imprimir; un procedimiento ya se reporta en la llamada

    def visitar_Return(self, nodo: Return) -> None:
        tipo = self.visitar(nodo.valor) if nodo.valor is not None else None
        funcion = self.funcion_actual
        if funcion is None:
            self._error("S10", nodo, "'return' fuera de una función")
            return
        esperado = funcion.tipo_retorno
        if esperado is None and nodo.valor is not None:
            self._error("S12", nodo, f"'{funcion.nombre}' es un procedimiento y no regresa ningún valor")
        elif esperado is not None and nodo.valor is None:
            self._error("S12", nodo, f"'{funcion.nombre}' debe regresar un valor {esperado}")
        elif esperado is not None:
            self._esperar(tipo, esperado, "S11", nodo.valor,
                          f"'{funcion.nombre}' debe regresar {esperado} y regresa {tipo}")

    def visitar_SentenciaExpr(self, nodo: SentenciaExpr) -> None:
        # Como sentencia se permite llamar a un procedimiento; si es función, su valor se descarta.
        self._llamada(nodo.expresion, como_valor=False)

    # --- expresiones ------------------------------------------------------------------

    def visitar_Entero(self, nodo: Entero) -> str:
        nodo.tipo = "int"
        return nodo.tipo

    def visitar_Booleano(self, nodo: Booleano) -> str:
        nodo.tipo = "bool"
        return nodo.tipo

    def visitar_Identificador(self, nodo: Identificador) -> str | None:
        simbolo = self._variable(nodo.nombre, nodo)
        if simbolo is None:
            return None
        if simbolo.nombre_unico != nodo.nombre:
            nodo.nombre_unico = simbolo.nombre_unico
        nodo.tipo = simbolo.tipo
        return nodo.tipo

    def visitar_Unaria(self, nodo: Unaria) -> str:
        tipo = self.visitar(nodo.operando)
        esperado = "int" if nodo.operador == "-" else "bool"
        self._esperar(tipo, esperado, "S08", nodo,
                      f"el operador '{nodo.operador}' necesita un operando {esperado} y recibió {tipo}")
        nodo.tipo = esperado
        return nodo.tipo

    def visitar_Binaria(self, nodo: Binaria) -> str:
        izq = self.visitar(nodo.izquierda)
        der = self.visitar(nodo.derecha)
        op = nodo.operador
        if op in IGUALDAD:
            if izq is not None and der is not None and izq != der:
                self._error("S08", nodo, f"el operador '{op}' compara dos valores del mismo tipo y recibió {izq} y {der}")
            nodo.tipo = "bool"
            return nodo.tipo
        esperado = "bool" if op in LOGICOS else "int"
        if (izq is not None and izq != esperado) or (der is not None and der != esperado):
            self._error("S08", nodo, f"el operador '{op}' necesita {esperado} y {esperado}, y recibió "
                                     f"{izq or 'un valor con error'} y {der or 'un valor con error'}")
        nodo.tipo = "int" if op in ARITMETICOS else "bool"
        return nodo.tipo

    def visitar_Llamada(self, nodo: Llamada) -> str | None:
        return self._llamada(nodo, como_valor=True)

    def _llamada(self, nodo: Llamada, como_valor: bool) -> str | None:
        tipos = [self.visitar(argumento) for argumento in nodo.argumentos]
        simbolo = self.tabla.buscar(nodo.nombre)
        if simbolo is None:
            self._error("S03", nodo, f"la función '{nodo.nombre}' no está declarada")
            return None
        if simbolo.categoria != "funcion":
            self._error("S16", nodo, f"'{nodo.nombre}' es una variable, no una función")
            return None
        esperados = simbolo.tipos_parametros
        if len(tipos) != len(esperados):
            self._error("S04", nodo, f"'{nodo.nombre}' espera {len(esperados)} argumento(s) y recibió {len(tipos)}")
        else:
            for i, (tipo, esperado, argumento) in enumerate(zip(tipos, esperados, nodo.argumentos), start=1):
                self._esperar(tipo, esperado, "S05", argumento,
                              f"el argumento {i} de '{nodo.nombre}' debe ser {esperado} y es {tipo}")
        if simbolo.tipo is None and como_valor:
            self._error("S14", nodo, f"'{nodo.nombre}' es un procedimiento: no regresa un valor que se pueda usar")
            return None
        nodo.tipo = simbolo.tipo
        return nodo.tipo


def _siempre_regresa(sentencias: list[Nodo]) -> bool:
    """True si toda ejecución de estas sentencias termina en un `return`.

    Un `if` cuenta solo si tiene `else` y las dos ramas regresan. Un `while` nunca cuenta:
    su condición puede ser falsa desde la primera vez.
    """
    return any(_regresa(s) for s in sentencias)


def _regresa(sentencia: Nodo) -> bool:
    if isinstance(sentencia, Return):
        return True
    if isinstance(sentencia, Bloque):
        return _siempre_regresa(sentencia.sentencias)
    if isinstance(sentencia, If):
        return sentencia.sino is not None and _regresa(sentencia.entonces) and _regresa(sentencia.sino)
    return False


def _nombres_declarados(programa: Programa) -> set[str]:
    nombres: set[str] = set()
    por_visitar: list[Nodo] = [programa]
    while por_visitar:
        nodo = por_visitar.pop()
        if isinstance(nodo, (DeclVar, Parametro, Funcion)):
            nombres.add(nodo.nombre)
        por_visitar.extend(hijos(nodo))
    return nombres


def analizar(programa: Programa) -> tuple[TablaSimbolos, list[ErrorCompilacion]]:
    """Analiza el programa: llena `tipo` y `nombre_unico` en el AST y regresa (tabla, errores)."""
    return Analizador().analizar(programa)
