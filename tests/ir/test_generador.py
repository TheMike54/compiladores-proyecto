"""Pruebas del generador de IR con ASTs armados a mano (no dependen del parser ni del semántico)."""

import unittest

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
    Parametro,
    Print,
    Programa,
    Return,
    SentenciaExpr,
    Unaria,
    While,
)
from src.ir import generar, listado


def ident(nombre: str, nombre_unico: str | None = None) -> Identificador:
    return Identificador(nombre, nombre_unico=nombre_unico, tipo="int")


def entero(valor: int) -> Entero:
    return Entero(valor, tipo="int")


def ir_de(*sentencias) -> str:
    return listado(generar(Programa(list(sentencias))))


class PruebasExpresiones(unittest.TestCase):
    def test_asignacion_con_expresion_anidada(self):
        # x = (a + b) * 2
        valor = Binaria("*", Binaria("+", ident("a"), ident("b"), tipo="int"), entero(2), tipo="int")
        self.assertEqual(
            ir_de(Asignacion("x", valor)),
            "@main:\n    @t1 = a + b\n    @t2 = @t1 * 2\n    x = @t2\n    return",
        )

    def test_comparacion_y_logica(self):
        # b = !(a < 3) && true
        menor = Binaria("<", ident("a"), entero(3), tipo="bool")
        valor = Binaria("&&", Unaria("!", menor, tipo="bool"), Booleano(True, tipo="bool"), tipo="bool")
        self.assertEqual(
            ir_de(Asignacion("b", valor)),
            "@main:\n    @t1 = a < 3\n    @t2 = !@t1\n    @t3 = @t2 && true\n    b = @t3\n    return",
        )

    def test_negacion_unaria(self):
        self.assertEqual(
            ir_de(Asignacion("x", Unaria("-", ident("y"), tipo="int"))),
            "@main:\n    @t1 = -y\n    x = @t1\n    return",
        )


class PruebasSentencias(unittest.TestCase):
    def test_declaracion_con_valor(self):
        self.assertEqual(ir_de(DeclVar("int", "n", entero(5))), "@main:\n    n = 5\n    return")

    def test_declaracion_sin_valor_usa_el_valor_inicial_del_tipo(self):
        self.assertEqual(
            ir_de(DeclVar("int", "x"), DeclVar("bool", "b")),
            "@main:\n    x = 0\n    b = false\n    return",
        )

    def test_print(self):
        self.assertEqual(
            ir_de(Print(Binaria("+", ident("a"), entero(1), tipo="int"))),
            "@main:\n    @t1 = a + 1\n    print @t1\n    return",
        )

    def test_usa_nombre_unico_si_existe(self):
        self.assertEqual(
            ir_de(DeclVar("int", "x", entero(1), nombre_unico="x_1"), Print(ident("x", "x_1"))),
            "@main:\n    x_1 = 1\n    print x_1\n    return",
        )

    def test_nombres_del_programa_no_chocan_con_los_internos(self):
        # Una variable llamada t1 o main conserva su nombre; los temporales llevan @.
        self.assertEqual(
            ir_de(Asignacion("t1", Binaria("+", ident("t1"), ident("main"), tipo="int"))),
            "@main:\n    @t1 = t1 + main\n    t1 = @t1\n    return",
        )


def bloque(*sentencias) -> Bloque:
    return Bloque(list(sentencias))


def menor(izquierda: str, derecha: int) -> Binaria:
    return Binaria("<", ident(izquierda), entero(derecha), tipo="bool")


def incremento(nombre: str) -> Asignacion:
    return Asignacion(nombre, Binaria("+", ident(nombre), entero(1), tipo="int"))


class PruebasControl(unittest.TestCase):
    def test_while(self):
        # while (i < 3) { i = i + 1; }
        self.assertEqual(
            ir_de(While(menor("i", 3), bloque(incremento("i")))),
            "@main:\n@L1:\n    @t1 = i < 3\n    if_false @t1 goto @L2\n"
            "    @t2 = i + 1\n    i = @t2\n    goto @L1\n@L2:\n    return",
        )

    def test_if_sin_else(self):
        self.assertEqual(
            ir_de(If(menor("a", 5), bloque(Print(ident("a"))))),
            "@main:\n    @t1 = a < 5\n    if_false @t1 goto @L1\n    print a\n@L1:\n    return",
        )

    def test_if_con_else(self):
        self.assertEqual(
            ir_de(If(menor("a", 5), bloque(Print(entero(1))), bloque(Print(entero(2))))),
            "@main:\n    @t1 = a < 5\n    if_false @t1 goto @L1\n    print 1\n    goto @L2\n"
            "@L1:\n    print 2\n@L2:\n    return",
        )

    def test_else_if_se_anida(self):
        # if (a < 1) print 1; else if (a < 2) print 2; else print 3;
        sino = If(menor("a", 2), bloque(Print(entero(2))), bloque(Print(entero(3))))
        self.assertEqual(
            ir_de(If(menor("a", 1), bloque(Print(entero(1))), sino)),
            "@main:\n    @t1 = a < 1\n    if_false @t1 goto @L1\n    print 1\n    goto @L2\n"
            "@L1:\n    @t2 = a < 2\n    if_false @t2 goto @L3\n    print 2\n    goto @L4\n"
            "@L3:\n    print 3\n@L4:\n@L2:\n    return",
        )

    def test_while_con_if_dentro(self):
        # while (i < 3) { if (i < 1) print i; i = i + 1; }
        cuerpo = bloque(If(menor("i", 1), bloque(Print(ident("i")))), incremento("i"))
        self.assertEqual(
            ir_de(While(menor("i", 3), cuerpo)),
            "@main:\n@L1:\n    @t1 = i < 3\n    if_false @t1 goto @L2\n"
            "    @t2 = i < 1\n    if_false @t2 goto @L3\n    print i\n@L3:\n"
            "    @t3 = i + 1\n    i = @t3\n    goto @L1\n@L2:\n    return",
        )


def llamada(nombre: str, *argumentos, tipo: str | None = "int") -> Llamada:
    return Llamada(nombre, list(argumentos), tipo=tipo)


def suma() -> Funcion:
    # int suma(int a, int b) { return a + b; }
    cuerpo = bloque(Return(Binaria("+", ident("a"), ident("b"), tipo="int")))
    return Funcion("suma", [Parametro("int", "a"), Parametro("int", "b")], "int", cuerpo)


class PruebasFunciones(unittest.TestCase):
    def test_funcion_y_llamada_como_expresion(self):
        self.assertEqual(
            ir_de(suma(), Print(llamada("suma", entero(1), entero(2)))),
            "func suma(a, b)\n    @t1 = a + b\n    return @t1\nendfunc suma\n"
            "@main:\n    param 1\n    param 2\n    @t2 = call suma, 2\n    print @t2\n    return",
        )

    def test_las_funciones_van_antes_de_main_aunque_se_declaren_despues(self):
        self.assertEqual(
            ir_de(Print(llamada("suma", entero(1), entero(2))), suma()).split("\n")[0],
            "func suma(a, b)",
        )

    def test_argumentos_se_evaluan_antes_de_los_param(self):
        # suma(1, suma(2, 3)): los param de la llamada interna no se mezclan con los de la externa
        interna = llamada("suma", entero(2), entero(3))
        self.assertEqual(
            ir_de(Print(llamada("suma", entero(1), interna))).split("@main:\n")[1],
            "    param 2\n    param 3\n    @t1 = call suma, 2\n    param 1\n    param @t1\n"
            "    @t2 = call suma, 2\n    print @t2\n    return",
        )

    def test_procedimiento_sin_destino_y_con_return_final(self):
        # void saludar() { print(1); }   saludar();
        saludar = Funcion("saludar", [], None, bloque(Print(entero(1))))
        self.assertEqual(
            ir_de(saludar, SentenciaExpr(llamada("saludar", tipo=None))),
            "func saludar()\n    print 1\n    return\nendfunc saludar\n"
            "@main:\n    call saludar, 0\n    return",
        )

    def test_llamada_con_valor_usada_como_sentencia_descarta_el_resultado(self):
        self.assertEqual(
            ir_de(suma(), SentenciaExpr(llamada("suma", entero(1), entero(2)))).split("@main:\n")[1],
            "    param 1\n    param 2\n    @t2 = call suma, 2\n    return",
        )

    def test_return_sin_valor(self):
        f = Funcion("f", [], None, bloque(If(menor("a", 1), bloque(Return()))))
        self.assertIn("    return\n@L1:", ir_de(f))

    def test_parametros_con_nombre_unico(self):
        f = Funcion("f", [Parametro("int", "x", nombre_unico="x_1")], "int", bloque(Return(ident("x", "x_1"))))
        self.assertEqual(ir_de(f).split("\n")[0], "func f(x_1)")


if __name__ == "__main__":
    unittest.main()
