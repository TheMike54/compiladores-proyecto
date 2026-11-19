"""Analizador léxico: recorre el fuente carácter a carácter con máxima coincidencia."""

from src.errores import ErrorCompilacion

from .tokens import PALABRAS_RESERVADAS, TipoToken, Token

SIMPLES = {
    "+": TipoToken.MAS,
    "-": TipoToken.MENOS,
    "*": TipoToken.POR,
    "%": TipoToken.MODULO,
    "(": TipoToken.PAR_IZQ,
    ")": TipoToken.PAR_DER,
    "{": TipoToken.LLAVE_IZQ,
    "}": TipoToken.LLAVE_DER,
    ";": TipoToken.PUNTO_COMA,
    ",": TipoToken.COMA,
    ":": TipoToken.DOS_PUNTOS,
}

# Operadores de uno o dos caracteres: (primero, segundo) -> tipo con dos, tipo con uno.
DOBLES = {
    "=": ("=", TipoToken.IGUAL, TipoToken.ASIGNAR),
    "!": ("=", TipoToken.DISTINTO, TipoToken.NO),
    "<": ("=", TipoToken.MENOR_IGUAL, TipoToken.MENOR),
    ">": ("=", TipoToken.MAYOR_IGUAL, TipoToken.MAYOR),
}

ENTERO_MAXIMO = 2**31 - 1


class Lexer:
    def __init__(self, fuente: str):
        self.fuente = fuente
        self.tokens: list[Token] = []
        self.errores: list[ErrorCompilacion] = []
        self.inicio = 0
        self.actual = 0
        self.linea = 1
        self.columna = 1
        self.linea_token = 1
        self.columna_token = 1

    def analizar(self) -> tuple[list[Token], list[ErrorCompilacion]]:
        while not self._fin():
            self.inicio = self.actual
            self.linea_token = self.linea
            self.columna_token = self.columna
            self._token()
        self.tokens.append(Token(TipoToken.EOF, "", None, self.linea, self.columna))
        return self.tokens, self.errores

    def _token(self) -> None:
        c = self._avanzar()

        if c in " \t\r\n":
            return

        if c == "/":
            if self._coincide("/"):
                while self._ver() != "\n" and not self._fin():
                    self._avanzar()
            elif self._coincide("*"):
                self._comentario_bloque()
            else:
                self._agregar(TipoToken.ENTRE)
            return

        if c in DOBLES:
            segundo, con_dos, con_uno = DOBLES[c]
            self._agregar(con_dos if self._coincide(segundo) else con_uno)
            return

        # && y || no tienen versión de un carácter: uno solo es un error.
        if c in "&|":
            if self._coincide(c):
                self._agregar(TipoToken.Y if c == "&" else TipoToken.O)
            else:
                self._error(f"se esperaba '{c}{c}' y se encontró '{c}' solo")
            return

        if c in SIMPLES:
            self._agregar(SIMPLES[c])
            return

        if c.isdigit():
            self._numero()
            return

        if c.isalpha() or c == "_":
            self._identificador()
            return

        self._error(f"carácter no válido '{c}'")

    def _comentario_bloque(self) -> None:
        while not self._fin():
            if self._ver() == "*" and self._ver_siguiente() == "/":
                self._avanzar()
                self._avanzar()
                return
            self._avanzar()
        self._error("comentario de bloque sin cerrar")

    def _numero(self) -> None:
        while self._ver().isdigit():
            self._avanzar()
        # Un número pegado a letras (12abc) es un solo lexema inválido, no dos tokens.
        if self._ver().isalpha() or self._ver() == "_":
            while self._ver().isalnum() or self._ver() == "_":
                self._avanzar()
            self._error(f"identificador no puede empezar con dígito: '{self._lexema()}'")
            return
        lexema = self._lexema()
        if len(lexema) > 1 and lexema[0] == "0":
            self._error(f"entero con cero inicial: '{lexema}'")
            return
        if int(lexema) > ENTERO_MAXIMO:
            self._error(f"entero fuera de rango (máximo {ENTERO_MAXIMO}): '{lexema}'")
            return
        self._agregar(TipoToken.LIT_ENTERO, int(lexema))

    def _identificador(self) -> None:
        while self._ver().isalnum() or self._ver() == "_":
            self._avanzar()
        lexema = self._lexema()
        if lexema in ("true", "false"):
            self._agregar(TipoToken.LIT_BOOL, lexema == "true")
        else:
            self._agregar(PALABRAS_RESERVADAS.get(lexema, TipoToken.ID))

    # --- utilidades ---------------------------------------------------------

    def _fin(self) -> bool:
        return self.actual >= len(self.fuente)

    def _avanzar(self) -> str:
        c = self.fuente[self.actual]
        self.actual += 1
        if c == "\n":
            self.linea += 1
            self.columna = 1
        else:
            self.columna += 1
        return c

    def _ver(self) -> str:
        return "" if self._fin() else self.fuente[self.actual]

    def _ver_siguiente(self) -> str:
        i = self.actual + 1
        return self.fuente[i] if i < len(self.fuente) else ""

    def _coincide(self, esperado: str) -> bool:
        if self._ver() != esperado:
            return False
        self._avanzar()
        return True

    def _lexema(self) -> str:
        return self.fuente[self.inicio : self.actual]

    def _agregar(self, tipo: TipoToken, valor: int | bool | None = None) -> None:
        self.tokens.append(Token(tipo, self._lexema(), valor, self.linea_token, self.columna_token))

    def _error(self, mensaje: str) -> None:
        self.errores.append(ErrorCompilacion("léxico", mensaje, self.linea_token, self.columna_token))


def tokenizar(fuente: str) -> tuple[list[Token], list[ErrorCompilacion]]:
    return Lexer(fuente).analizar()
