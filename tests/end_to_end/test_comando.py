"""Comprueba el comando público con todas las fases integradas."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORIO = Path(__file__).resolve().parents[2]


@unittest.skipUnless(importlib.util.find_spec("src.semantic"), "requiere la fase semántica")
class ComandoDelCompilador(unittest.TestCase):
    def ejecutar(self, directorio, fuente, *opciones):
        entorno = dict(os.environ, PYTHONPATH=str(REPOSITORIO))
        return subprocess.run(
            [sys.executable, "-m", "src.main", str(fuente), *opciones],
            cwd=directorio,
            env=entorno,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_factorial_y_archivo_objetivo(self):
        with tempfile.TemporaryDirectory() as directorio:
            fuente = REPOSITORIO / "examples" / "factorial.src"
            resultado = self.ejecutar(directorio, fuente)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertEqual(resultado.stdout.splitlines(), ["120"])
            codigo = Path(directorio, "build", "factorial.pila").read_text(encoding="utf-8")
            self.assertIn("LABEL @main\n", codigo)
            self.assertTrue(codigo.endswith("HALT\n"))

    def test_todo_muestra_los_artefactos_y_ejecuta(self):
        with tempfile.TemporaryDirectory() as directorio:
            fuente = REPOSITORIO / "examples" / "factorial.src"
            resultado = self.ejecutar(directorio, fuente, "--todo")
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            encabezados = [linea for linea in resultado.stdout.splitlines() if linea.startswith("== ")]
            self.assertEqual(encabezados, [
                "== TOKENS ==", "== AST ==", "== TABLA DE SÍMBOLOS ==",
                "== IR ==", "== IR OPTIMIZADO ==", "== CÓDIGO OBJETIVO ==",
            ])
            self.assertIn("├", resultado.stdout)
            self.assertEqual(resultado.stdout.splitlines()[-1], "120")

    def test_error_semantico_detiene_la_generacion(self):
        with tempfile.TemporaryDirectory() as directorio:
            fuente = Path(directorio, "invalido.src")
            fuente.write_text("print(no_declarada);", encoding="utf-8")
            resultado = self.ejecutar(directorio, fuente)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("no_declarada", resultado.stderr)
            self.assertFalse(Path(directorio, "build").exists())

    def test_error_de_ejecucion(self):
        with tempfile.TemporaryDirectory() as directorio:
            fuente = Path(directorio, "division.src")
            fuente.write_text("print(1 / 0);", encoding="utf-8")
            resultado = self.ejecutar(directorio, fuente)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("división entre cero", resultado.stderr)

    def test_archivo_inexistente(self):
        with tempfile.TemporaryDirectory() as directorio:
            fuente = Path(directorio, "inexistente.src")
            resultado = self.ejecutar(directorio, fuente)
            self.assertEqual(resultado.returncode, 2)
            self.assertIn("No se pudo leer", resultado.stderr)
