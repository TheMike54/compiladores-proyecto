import unittest

from src.lexer import TipoToken as T
from src.lexer import tokenizar


def tipos(fuente: str) -> list[T]:
    tokens, errores = tokenizar(fuente)
    assert not errores, errores
    return [t.tipo for t in tokens]


class CasosValidos(unittest.TestCase):
    def test_palabras_reservadas_e_identificadores(self):
        self.assertEqual(
            tipos("int bool if else while print func return x _y z9"),
            [T.INT, T.BOOL, T.IF, T.ELSE, T.WHILE, T.PRINT, T.FUNC, T.RETURN, T.ID, T.ID, T.ID, T.EOF],
        )

    def test_literales(self):
        tokens, _ = tokenizar("0 42 true false")
        self.assertEqual([t.valor for t in tokens[:-1]], [0, 42, True, False])
        self.assertEqual(tokens[2].tipo, T.LIT_BOOL)

    def test_operadores_de_dos_caracteres_por_maxima_coincidencia(self):
        self.assertEqual(
            tipos("== != <= >= && || = ! < >"),
            [T.IGUAL, T.DISTINTO, T.MENOR_IGUAL, T.MAYOR_IGUAL, T.Y, T.O,
             T.ASIGNAR, T.NO, T.MENOR, T.MAYOR, T.EOF],
        )

    def test_comentarios_y_espacios_se_ignoran(self):
        self.assertEqual(tipos("a // linea\n/* bloque\n varias */ b"), [T.ID, T.ID, T.EOF])

    def test_posicion_linea_y_columna(self):
        tokens, _ = tokenizar("int a;\n  a = 1;")
        segundo_a = tokens[3]
        self.assertEqual((segundo_a.lexema, segundo_a.linea, segundo_a.columna), ("a", 2, 3))

    def test_palabra_reservada_como_prefijo_es_identificador(self):
        self.assertEqual(tipos("integer iff"), [T.ID, T.ID, T.EOF])


class CasosInvalidos(unittest.TestCase):
    def errores(self, fuente: str):
        return tokenizar(fuente)[1]

    def test_caracter_no_valido_con_posicion(self):
        (error,) = self.errores("int a = 3 @ 4;")
        self.assertEqual((error.fase, error.linea, error.columna), ("léxico", 1, 11))

    def test_ampersand_solo(self):
        self.assertIn("'&&'", self.errores("a & b")[0].mensaje)

    def test_cero_inicial(self):
        self.assertIn("cero inicial", self.errores("007")[0].mensaje)

    def test_numero_pegado_a_letras(self):
        self.assertIn("dígito", self.errores("12abc")[0].mensaje)

    def test_comentario_sin_cerrar(self):
        self.assertIn("sin cerrar", self.errores("a /* nunca")[0].mensaje)

    def test_entero_fuera_de_rango(self):
        self.assertIn("rango", self.errores("2147483648")[0].mensaje)

    def test_varios_errores_en_una_corrida(self):
        self.assertEqual(len(self.errores("@ $ #")), 3)

    def test_continua_despues_del_error(self):
        tokens, errores = tokenizar("a @ b")
        self.assertEqual(len(errores), 1)
        self.assertEqual([t.lexema for t in tokens[:-1]], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
