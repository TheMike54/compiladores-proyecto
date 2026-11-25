"""Pruebas del optimizador: se arman listas de instrucciones y se compara el listado antes y después."""

import unittest

from src.ir import Instruccion, listado
from src.optimizer import optimizar
from src.optimizer.optimizador import propagar_y_plegar, quitar_temporales_muertos


def copia(destino, valor) -> Instruccion:
    return Instruccion("copy", destino=destino, arg1=valor)


def binaria(op, destino, a, b) -> Instruccion:
    return Instruccion(op, destino=destino, arg1=a, arg2=b)


def optimizado(*instrucciones: Instruccion) -> str:
    """Solo la primera pasada (plegado y propagación), para ver sus efectos sin que se borren los temporales."""
    return listado(propagar_y_plegar(list(instrucciones)))


def sin_muertos(*instrucciones: Instruccion) -> str:
    """Solo la segunda pasada (eliminación de temporales que nadie lee)."""
    return listado(quitar_temporales_muertos(list(instrucciones)))


class PruebasPlegado(unittest.TestCase):
    def test_suma_constante(self):
        self.assertEqual(optimizado(binaria("add", "@t1", 2, 3)), "    @t1 = 5")

    def test_comparacion_y_logica(self):
        self.assertEqual(optimizado(binaria("lt", "@t1", 2, 3)), "    @t1 = true")
        self.assertEqual(optimizado(binaria("and", "@t1", True, False)), "    @t1 = false")
        self.assertEqual(optimizado(Instruccion("not", destino="@t1", arg1=True)), "    @t1 = false")
        self.assertEqual(optimizado(Instruccion("neg", destino="@t1", arg1=4)), "    @t1 = -4")

    def test_division_y_modulo_truncan_hacia_cero(self):
        self.assertEqual(optimizado(binaria("div", "@t1", -7, 2)), "    @t1 = -3")
        self.assertEqual(optimizado(binaria("mod", "@t1", -7, 2)), "    @t1 = -1")
        self.assertEqual(optimizado(binaria("div", "@t1", 7, -2)), "    @t1 = -3")
        self.assertEqual(optimizado(binaria("mod", "@t1", 7, -2)), "    @t1 = 1")

    def test_no_pliega_division_entre_cero(self):
        self.assertEqual(optimizado(binaria("div", "@t1", 1, 0)), "    @t1 = 1 / 0")
        self.assertEqual(optimizado(binaria("mod", "@t1", 1, 0)), "    @t1 = 1 % 0")

    def test_no_pliega_si_se_sale_de_32_bits(self):
        self.assertEqual(optimizado(binaria("mul", "@t1", 65536, 65536)), "    @t1 = 65536 * 65536")
        self.assertEqual(optimizado(binaria("mul", "@t1", 46340, 46340)), "    @t1 = 2147395600")


class PruebasPropagacion(unittest.TestCase):
    def test_cadena_de_constantes(self):
        # a = 2 + 3; b = a * 2; print b
        self.assertEqual(
            optimizado(
                binaria("add", "@t1", 2, 3), copia("a", "@t1"),
                binaria("mul", "@t2", "a", 2), copia("b", "@t2"),
                Instruccion("print", arg1="b"),
            ),
            "    @t1 = 5\n    a = 5\n    @t2 = 10\n    b = 10\n    print 10",
        )

    def test_copia_de_variable(self):
        # y = x; print y  ->  print x
        self.assertEqual(
            optimizado(copia("y", "x"), Instruccion("print", arg1="y")),
            "    y = x\n    print x",
        )

    def test_reasignar_la_variable_original_invalida_las_copias(self):
        # y = x; x = 7; print y  ->  y ya no es igual a x
        self.assertEqual(
            optimizado(copia("y", "x"), copia("x", 7), Instruccion("print", arg1="y")),
            "    y = x\n    x = 7\n    print y",
        )

    def test_reasignar_la_copia_invalida_su_valor(self):
        self.assertEqual(
            optimizado(copia("x", 1), copia("x", "z"), Instruccion("print", arg1="x")),
            "    x = 1\n    x = z\n    print z",
        )

    def test_copia_a_si_misma_se_elimina(self):
        self.assertEqual(
            optimizado(copia("@t1", "x"), copia("x", "@t1"), Instruccion("print", arg1="x")),
            "    @t1 = x\n    print x",
        )

    def test_una_etiqueta_olvida_lo_aprendido(self):
        # x = 1; @L1: print x   (a @L1 puede llegarse desde otro lado con otro valor de x)
        self.assertEqual(
            optimizado(copia("x", 1), Instruccion("label", etiqueta="@L1"), Instruccion("print", arg1="x")),
            "    x = 1\n@L1:\n    print x",
        )

    def test_un_salto_olvida_lo_aprendido(self):
        self.assertEqual(
            optimizado(
                copia("x", 1), Instruccion("goto", etiqueta="@L1"), Instruccion("print", arg1="x"),
            ),
            "    x = 1\n    goto @L1\n    print x",
        )

    def test_una_llamada_olvida_lo_aprendido_porque_puede_cambiar_globales(self):
        self.assertEqual(
            optimizado(
                copia("g", 5), Instruccion("call", arg1="f", arg2=0), Instruccion("print", arg1="g"),
            ),
            "    g = 5\n    call f, 0\n    print g",
        )

    def test_no_sustituye_el_nombre_de_la_funcion_ni_el_numero_de_argumentos(self):
        self.assertEqual(
            optimizado(copia("f", 1), copia("n", 2), Instruccion("call", destino="@t1", arg1="f", arg2=2)),
            "    f = 1\n    n = 2\n    @t1 = call f, 2",
        )

    def test_sustituye_en_condicion_param_y_return(self):
        self.assertEqual(
            optimizado(
                copia("c", False), Instruccion("if_false", arg1="c", etiqueta="@L1"),
                copia("v", 3), Instruccion("param", arg1="v"), Instruccion("return", arg1="v"),
            ),
            "    c = false\n    if_false false goto @L1\n    v = 3\n    param 3\n    return 3",
        )

    def test_no_modifica_la_lista_de_entrada(self):
        entrada = [copia("a", 2), binaria("add", "@t1", "a", 3)]
        antes = listado(entrada)
        optimizar(entrada)
        self.assertEqual(listado(entrada), antes)


class PruebasTemporalesMuertos(unittest.TestCase):
    def test_borra_el_temporal_que_nadie_lee(self):
        self.assertEqual(sin_muertos(binaria("add", "@t1", 2, 3), Instruccion("print", arg1=1)), "    print 1")

    def test_conserva_el_temporal_que_se_lee(self):
        entrada = (binaria("add", "@t1", "a", "b"), Instruccion("print", arg1="@t1"))
        self.assertEqual(sin_muertos(*entrada), listado(list(entrada)))

    def test_borrar_uno_deja_sin_uso_al_anterior(self):
        # @t1 solo lo lee @t2, y @t2 no lo lee nadie: mueren los dos
        self.assertEqual(sin_muertos(copia("@t1", "x"), binaria("add", "@t2", "@t1", 1)), "")

    def test_no_borra_variables_del_programa(self):
        self.assertEqual(sin_muertos(copia("x", 5)), "    x = 5")

    def test_no_borra_una_division_que_puede_fallar(self):
        for divisor in (0, "b"):
            with self.subTest(divisor=divisor):
                self.assertEqual(sin_muertos(binaria("div", "@t1", "a", divisor)), f"    @t1 = a / {divisor}")
                self.assertEqual(sin_muertos(binaria("mod", "@t1", "a", divisor)), f"    @t1 = a % {divisor}")

    def test_borra_una_division_entre_constante_distinta_de_cero(self):
        self.assertEqual(sin_muertos(binaria("div", "@t1", "a", 2)), "")

    def test_no_borra_una_llamada_aunque_no_se_use_su_resultado(self):
        self.assertEqual(
            sin_muertos(Instruccion("call", destino="@t1", arg1="f", arg2=0)), "    @t1 = call f, 0"
        )

    def test_un_uso_en_otro_bloque_cuenta(self):
        entrada = (binaria("add", "@t1", "a", "b"), Instruccion("label", etiqueta="@L1"), Instruccion("print", arg1="@t1"))
        self.assertEqual(sin_muertos(*entrada), listado(list(entrada)))

    def test_optimizar_encadena_las_dos_pasadas(self):
        # a = 2 + 3; print a  ->  a = 5; print 5   (sin el temporal)
        self.assertEqual(
            listado(optimizar([binaria("add", "@t1", 2, 3), copia("a", "@t1"), Instruccion("print", arg1="a")])),
            "    a = 5\n    print 5",
        )

    def test_no_modifica_la_lista_de_entrada(self):
        entrada = [binaria("add", "@t1", 2, 3), Instruccion("print", arg1=1)]
        antes = listado(entrada)
        optimizar(entrada)
        self.assertEqual(listado(entrada), antes)


if __name__ == "__main__":
    unittest.main()
