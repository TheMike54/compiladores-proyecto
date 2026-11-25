import unittest
from pathlib import Path

from src.ast import (
    Asignacion,
    Binaria,
    Bloque,
    DeclVar,
    Entero,
    Funcion,
    Identificador,
    If,
    Llamada,
    Print,
    Return,
    SentenciaExpr,
    Unaria,
    While,
)
from src.lexer import tokenizar
from src.parser import analizar

EJEMPLOS = Path(__file__).resolve().parents[2] / "examples"


def parsear(fuente: str):
    tokens, errores = tokenizar(fuente)
    assert not errores, errores
    return analizar(tokens)


def sin_errores(fuente: str):
    programa, errores = parsear(fuente)
    assert not errores, [str(e) for e in errores]
    return programa


def expresion(texto: str):
    return sin_errores(f"print({texto});").elementos[0].valor


def prefijo(nodo) -> str:
    """Forma prefija para comparar la estructura sin depender de las posiciones."""
    match nodo:
        case Binaria():
            return f"({nodo.operador} {prefijo(nodo.izquierda)} {prefijo(nodo.derecha)})"
        case Unaria():
            return f"({nodo.operador} {prefijo(nodo.operando)})"
        case Entero():
            return str(nodo.valor)
        case Identificador():
            return nodo.nombre
        case Llamada():
            return f"{nodo.nombre}({' '.join(prefijo(a) for a in nodo.argumentos)})"
    return type(nodo).__name__


class Precedencia(unittest.TestCase):
    def test_producto_antes_que_suma(self):
        self.assertEqual(prefijo(expresion("1 + 2 * 3")), "(+ 1 (* 2 3))")

    def test_asociatividad_izquierda(self):
        self.assertEqual(prefijo(expresion("10 - 3 - 4")), "(- (- 10 3) 4)")
        self.assertEqual(prefijo(expresion("8 / 4 / 2")), "(/ (/ 8 4) 2)")

    def test_parentesis_cambian_el_arbol(self):
        self.assertEqual(prefijo(expresion("(1 + 2) * 3")), "(* (+ 1 2) 3)")

    def test_logicos_relacionales_y_aritmeticos(self):
        self.assertEqual(
            prefijo(expresion("a + 1 < b || c == d && e")),
            "(|| (< (+ a 1) b) (&& (== c d) e))",
        )

    def test_unarios(self):
        self.assertEqual(prefijo(expresion("-a * !b")), "(* (- a) (! b))")
        self.assertEqual(prefijo(expresion("--a")), "(- (- a))")

    def test_llamada_en_expresion(self):
        self.assertEqual(prefijo(expresion("f(1, g(x)) + 2")), "(+ f(1 g(x)) 2)")


class Sentencias(unittest.TestCase):
    def test_declaraciones_y_asignacion(self):
        a, b, c = sin_errores("int a; bool b = true; a = 3;").elementos
        self.assertIsInstance(a, DeclVar)
        self.assertIsNone(a.inicial)
        self.assertEqual((b.tipo_dato, b.nombre), ("bool", "b"))
        self.assertIsInstance(c, Asignacion)

    def test_if_else_if_else(self):
        (nodo,) = sin_errores("if (a) { print(1); } else if (b) { print(2); } else { print(3); }").elementos
        self.assertIsInstance(nodo, If)
        self.assertIsInstance(nodo.sino, If)
        self.assertIsInstance(nodo.sino.sino, Bloque)

    def test_while_y_bloque_anidado(self):
        (nodo,) = sin_errores("while (i < 3) { { i = i + 1; } }").elementos
        self.assertIsInstance(nodo, While)
        self.assertIsInstance(nodo.cuerpo.sentencias[0], Bloque)

    def test_funcion_con_parametros_y_retorno(self):
        (f,) = sin_errores("func suma(int a, int b): int { return a + b; }").elementos
        self.assertIsInstance(f, Funcion)
        self.assertEqual([(p.tipo_dato, p.nombre) for p in f.parametros], [("int", "a"), ("int", "b")])
        self.assertEqual(f.tipo_retorno, "int")
        self.assertIsInstance(f.cuerpo.sentencias[0], Return)

    def test_procedimiento_y_llamada_como_sentencia(self):
        f, llamada = sin_errores("func hola() { print(1); return; } hola();").elementos
        self.assertIsNone(f.tipo_retorno)
        self.assertIsNone(f.cuerpo.sentencias[1].valor)
        self.assertIsInstance(llamada, SentenciaExpr)

    def test_posiciones(self):
        (nodo,) = sin_errores("\n   print(1);").elementos
        self.assertIsInstance(nodo, Print)
        self.assertEqual((nodo.linea, nodo.columna), (2, 4))

    def test_ejemplos_validos(self):
        for nombre in ("factorial.src", "completo.src"):
            with self.subTest(nombre):
                sin_errores((EJEMPLOS / nombre).read_text(encoding="utf-8"))


class Errores(unittest.TestCase):
    def errores(self, fuente: str):
        return parsear(fuente)[1]

    def test_falta_punto_y_coma_con_posicion(self):
        (error,) = self.errores("int a = 3\nint b;")
        self.assertEqual((error.fase, error.linea, error.columna), ("sintáctico", 2, 1))
        self.assertIn("';'", error.mensaje)

    def test_bloque_sin_cerrar(self):
        (error,) = self.errores("while (a) { print(1);")
        self.assertIn("'}'", error.mensaje)
        self.assertIn("fin del archivo", error.mensaje)

    def test_funcion_dentro_de_bloque(self):
        self.assertIn("fuera de cualquier bloque", self.errores("{ func f() { } }")[0].mensaje)

    def test_sentencia_que_no_empieza_bien(self):
        self.assertIn("una sentencia", self.errores("3 + 4;")[0].mensaje)

    def test_identificador_suelto(self):
        self.assertIn("'=' o '('", self.errores("a;")[0].mensaje)

    def test_reporta_varios_errores_y_recupera(self):
        archivo = (EJEMPLOS / "error_sintactico.src").read_text(encoding="utf-8")
        programa, errores = parsear(archivo)
        self.assertEqual([e.linea for e in errores], [3, 4, 7])
        # Después de los errores, las sentencias válidas siguen en el árbol.
        self.assertTrue(any(isinstance(e, DeclVar) and e.nombre == "b" for e in programa.elementos))

    def test_llave_suelta_no_cicla(self):
        self.assertEqual(len(self.errores("} } print(1);")), 2)


if __name__ == "__main__":
    unittest.main()
