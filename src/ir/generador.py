"""Generador de código intermedio: recorre el AST anotado y produce instrucciones de tres direcciones.

Cada expresión devuelve su operando (una constante, el nombre de una variable o un temporal nuevo);
cada sentencia agrega sus instrucciones a `codigo`. El formato está en docs/arquitectura.md, sección 5.
"""

from src.ast import Funcion, Programa
from src.ast.visitor import Visitor

from .instrucciones import OPERACIONES_BINARIAS, OPERACIONES_UNARIAS, Instruccion, Operando


class GeneradorIR(Visitor):
    def __init__(self) -> None:
        self.codigo: list[Instruccion] = []
        self._temporales = 0
        self._etiquetas = 0

    # --- Utilidades ----------------------------------------------------------

    def nuevo_temporal(self) -> str:
        self._temporales += 1
        return f"@t{self._temporales}"

    def nueva_etiqueta(self) -> str:
        self._etiquetas += 1
        return f"@L{self._etiquetas}"

    def emitir(self, op: str, **campos) -> None:
        self.codigo.append(Instruccion(op, **campos))

    # --- Expresiones: devuelven un operando -----------------------------------

    def visitar_Entero(self, nodo) -> Operando:
        return nodo.valor

    def visitar_Booleano(self, nodo) -> Operando:
        return nodo.valor

    def visitar_Identificador(self, nodo) -> Operando:
        return nodo.nombre_unico or nodo.nombre

    def visitar_Binaria(self, nodo) -> Operando:
        izquierda = self.visitar(nodo.izquierda)
        derecha = self.visitar(nodo.derecha)
        temporal = self.nuevo_temporal()
        self.emitir(OPERACIONES_BINARIAS[nodo.operador], destino=temporal, arg1=izquierda, arg2=derecha)
        return temporal

    def visitar_Unaria(self, nodo) -> Operando:
        operando = self.visitar(nodo.operando)
        temporal = self.nuevo_temporal()
        self.emitir(OPERACIONES_UNARIAS[nodo.operador], destino=temporal, arg1=operando)
        return temporal

    def visitar_Llamada(self, nodo) -> Operando | None:
        # Primero se evalúan todos los argumentos; así los `param` de una llamada anidada no se
        # mezclan con los de la llamada exterior.
        argumentos = [self.visitar(argumento) for argumento in nodo.argumentos]
        for argumento in argumentos:
            self.emitir("param", arg1=argumento)
        # Un procedimiento no regresa valor: su `tipo` queda en None y la llamada no lleva destino.
        destino = self.nuevo_temporal() if nodo.tipo is not None else None
        self.emitir("call", destino=destino, arg1=nodo.nombre, arg2=len(argumentos))
        return destino

    # --- Sentencias -----------------------------------------------------------

    def visitar_DeclVar(self, nodo) -> None:
        if nodo.inicial is None:
            valor: Operando = 0 if nodo.tipo_dato == "int" else False
        else:
            valor = self.visitar(nodo.inicial)
        self.emitir("copy", destino=nodo.nombre_unico or nodo.nombre, arg1=valor)

    def visitar_Asignacion(self, nodo) -> None:
        valor = self.visitar(nodo.valor)
        self.emitir("copy", destino=nodo.nombre_unico or nodo.nombre, arg1=valor)

    def visitar_Print(self, nodo) -> None:
        self.emitir("print", arg1=self.visitar(nodo.valor))

    def visitar_SentenciaExpr(self, nodo) -> None:
        self.visitar(nodo.expresion)  # el valor de la llamada, si lo hay, se descarta

    def visitar_Return(self, nodo) -> None:
        valor = None if nodo.valor is None else self.visitar(nodo.valor)
        self.emitir("return", arg1=valor)

    def visitar_Funcion(self, nodo) -> None:
        parametros = tuple(p.nombre_unico or p.nombre for p in nodo.parametros)
        self.emitir("func", arg1=nodo.nombre, params=parametros)
        self.visitar(nodo.cuerpo)
        if nodo.tipo_retorno is None:
            self.emitir("return")  # un procedimiento siempre regresa al llamador al llegar al final
        self.emitir("endfunc", arg1=nodo.nombre)

    def visitar_If(self, nodo) -> None:
        condicion = self.visitar(nodo.condicion)
        if nodo.sino is None:
            fin = self.nueva_etiqueta()
            self.emitir("if_false", arg1=condicion, etiqueta=fin)
            self.visitar(nodo.entonces)
            self.emitir("label", etiqueta=fin)
            return
        inicio_sino = self.nueva_etiqueta()
        fin = self.nueva_etiqueta()
        self.emitir("if_false", arg1=condicion, etiqueta=inicio_sino)
        self.visitar(nodo.entonces)
        self.emitir("goto", etiqueta=fin)
        self.emitir("label", etiqueta=inicio_sino)
        self.visitar(nodo.sino)  # un If aquí es un "else if" y se traduce con este mismo método
        self.emitir("label", etiqueta=fin)

    def visitar_While(self, nodo) -> None:
        inicio = self.nueva_etiqueta()
        fin = self.nueva_etiqueta()
        self.emitir("label", etiqueta=inicio)
        condicion = self.visitar(nodo.condicion)
        self.emitir("if_false", arg1=condicion, etiqueta=fin)
        self.visitar(nodo.cuerpo)
        self.emitir("goto", etiqueta=inicio)
        self.emitir("label", etiqueta=fin)


def generar(programa: Programa) -> list[Instruccion]:
    """Traduce un `Programa` ya analizado a una lista de instrucciones de tres direcciones.

    Orden del programa: primero todas las funciones; luego la etiqueta `@main` con las sentencias
    globales, y la lista termina con un `return` sin valor.
    """
    generador = GeneradorIR()
    for elemento in programa.elementos:
        if isinstance(elemento, Funcion):
            generador.visitar(elemento)
    generador.emitir("label", etiqueta="@main")
    for elemento in programa.elementos:
        if not isinstance(elemento, Funcion):
            generador.visitar(elemento)
    generador.emitir("return")
    return generador.codigo
