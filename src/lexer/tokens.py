from dataclasses import dataclass
from enum import Enum, auto


class TipoToken(Enum):
    # Palabras reservadas
    INT = auto()
    BOOL = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    PRINT = auto()
    FUNC = auto()
    RETURN = auto()

    # Identificadores y literales
    ID = auto()
    LIT_ENTERO = auto()
    LIT_BOOL = auto()

    # Operadores
    ASIGNAR = auto()      # =
    IGUAL = auto()        # ==
    DISTINTO = auto()     # !=
    MENOR = auto()        # <
    MENOR_IGUAL = auto()  # <=
    MAYOR = auto()        # >
    MAYOR_IGUAL = auto()  # >=
    MAS = auto()          # +
    MENOS = auto()        # -
    POR = auto()          # *
    ENTRE = auto()        # /
    MODULO = auto()       # %
    Y = auto()            # &&
    O = auto()            # ||
    NO = auto()           # !

    # Delimitadores
    PAR_IZQ = auto()      # (
    PAR_DER = auto()      # )
    LLAVE_IZQ = auto()    # {
    LLAVE_DER = auto()    # }
    PUNTO_COMA = auto()   # ;
    COMA = auto()         # ,
    DOS_PUNTOS = auto()   # :

    EOF = auto()


PALABRAS_RESERVADAS = {
    "int": TipoToken.INT,
    "bool": TipoToken.BOOL,
    "if": TipoToken.IF,
    "else": TipoToken.ELSE,
    "while": TipoToken.WHILE,
    "print": TipoToken.PRINT,
    "func": TipoToken.FUNC,
    "return": TipoToken.RETURN,
}


@dataclass(frozen=True)
class Token:
    tipo: TipoToken
    lexema: str
    valor: int | bool | None
    linea: int
    columna: int

    def __str__(self) -> str:
        return f"{self.linea}:{self.columna}\t{self.tipo.name}\t{self.lexema!r}"
