"""Criterio de aceptación del IR y el optimizador, de punta a punta (fuente -> IR -> optimizado).

Para cada programa se comprueba que el IR tiene las etiquetas y saltos esperados y que el programa imprime lo mismo
antes y después de optimizar.
"""

import unittest
from pathlib import Path

from src.ast import Funcion, Llamada, Programa
from src.ast.visitor import Visitor
from src.ir import generar, listado
from src.lexer import tokenizar
from src.optimizer import optimizar
from src.parser import analizar
from tests.ir.interprete import ejecutar

EJEMPLOS = Path(__file__).resolve().parents[2] / "examples"


class _MarcarLlamadas(Visitor):
    """Hace lo que hará el semántico con las llamadas: `tipo` es el de retorno de la función, o None si es un procedimiento."""

    def __init__(self, programa: Programa) -> None:
        self.retornos = {f.nombre: f.tipo_retorno for f in programa.elementos if isinstance(f, Funcion)}

    def visitar_Llamada(self, nodo: Llamada) -> None:
        nodo.tipo = self.retornos[nodo.nombre]
        self.visitar_generico(nodo)


def compilar(fuente: str):
    """Devuelve (IR sin optimizar, IR optimizado)."""
    tokens, errores = tokenizar(fuente)
    assert not errores, errores
    programa, errores = analizar(tokens)
    assert not errores, errores
    _MarcarLlamadas(programa).visitar(programa)
    sin_optimizar = generar(programa)
    return sin_optimizar, optimizar(sin_optimizar)


PROGRAMA_DEL_CRITERIO = """
int i = 0;
int suma = 0;
int limite = 2 + 3;
while (i < limite) {
    suma = suma + i * 2;
    i = i + 1;
}
if (suma > 10) {
    print(suma);
} else {
    print(0);
}
print(4 * 5 - 6 / 2);
"""


class CriterioDeAceptacion(unittest.TestCase):
    def test_etiquetas_y_saltos_correctos(self):
        sin_optimizar, _ = compilar(PROGRAMA_DEL_CRITERIO)
        self.assertEqual(
            listado(sin_optimizar),
            "@main:\n"
            "    i = 0\n"
            "    suma = 0\n"
            "    @t1 = 2 + 3\n"
            "    limite = @t1\n"
            "@L1:\n"
            "    @t2 = i < limite\n"
            "    if_false @t2 goto @L2\n"
            "    @t3 = i * 2\n"
            "    @t4 = suma + @t3\n"
            "    suma = @t4\n"
            "    @t5 = i + 1\n"
            "    i = @t5\n"
            "    goto @L1\n"
            "@L2:\n"
            "    @t6 = suma > 10\n"
            "    if_false @t6 goto @L3\n"
            "    print suma\n"
            "    goto @L4\n"
            "@L3:\n"
            "    print 0\n"
            "@L4:\n"
            "    @t7 = 4 * 5\n"
            "    @t8 = 6 / 2\n"
            "    @t9 = @t7 - @t8\n"
            "    print @t9\n"
            "    return",
        )

    def test_la_expresion_constante_aparece_calculada_despues_de_optimizar(self):
        _, optimizado = compilar(PROGRAMA_DEL_CRITERIO)
        texto = listado(optimizado)
        self.assertIn("    limite = 5", texto)
        self.assertIn("    print 17", texto)
        self.assertNotIn("4 * 5", texto)

    def test_listado_optimizado_completo(self):
        _, optimizado = compilar(PROGRAMA_DEL_CRITERIO)
        self.assertEqual(
            listado(optimizado),
            "@main:\n"
            "    i = 0\n"
            "    suma = 0\n"
            "    limite = 5\n"
            "@L1:\n"
            "    @t2 = i < limite\n"
            "    if_false @t2 goto @L2\n"
            "    @t3 = i * 2\n"
            "    @t4 = suma + @t3\n"
            "    suma = @t4\n"
            "    @t5 = i + 1\n"
            "    i = @t5\n"
            "    goto @L1\n"
            "@L2:\n"
            "    @t6 = suma > 10\n"
            "    if_false @t6 goto @L3\n"
            "    print suma\n"
            "    goto @L4\n"
            "@L3:\n"
            "    print 0\n"
            "@L4:\n"
            "    print 17\n"
            "    return",
        )

    def test_el_optimizador_conserva_etiquetas_y_saltos(self):
        sin_optimizar, optimizado = compilar(PROGRAMA_DEL_CRITERIO)

        def saltos(instrucciones):
            return [(i.op, i.etiqueta) for i in instrucciones if i.op in ("label", "goto", "if_false")]

        self.assertEqual(saltos(optimizado), saltos(sin_optimizar))

    def test_imprime_lo_mismo_antes_y_despues(self):
        sin_optimizar, optimizado = compilar(PROGRAMA_DEL_CRITERIO)
        self.assertEqual(ejecutar(sin_optimizar), ["20", "17"])
        self.assertEqual(ejecutar(optimizado), ["20", "17"])


class EjemploOptimizacion(unittest.TestCase):
    """`examples/optimizacion.src`: el programa donde la optimización se nota."""

    def setUp(self):
        fuente = (EJEMPLOS / "optimizacion.src").read_text(encoding="utf-8")
        self.sin_optimizar, self.optimizado = compilar(fuente)

    def test_el_ejemplo_es_el_programa_del_criterio(self):
        fuente = (EJEMPLOS / "optimizacion.src").read_text(encoding="utf-8")
        self.assertEqual(fuente.strip(), PROGRAMA_DEL_CRITERIO.strip())

    def test_la_optimizacion_reduce_las_instrucciones(self):
        self.assertEqual(len(self.sin_optimizar), 27)
        self.assertEqual(len(self.optimizado), 23)

    def test_las_expresiones_constantes_quedan_calculadas(self):
        texto = listado(self.optimizado)
        self.assertIn("    limite = 5", texto)
        self.assertIn("    print 17", texto)

    def test_imprime_lo_mismo_antes_y_despues(self):
        self.assertEqual(ejecutar(self.sin_optimizar), ["20", "17"])
        self.assertEqual(ejecutar(self.optimizado), ["20", "17"])


class MismaSalidaConElOptimizador(unittest.TestCase):
    def comprobar(self, fuente: str, esperado: list[str]) -> None:
        sin_optimizar, optimizado = compilar(fuente)
        self.assertEqual(ejecutar(sin_optimizar), esperado)
        self.assertEqual(ejecutar(optimizado), esperado)

    def test_factorial(self):
        fuente = (EJEMPLOS / "factorial.src").read_text(encoding="utf-8")
        self.comprobar(fuente, ["120"])

    def test_ejemplo_completo(self):
        # Referencia calculada en Python, independiente del compilador.
        def fib(n: int) -> int:
            return n if n < 2 else fib(n - 1) + fib(n - 2)

        serie = [str(fib(i)) for i in range(11)]
        fuente = (EJEMPLOS / "completo.src").read_text(encoding="utf-8")
        self.comprobar(fuente, serie + ["55", "true", "3"])

    def test_una_funcion_puede_cambiar_una_global_y_el_optimizador_lo_respeta(self):
        self.comprobar(
            "int g = 1;\nfunc inc() { g = g + 1; }\ng = 5;\ninc();\nprint(g);",
            ["6"],
        )

    def test_reasignar_despues_de_copiar(self):
        self.comprobar("int a = 3;\nint b = a;\na = 10;\nprint(b);\nprint(a);", ["3", "10"])

    def test_copia_de_una_variable_que_cambia_despues(self):
        # `x` copia el valor de `n` y luego `n` cambia: `x` debe conservar el valor viejo.
        self.comprobar(
            "int n = 0;\nwhile (n < 3) {\n    int x = n;\n    n = n + 1;\n    print(x);\n}",
            ["0", "1", "2"],
        )

    def test_division_y_modulo_con_negativos(self):
        self.comprobar("print(-7 / 2);\nprint(-7 % 2);\nprint(7 / -2);", ["-3", "-1", "-3"])

    def test_la_division_entre_cero_sigue_siendo_error_al_ejecutar(self):
        sin_optimizar, optimizado = compilar("print(1 / 0);")
        with self.assertRaises(ZeroDivisionError):
            ejecutar(sin_optimizar)
        with self.assertRaises(ZeroDivisionError):
            ejecutar(optimizado)

    def test_variable_en_ambito_interno(self):
        self.comprobar("int x = 1;\nif (x == 1) {\n    int y = x + 1;\n    print(y);\n}\nprint(x);", ["2", "1"])


if __name__ == "__main__":
    unittest.main()
