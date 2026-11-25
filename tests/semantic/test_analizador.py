import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from src.ast import Expresion, Visitor
from src.lexer import tokenizar
from src.parser import analizar as analizar_sintaxis
from src.semantic import analizar
from src.semantic.__main__ import main

EJEMPLOS = Path(__file__).resolve().parents[2] / "examples"


def semantico(fuente: str):
    tokens, errores = tokenizar(fuente)
    assert not errores, errores
    programa, errores = analizar_sintaxis(tokens)
    assert not errores, [str(e) for e in errores]
    tabla, errores = analizar(programa)
    return programa, tabla, errores


def codigos(fuente: str) -> list[str]:
    return [e.codigo for e in semantico(fuente)[2]]


class CasoSemantico(unittest.TestCase):
    def valido(self, fuente: str):
        programa, tabla, errores = semantico(fuente)
        self.assertEqual([str(e) for e in errores], [])
        return programa, tabla

    def invalido(self, fuente: str, codigo: str, linea: int | None = None):
        errores = semantico(fuente)[2]
        self.assertEqual([e.codigo for e in errores], [codigo], [str(e) for e in errores])
        self.assertEqual(errores[0].fase, "semántico")
        if linea is not None:
            self.assertEqual(errores[0].linea, linea)
        return errores[0]


class TestAlcance(CasoSemantico):
    def test_s01_variable_declarada(self):
        self.valido("int x = 1; print(x);")

    def test_s01_variable_no_declarada(self):
        error = self.invalido("int x = 1;\nprint(y);", "S01", linea=2)
        self.assertEqual(error.columna, 7)
        self.assertIn("'y'", error.mensaje)

    def test_s01_variable_de_un_bloque_cerrado(self):
        self.invalido("{ int x = 1; }\nprint(x);", "S01", linea=2)

    def test_s01_variable_usada_en_su_propio_valor_inicial(self):
        self.invalido("int x = x + 1;", "S01")

    def test_s01_variable_global_declarada_despues_de_la_funcion(self):
        self.invalido("func f(): int { return g; }\nint g = 1;", "S01", linea=1)

    def test_s02_mismo_nombre_en_ambitos_distintos(self):
        self.valido("int x = 1; { bool x = true; print(x); } print(x);")

    def test_s02_redeclaracion_en_el_mismo_ambito(self):
        error = self.invalido("int x;\nbool x;", "S02", linea=2)
        self.assertIn("línea 1", error.mensaje)

    def test_s02_parametro_repetido(self):
        self.invalido("func f(int a, bool a) { }", "S02")

    def test_s02_el_cuerpo_comparte_ambito_con_los_parametros(self):
        self.invalido("func f(int a) { int a = 2; }", "S02")
        self.valido("func f(int a) { { int a = 2; print(a); } }")

    def test_s02_funcion_repetida_o_con_nombre_de_variable(self):
        self.invalido("func f() { }\nfunc f() { }", "S02", linea=2)
        self.invalido("func f() { }\nint f;", "S02", linea=2)
        # La repetida se revisa con su propio tipo de retorno: no debe salir además un S12.
        self.invalido("func f() { }\nfunc f(): int { return 1; }", "S02", linea=2)


class TestFunciones(CasoSemantico):
    def test_s03_funcion_declarada_incluso_despues_de_usarla(self):
        self.valido("print(doble(2));\nfunc doble(int n): int { return n * 2; }")

    def test_s03_funcion_no_declarada(self):
        self.invalido("print(triple(2));", "S03")

    def test_s04_numero_de_argumentos_correcto(self):
        self.valido("func f(int a, bool b) { } f(1, true);")

    def test_s04_numero_de_argumentos_incorrecto(self):
        error = self.invalido("func f(int a, bool b) { }\nf(1);", "S04", linea=2)
        self.assertIn("2 argumento", error.mensaje)

    def test_s05_tipo_de_argumento_correcto(self):
        self.valido("func f(int a, bool b) { } f(1 + 2, 3 > 4);")

    def test_s05_tipo_de_argumento_incorrecto(self):
        error = self.invalido("func f(int a, bool b) { }\nf(1, 2);", "S05", linea=2)
        self.assertIn("argumento 2", error.mensaje)

    def test_s14_procedimiento_como_sentencia(self):
        self.valido("func p() { print(1); } p();")

    def test_s14_procedimiento_usado_como_valor(self):
        self.invalido("func p() { }\nprint(p());", "S14", linea=2)
        self.invalido("func p() { }\nint x = p() + 1;", "S14", linea=2)

    def test_s14_funcion_como_sentencia_descarta_su_valor(self):
        self.valido("func f(): int { return 1; } f();")

    def test_s15_funcion_usada_como_llamada(self):
        self.valido("func f(): int { return 1; } int x = f();")

    def test_s15_funcion_usada_como_variable(self):
        self.invalido("func f(): int { return 1; }\nint x = f;", "S15", linea=2)
        self.invalido("func f(): int { return 1; }\nf = 2;", "S15", linea=2)

    def test_s16_variable_usada_como_variable(self):
        self.valido("int x; int y = x + 1;")

    def test_s16_variable_llamada_como_funcion(self):
        self.invalido("int x;\nx();", "S16", linea=2)

    def test_recursion(self):
        self.valido("func f(int n): int { if (n < 1) { return 0; } return f(n - 1); }")


class TestTipos(CasoSemantico):
    def test_s06_asignacion_compatible(self):
        self.valido("bool b; b = 1 < 2;")

    def test_s06_asignacion_incompatible(self):
        error = self.invalido("int x;\nx = true;", "S06", linea=2)
        self.assertIn("bool", error.mensaje)

    def test_s06_asignacion_a_variable_no_declarada(self):
        self.invalido("x = 1;", "S01")

    def test_s07_declaracion_compatible(self):
        self.valido("int x = 2 * 3; bool b = !true;")

    def test_s07_declaracion_incompatible(self):
        self.invalido("bool b = 5;", "S07")

    def test_s08_operadores_bien_usados(self):
        self.valido("bool b = 1 + 2 * 3 > 4 && !(5 == 6) || true != false; int n = -(7 % 2);")

    def test_s08_aritmetica_con_bool(self):
        error = self.invalido("int x = 1 + true;", "S08")
        self.assertEqual(error.columna, 11)

    def test_s08_logico_con_int(self):
        self.invalido("bool b = 1 && true;", "S08")

    def test_s08_relacional_encadenado(self):
        self.invalido("bool b = 1 < 2 < 3;", "S08")

    def test_s08_igualdad_entre_tipos_distintos(self):
        self.invalido("bool b = 1 == true;", "S08")

    def test_s08_unarios(self):
        self.invalido("bool b = !5;", "S08")
        self.invalido("int n = -true;", "S08")

    def test_s09_condiciones_bool(self):
        self.valido("int i; while (i < 3) { if (i == 1) { print(i); } i = i + 1; }")

    def test_s09_condicion_del_if_no_es_bool(self):
        error = self.invalido("int x;\nif (x) { }", "S09", linea=2)
        self.assertIn("'if'", error.mensaje)

    def test_s09_condicion_del_while_no_es_bool(self):
        self.invalido("while (1 + 1) { }", "S09")

    def test_s09_condicion_del_else_if(self):
        self.invalido("if (true) { } else if (3) { }", "S09")

    def test_print_de_int_y_bool(self):
        self.valido("print(1); print(true);")


class TestReturn(CasoSemantico):
    def test_s10_return_dentro_de_funcion(self):
        self.valido("func p() { return; }")

    def test_s10_return_fuera_de_funcion(self):
        self.invalido("return 1;", "S10")

    def test_s11_return_del_tipo_correcto(self):
        self.valido("func f(): bool { return 1 < 2; }")

    def test_s11_return_de_tipo_incorrecto(self):
        self.invalido("func f(): bool {\nreturn 1;\n}", "S11", linea=2)

    def test_s12_return_con_y_sin_valor_donde_toca(self):
        self.valido("func f(): int { return 1; } func p() { return; }")

    def test_s12_return_sin_valor_en_funcion(self):
        self.invalido("func f(): int { return; }", "S12")

    def test_s12_return_con_valor_en_procedimiento(self):
        self.invalido("func p() { return 1; }", "S12")

    def test_s13_regresa_en_todos_los_caminos(self):
        self.valido("func f(int n): int { if (n > 0) { return 1; } else if (n < 0) { return -1; } else { return 0; } }")
        self.valido("func f(): int { { return 1; } }")

    def test_s13_if_sin_else(self):
        self.invalido("func f(int n): int { if (n > 0) { return 1; } }", "S13")

    def test_s13_return_solo_dentro_de_un_while(self):
        self.invalido("func f(): int { while (true) { return 1; } }", "S13")

    def test_s13_funcion_sin_return(self):
        self.invalido("func f(): int { print(1); }", "S13")


class TestVariosErrores(CasoSemantico):
    def test_reporta_tres_errores_distintos_con_su_linea(self):
        fuente = (
            "int x = 1;\n"
            "y = 2;\n"
            "int z = x + true;\n"
            "if (x) {\n"
            "    print(z);\n"
            "}\n"
        )
        errores = semantico(fuente)[2]
        self.assertEqual([(e.codigo, e.linea) for e in errores], [("S01", 2), ("S08", 3), ("S09", 4)])

    def test_errores_ordenados_por_linea_aunque_esten_en_funciones(self):
        fuente = "print(z);\nfunc f() { print(w); }\n"
        self.assertEqual([e.linea for e in semantico(fuente)[2]], [1, 2])

    def test_un_error_no_provoca_errores_en_cadena(self):
        self.assertEqual(codigos("int x = (nada + 1) * 2 - 3;"), ["S01"])
        self.assertEqual(codigos("bool b = !(nada < 1);"), ["S01"])
        self.assertEqual(codigos("print(noexiste(1) + 2);"), ["S03"])


class TestAnotaciones(CasoSemantico):
    def test_tipo_en_cada_expresion(self):
        programa, _ = self.valido("bool b = 1 + 2 < 3;")
        binaria = programa.elementos[0].inicial
        self.assertEqual((binaria.tipo, binaria.izquierda.tipo, binaria.derecha.tipo), ("bool", "int", "int"))

    def test_nombre_unico_cuando_se_oculta_una_variable(self):
        programa, _ = self.valido("int x = 1; { int x = 2; x = x + 1; } print(x);")
        externa, bloque, impresion = programa.elementos
        interna, asignacion = bloque.sentencias
        self.assertIsNone(externa.nombre_unico)
        self.assertEqual(interna.nombre_unico, "x_1")
        self.assertEqual(asignacion.nombre_unico, "x_1")
        self.assertEqual(asignacion.valor.izquierda.nombre_unico, "x_1")
        self.assertIsNone(impresion.valor.nombre_unico)

    def test_nombre_unico_en_parametros_de_funciones_distintas(self):
        programa, _ = self.valido("func f(int n) { } func g(int n) { print(n); }")
        g = programa.elementos[1]
        self.assertEqual(g.parametros[0].nombre_unico, "n_1")
        self.assertEqual(g.cuerpo.sentencias[0].valor.nombre_unico, "n_1")

    def test_nombre_unico_no_choca_con_un_nombre_del_programa(self):
        programa, _ = self.valido("int x; int x_1; { int x; print(x); }")
        self.assertEqual(programa.elementos[2].sentencias[0].nombre_unico, "x_2")

    def test_ejemplos_sin_errores_y_con_todas_las_expresiones_tipadas(self):
        for nombre in ("completo.src", "factorial.src"):
            with self.subTest(nombre):
                programa, _ = self.valido((EJEMPLOS / nombre).read_text(encoding="utf-8"))
                self.assertEqual(_expresiones_sin_tipo(programa), [])

    def test_tabla_de_un_programa_correcto_tiene_todos_sus_ambitos(self):
        _, tabla = self.valido("func f(int a): int { { int b = a; } return a; } int g = f(1);")
        self.assertEqual([a.nombre for a in tabla.ambitos()], ["global", "función f", "bloque (línea 1)"])
        texto = tabla.texto()
        for esperado in ("Ámbito global", "Ámbito función f", "Ámbito bloque", "g ", "a ", "b "):
            self.assertIn(esperado, texto)


class TestComando(unittest.TestCase):
    def correr(self, archivo: Path):
        salida, errores = io.StringIO(), io.StringIO()
        with redirect_stdout(salida), redirect_stderr(errores):
            codigo = main([str(archivo)])
        return codigo, salida.getvalue(), errores.getvalue()

    def test_programa_correcto_imprime_la_tabla(self):
        codigo, salida, _ = self.correr(EJEMPLOS / "completo.src")
        self.assertEqual(codigo, 0)
        self.assertIn("TABLA DE SÍMBOLOS", salida)
        self.assertIn("Ámbito función fibonacci (nivel 1)", salida)

    def test_programa_con_tres_errores_semanticos(self):
        codigo, _, errores = self.correr(EJEMPLOS / "error_semantico.src")
        self.assertEqual(codigo, 1)
        self.assertEqual(errores.count("Error semántico"), 3)


def _expresiones_sin_tipo(programa) -> list[str]:
    """Las expresiones sin tipo, salvo la llamada a un procedimiento usada como sentencia."""
    faltan: list[str] = []

    class Revisor(Visitor):
        def visitar_SentenciaExpr(self, nodo):
            for argumento in nodo.expresion.argumentos:
                self.visitar(argumento)

        def visitar_generico(self, nodo):
            if isinstance(nodo, Expresion) and nodo.tipo is None:
                faltan.append(f"{type(nodo).__name__} ({nodo.linea}:{nodo.columna})")
            super().visitar_generico(nodo)

    Revisor().visitar(programa)
    return faltan


if __name__ == "__main__":
    unittest.main()
