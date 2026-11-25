import unittest

from src.semantic import Simbolo, TablaSimbolos


def variable(nombre: str, tipo: str = "int", linea: int = 1) -> Simbolo:
    return Simbolo(nombre, "variable", tipo, linea)


class TestTablaSimbolos(unittest.TestCase):
    def test_declarar_y_buscar_en_el_global(self):
        tabla = TablaSimbolos()
        self.assertIsNone(tabla.declarar(variable("x")))
        self.assertEqual(tabla.buscar("x").tipo, "int")
        self.assertIs(tabla.buscar("x").ambito, tabla.global_)

    def test_buscar_un_nombre_inexistente_regresa_none(self):
        self.assertIsNone(TablaSimbolos().buscar("x"))

    def test_redeclarar_en_el_mismo_ambito_regresa_el_previo(self):
        tabla = TablaSimbolos()
        primero = variable("x", linea=1)
        tabla.declarar(primero)
        self.assertIs(tabla.declarar(variable("x", "bool", linea=2)), primero)
        self.assertEqual(tabla.buscar("x").tipo, "int")

    def test_un_ambito_interno_ve_al_externo(self):
        tabla = TablaSimbolos()
        tabla.declarar(variable("x"))
        tabla.abrir("bloque")
        self.assertIsNotNone(tabla.buscar("x"))

    def test_un_ambito_interno_oculta_al_externo_y_al_cerrar_reaparece(self):
        tabla = TablaSimbolos()
        tabla.declarar(variable("x", "int"))
        tabla.abrir("bloque")
        self.assertIsNone(tabla.declarar(variable("x", "bool")))
        self.assertEqual(tabla.buscar("x").tipo, "bool")
        tabla.cerrar()
        self.assertEqual(tabla.buscar("x").tipo, "int")

    def test_lo_declarado_en_un_bloque_no_se_ve_al_cerrarlo(self):
        tabla = TablaSimbolos()
        tabla.abrir("bloque")
        tabla.declarar(variable("y"))
        tabla.cerrar()
        self.assertIsNone(tabla.buscar("y"))

    def test_niveles_y_ambitos_cerrados_se_conservan(self):
        tabla = TablaSimbolos()
        tabla.abrir("función f")
        tabla.abrir("bloque (línea 2)")
        tabla.cerrar()
        tabla.cerrar()
        tabla.abrir("bloque (línea 5)")
        tabla.cerrar()
        self.assertEqual([(a.nombre, a.nivel) for a in tabla.ambitos()],
                         [("global", 0), ("función f", 1), ("bloque (línea 2)", 2), ("bloque (línea 5)", 1)])

    def test_no_se_puede_cerrar_el_global(self):
        with self.assertRaises(RuntimeError):
            TablaSimbolos().cerrar()

    def test_texto_muestra_cada_ambito_con_sus_simbolos(self):
        tabla = TablaSimbolos()
        tabla.declarar(Simbolo("suma", "funcion", "int", 1, tipos_parametros=["int", "int"]))
        tabla.abrir("función suma")
        tabla.declarar(Simbolo("a", "parametro", "int", 1, nombre_unico="a"))
        texto = tabla.texto()
        self.assertIn("Ámbito global (nivel 0)", texto)
        self.assertIn("Ámbito función suma (nivel 1)", texto)
        self.assertRegex(texto, r"suma\s+funcion\s+int\s+1\s+\(int, int\)")
        self.assertRegex(texto, r"a\s+parametro\s+int\s+1\s+a")


if __name__ == "__main__":
    unittest.main()
