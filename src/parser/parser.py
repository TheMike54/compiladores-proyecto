"""Parser descendente recursivo de MiniLang. La gramática completa está en docs/gramatica.md.

Un método por no terminal. Las reglas de expresión siguen la precedencia de menor a mayor
(o, y, igualdad, relacional, suma, producto, unaria, primaria); cada nivel es un ciclo
`while` en lugar de recursión por la derecha, así los operadores binarios asocian a la
izquierda.

Recuperación de errores en modo pánico: un error sintáctico desenrolla hasta la sentencia
que se estaba analizando, se registra y se descartan tokens hasta un punto seguro (después
de `;`, antes de `}` o antes de una palabra que inicia sentencia). Así un archivo con varios
errores los reporta todos.
"""

from src.ast import (
    Asignacion,
    Binaria,
    Bloque,
    Booleano,
    DeclVar,
    Entero,
    Expresion,
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
    While,
)
from src.errores import ErrorCompilacion
from src.lexer import TipoToken as T
from src.lexer import Token

INICIO_SENTENCIA = {T.INT, T.BOOL, T.IF, T.WHILE, T.PRINT, T.RETURN, T.FUNC, T.LLAVE_IZQ}

NIVELES_BINARIOS: list[set[T]] = [
    {T.O},
    {T.Y},
    {T.IGUAL, T.DISTINTO},
    {T.MENOR, T.MENOR_IGUAL, T.MAYOR, T.MAYOR_IGUAL},
    {T.MAS, T.MENOS},
    {T.POR, T.ENTRE, T.MODULO},
]

DESCRIPCION = {
    T.PUNTO_COMA: "';'", T.PAR_IZQ: "'('", T.PAR_DER: "')'", T.LLAVE_IZQ: "'{'",
    T.LLAVE_DER: "'}'", T.ID: "un identificador", T.ASIGNAR: "'='", T.COMA: "','",
}


class _Panico(Exception):
    """Interna: corta el análisis de la sentencia actual tras registrar el error."""


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.errores: list[ErrorCompilacion] = []

    # --- nivel superior -------------------------------------------------------

    def analizar(self) -> tuple[Programa, list[ErrorCompilacion]]:
        inicio = self._actual()
        programa = Programa(linea=inicio.linea, columna=inicio.columna)
        while not self._es(T.EOF):
            elemento = self._protegido(self._elemento_global)
            if elemento is not None:
                programa.elementos.append(elemento)
        return programa, self.errores

    def _elemento_global(self) -> Nodo:
        if self._es(T.FUNC):
            return self._funcion()
        return self._sentencia()

    def _funcion(self) -> Funcion:
        inicio = self._consumir(T.FUNC)
        nombre = self._consumir(T.ID, "el nombre de la función").lexema
        self._consumir(T.PAR_IZQ)
        parametros: list[Parametro] = []
        if not self._es(T.PAR_DER):
            parametros.append(self._parametro())
            while self._acepta(T.COMA):
                parametros.append(self._parametro())
        self._consumir(T.PAR_DER)
        tipo_retorno = self._tipo() if self._acepta(T.DOS_PUNTOS) else None
        cuerpo = self._bloque()
        return Funcion(nombre, parametros, tipo_retorno, cuerpo, linea=inicio.linea, columna=inicio.columna)

    def _parametro(self) -> Parametro:
        inicio = self._actual()
        tipo = self._tipo()
        nombre = self._consumir(T.ID, "el nombre del parámetro").lexema
        return Parametro(tipo, nombre, linea=inicio.linea, columna=inicio.columna)

    def _tipo(self) -> str:
        if self._es(T.INT) or self._es(T.BOOL):
            return self._avanzar().lexema
        self._fallar("un tipo ('int' o 'bool')")

    # --- sentencias -------------------------------------------------------------

    def _sentencia(self) -> Nodo:
        t = self._actual()
        if t.tipo in (T.INT, T.BOOL):
            return self._declaracion()
        if t.tipo is T.IF:
            return self._if()
        if t.tipo is T.WHILE:
            return self._while()
        if t.tipo is T.PRINT:
            return self._print()
        if t.tipo is T.RETURN:
            return self._return()
        if t.tipo is T.LLAVE_IZQ:
            return self._bloque()
        if t.tipo is T.ID:
            return self._asignacion_o_llamada()
        if t.tipo is T.FUNC:
            self._fallar_en(t, "las funciones solo se declaran fuera de cualquier bloque")
        self._fallar("una sentencia")

    def _bloque(self) -> Bloque:
        inicio = self._consumir(T.LLAVE_IZQ)
        bloque = Bloque(linea=inicio.linea, columna=inicio.columna)
        while not self._es(T.LLAVE_DER) and not self._es(T.EOF):
            sentencia = self._protegido(self._sentencia)
            if sentencia is not None:
                bloque.sentencias.append(sentencia)
        self._consumir(T.LLAVE_DER, f"'}}' para cerrar el bloque abierto en la línea {inicio.linea}")
        return bloque

    def _declaracion(self) -> DeclVar:
        inicio = self._actual()
        tipo = self._tipo()
        nombre = self._consumir(T.ID, "el nombre de la variable").lexema
        inicial = self._expresion() if self._acepta(T.ASIGNAR) else None
        self._consumir(T.PUNTO_COMA)
        return DeclVar(tipo, nombre, inicial, linea=inicio.linea, columna=inicio.columna)

    def _asignacion_o_llamada(self) -> Nodo:
        nombre = self._actual()
        siguiente = self._ver(1)
        if siguiente.tipo is T.ASIGNAR:
            self._avanzar()
            self._avanzar()
            valor = self._expresion()
            self._consumir(T.PUNTO_COMA)
            return Asignacion(nombre.lexema, valor, linea=nombre.linea, columna=nombre.columna)
        if siguiente.tipo is T.PAR_IZQ:
            llamada = self._llamada()
            self._consumir(T.PUNTO_COMA)
            return SentenciaExpr(llamada, linea=nombre.linea, columna=nombre.columna)
        self._avanzar()
        self._fallar(f"'=' o '(' después de '{nombre.lexema}'")

    def _if(self) -> If:
        inicio = self._consumir(T.IF)
        condicion = self._condicion()
        entonces = self._bloque()
        sino = None
        if self._acepta(T.ELSE):
            sino = self._if() if self._es(T.IF) else self._bloque()
        return If(condicion, entonces, sino, linea=inicio.linea, columna=inicio.columna)

    def _while(self) -> While:
        inicio = self._consumir(T.WHILE)
        condicion = self._condicion()
        cuerpo = self._bloque()
        return While(condicion, cuerpo, linea=inicio.linea, columna=inicio.columna)

    def _condicion(self) -> Expresion:
        self._consumir(T.PAR_IZQ)
        condicion = self._expresion()
        self._consumir(T.PAR_DER)
        return condicion

    def _print(self) -> Print:
        inicio = self._consumir(T.PRINT)
        self._consumir(T.PAR_IZQ)
        valor = self._expresion()
        self._consumir(T.PAR_DER)
        self._consumir(T.PUNTO_COMA)
        return Print(valor, linea=inicio.linea, columna=inicio.columna)

    def _return(self) -> Return:
        inicio = self._consumir(T.RETURN)
        valor = None if self._es(T.PUNTO_COMA) else self._expresion()
        self._consumir(T.PUNTO_COMA)
        return Return(valor, linea=inicio.linea, columna=inicio.columna)

    # --- expresiones ------------------------------------------------------------

    def _expresion(self) -> Expresion:
        return self._binaria(0)

    def _binaria(self, nivel: int) -> Expresion:
        if nivel == len(NIVELES_BINARIOS):
            return self._unaria()
        izquierda = self._binaria(nivel + 1)
        while self._actual().tipo in NIVELES_BINARIOS[nivel]:
            operador = self._avanzar()
            derecha = self._binaria(nivel + 1)
            izquierda = Binaria(operador.lexema, izquierda, derecha, linea=operador.linea, columna=operador.columna)
        return izquierda

    def _unaria(self) -> Expresion:
        if self._es(T.MENOS) or self._es(T.NO):
            operador = self._avanzar()
            operando = self._unaria()
            return Unaria(operador.lexema, operando, linea=operador.linea, columna=operador.columna)
        return self._primaria()

    def _primaria(self) -> Expresion:
        t = self._actual()
        if t.tipo is T.LIT_ENTERO:
            self._avanzar()
            return Entero(t.valor, linea=t.linea, columna=t.columna)
        if t.tipo is T.LIT_BOOL:
            self._avanzar()
            return Booleano(t.valor, linea=t.linea, columna=t.columna)
        if t.tipo is T.ID:
            if self._ver(1).tipo is T.PAR_IZQ:
                return self._llamada()
            self._avanzar()
            return Identificador(t.lexema, linea=t.linea, columna=t.columna)
        if t.tipo is T.PAR_IZQ:
            self._avanzar()
            interior = self._expresion()
            self._consumir(T.PAR_DER)
            return interior
        self._fallar("una expresión (número, true/false, variable, llamada o '(')")

    def _llamada(self) -> Llamada:
        nombre = self._consumir(T.ID)
        self._consumir(T.PAR_IZQ)
        argumentos: list[Expresion] = []
        if not self._es(T.PAR_DER):
            argumentos.append(self._expresion())
            while self._acepta(T.COMA):
                argumentos.append(self._expresion())
        self._consumir(T.PAR_DER)
        return Llamada(nombre.lexema, argumentos, linea=nombre.linea, columna=nombre.columna)

    # --- utilidades -------------------------------------------------------------

    def _actual(self) -> Token:
        return self.tokens[self.pos]

    def _ver(self, adelante: int) -> Token:
        return self.tokens[min(self.pos + adelante, len(self.tokens) - 1)]

    def _es(self, tipo: T) -> bool:
        return self._actual().tipo is tipo

    def _avanzar(self) -> Token:
        token = self._actual()
        if token.tipo is not T.EOF:
            self.pos += 1
        return token

    def _acepta(self, tipo: T) -> bool:
        if self._es(tipo):
            self._avanzar()
            return True
        return False

    def _consumir(self, tipo: T, esperado: str | None = None) -> Token:
        if self._es(tipo):
            return self._avanzar()
        self._fallar(esperado or DESCRIPCION.get(tipo, tipo.name))

    def _fallar(self, esperado: str):
        t = self._actual()
        encontrado = "el fin del archivo" if t.tipo is T.EOF else f"'{t.lexema}'"
        self._fallar_en(t, f"se esperaba {esperado} y se encontró {encontrado}")

    def _fallar_en(self, token: Token, mensaje: str):
        self.errores.append(ErrorCompilacion("sintáctico", mensaje, token.linea, token.columna))
        raise _Panico

    def _protegido(self, regla):
        """Corre una regla de sentencia; si falla, sincroniza y regresa None."""
        inicio = self.pos
        try:
            return regla()
        except _Panico:
            self._sincronizar(inicio)
            return None

    def _sincronizar(self, inicio: int) -> None:
        # Si el error fue en el primer token, hay que descartarlo o se repetiría para siempre.
        if self.pos == inicio:
            self._avanzar()
        while not self._es(T.EOF):
            if self.tokens[self.pos - 1].tipo is T.PUNTO_COMA:
                return
            if self._actual().tipo in INICIO_SENTENCIA or self._es(T.LLAVE_DER):
                return
            self._avanzar()


def analizar(tokens: list[Token]) -> tuple[Programa, list[ErrorCompilacion]]:
    return Parser(tokens).analizar()
