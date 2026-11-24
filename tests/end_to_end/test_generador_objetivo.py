import tempfile
import unittest
from pathlib import Path

from src.backend.generador import generar, guardar
from src.ir import Instruccion
from tests.ir.test_criterio import EJEMPLOS, compilar


class GeneradorObjetivo(unittest.TestCase):
    def test_traduce_funciones_argumentos_y_saltos(self):
        ir = [
            Instruccion("func", arg1="resta", params=("a", "b")),
            Instruccion("sub", destino="@t1", arg1="a", arg2="b"),
            Instruccion("return", arg1="@t1"),
            Instruccion("endfunc", arg1="resta"),
            Instruccion("label", etiqueta="@main"),
            Instruccion("if_false", arg1=True, etiqueta="@L1"),
            Instruccion("param", arg1=7),
            Instruccion("param", arg1=2),
            Instruccion("call", destino="@t2", arg1="resta", arg2=2),
            Instruccion("print", arg1="@t2"),
            Instruccion("goto", etiqueta="@L1"),
            Instruccion("label", etiqueta="@L1"),
            Instruccion("return"),
        ]
        self.assertEqual(
            generar(ir),
            [
                "FUNC resta a b", "LOAD a", "LOAD b", "SUB", "STORE @t1",
                "LOAD @t1", "RET", "LABEL @main", "PUSH true", "JZ @L1",
                "PUSH 7", "PUSH 2", "CALL resta 2", "STORE @t2",
                "LOAD @t2", "PRINT", "JMP @L1", "LABEL @L1", "HALT",
            ],
        )

    def test_genera_y_guarda_el_factorial_optimizado(self):
        fuente = (EJEMPLOS / "factorial.src").read_text(encoding="utf-8")
        _, optimizado = compilar(fuente)
        codigo = generar(optimizado)

        self.assertEqual(codigo[0], "LABEL @main")
        self.assertIn("MUL", codigo)
        self.assertTrue(any(linea.startswith("JZ ") for linea in codigo))
        self.assertEqual(codigo[-2:], ["PRINT", "HALT"])
        with tempfile.TemporaryDirectory() as directorio:
            destino = Path(directorio) / "factorial.pila"
            guardar(codigo, destino)
            self.assertEqual(destino.read_text(encoding="utf-8").splitlines(), codigo)
