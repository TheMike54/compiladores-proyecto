"""Comprueba que los artefactos de `examples/salidas/` siguen iguales a lo que produce el compilador.

Para regenerarlos después de un cambio intencional: `python -m tests.end_to_end.test_salidas`.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORIO = Path(__file__).resolve().parents[2]
EJEMPLOS = REPOSITORIO / "examples"
SALIDAS = EJEMPLOS / "salidas"

VALIDOS = ["factorial", "completo", "optimizacion"]
CON_ERRORES = ["error_lexico", "error_sintactico", "error_semantico"]

# Opción del comando, encabezado que imprime y archivo donde se guarda.
ARTEFACTOS = [
    ("--tokens", "TOKENS", "tokens.txt"),
    ("--ast", "AST", "ast.txt"),
    ("--simbolos", "TABLA DE SÍMBOLOS", "simbolos.txt"),
    ("--ir", "IR", "ir.txt"),
    ("--ir-opt", "IR OPTIMIZADO", "ir-opt.txt"),
    ("--objetivo", "CÓDIGO OBJETIVO", "objetivo.pila"),
]


def _correr(programa: str, *opciones: str) -> subprocess.CompletedProcess:
    entorno = dict(os.environ, PYTHONPATH=str(REPOSITORIO), PYTHONIOENCODING="utf-8")
    with tempfile.TemporaryDirectory() as directorio:
        return subprocess.run(
            [sys.executable, "-m", "src.main", str(EJEMPLOS / f"{programa}.src"), *opciones],
            cwd=directorio,
            env=entorno,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )


def artefactos(programa: str) -> dict[str, str]:
    """Nombre de archivo -> contenido, tal como lo imprime el comando único."""
    if programa in CON_ERRORES:
        return {"errores.txt": _correr(programa).stderr}

    salida = _correr(programa).stdout
    archivos = {"salida.txt": salida}
    for opcion, encabezado, archivo in ARTEFACTOS:
        texto = _correr(programa, opcion).stdout
        inicio = f"== {encabezado} ==\n"
        # El comando imprime el artefacto, una línea en blanco y luego la salida del programa.
        if not texto.startswith(inicio) or not texto.endswith("\n\n" + salida):
            raise ValueError(f"salida inesperada de {opcion} con {programa}")
        archivos[archivo] = texto[len(inicio) : len(texto) - len(salida) - 1]
    return archivos


@unittest.skipUnless(importlib.util.find_spec("src.semantic"), "requiere la fase semántica")
class ArtefactosVersionados(unittest.TestCase):
    def test_artefactos_iguales_al_compilador(self):
        for programa in VALIDOS + CON_ERRORES:
            for archivo, contenido in artefactos(programa).items():
                with self.subTest(programa=programa, archivo=archivo):
                    guardado = (SALIDAS / programa / archivo).read_text(encoding="utf-8")
                    self.assertEqual(guardado, contenido)


def regenerar() -> None:
    for programa in VALIDOS + CON_ERRORES:
        carpeta = SALIDAS / programa
        carpeta.mkdir(parents=True, exist_ok=True)
        for archivo, contenido in artefactos(programa).items():
            (carpeta / archivo).write_text(contenido, encoding="utf-8", newline="\n")
            print(carpeta.relative_to(REPOSITORIO) / archivo)


if __name__ == "__main__":
    regenerar()
