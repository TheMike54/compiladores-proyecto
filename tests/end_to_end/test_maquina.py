"""Pruebas de la máquina con código de pila escrito a mano y generado."""

import unittest

from src.backend.generador import generar
from src.backend.maquina import ejecutar
from tests.ir.test_criterio import EJEMPLOS, compilar


class MaquinaDePila(unittest.TestCase):
    def comprobar_salida(self, codigo: list[str], esperada: list[str]) -> None:
        salida: list[str] = []
        error = ejecutar(codigo, mostrar=salida.append)
        self.assertIsNone(error)
        self.assertEqual(salida, esperada)

    def test_saltos_y_orden_de_argumentos(self):
        codigo = """
FUNC resta a b
LOAD a
LOAD b
SUB
RET
LABEL @main
PUSH false
JZ @restar
PUSH 99
PRINT
JMP @fin
LABEL @restar
PUSH 7
PUSH 2
CALL resta 2
PRINT
LABEL @fin
HALT
"""
        self.comprobar_salida(codigo.splitlines(), ["5"])

    def test_ejemplos_con_ir_optimizado(self):
        ejemplos = {
            "factorial.src": ["120"],
            "completo.src": ["0", "1", "1", "2", "3", "5", "8", "13", "21", "34", "55",
                             "55", "true", "3"],
        }
        for archivo, salida_esperada in ejemplos.items():
            with self.subTest(archivo=archivo):
                fuente = (EJEMPLOS / archivo).read_text(encoding="utf-8")
                _, optimizado = compilar(fuente)
                self.comprobar_salida(generar(optimizado), salida_esperada)

    def test_division_y_residuo_negativos(self):
        codigo = ["LABEL @main", "PUSH -7", "PUSH 2", "DIV", "PRINT",
                  "PUSH -7", "PUSH 2", "MOD", "PRINT", "HALT"]
        self.comprobar_salida(codigo, ["-3", "-1"])

    def test_errores_de_ejecucion(self):
        casos = [
            (["PUSH 1", "PUSH 0", "DIV"], "división entre cero"),
            (["PUSH 1", "PUSH 0", "MOD"], "módulo entre cero"),
            (["LOAD g"], "la variable 'g' se usó antes de tener valor"),
            (["PUSH 2147483647", "PUSH 1", "ADD"], "entero de 32 bits"),
        ]
        for instrucciones, mensaje in casos:
            with self.subTest(mensaje=mensaje):
                error = ejecutar(["LABEL @main", *instrucciones, "HALT"])
                self.assertIsNotNone(error)
                self.assertEqual(error.fase, "ejecución")
                self.assertIn(mensaje, error.mensaje)

    def test_limite_de_llamadas(self):
        codigo = ["FUNC repetir", "CALL repetir 0", "RET",
                  "LABEL @main", "CALL repetir 0", "HALT"]
        error = ejecutar(codigo)
        self.assertIsNotNone(error)
        self.assertIn("desbordamiento de la pila de llamadas", error.mensaje)

    def test_funcion_actualiza_global(self):
        fuente = """
int g = 1;
func inc(int n) { g = g + n; }
inc(5);
print(g);
"""
        _, optimizado = compilar(fuente)
        self.comprobar_salida(generar(optimizado), ["6"])
