"""Regressões da saída produzida pelo executor Python usado no navegador."""
import io
import re
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase


class SaidaDoWorkerTest(SimpleTestCase):
    def executar(self, codigo, entradas):
        fonte = (Path(settings.BASE_DIR) / "static/js/python_worker.js").read_text(encoding="utf-8")
        preparo = re.search(r"const PREPARO = `([\s\S]*?)`;", fonte).group(1)
        # O template JavaScript usa barras duplas para os escapes do Python.
        preparo = preparo.replace("\\\\", "\\")
        saida = io.StringIO()
        with redirect_stdout(saida), redirect_stderr(io.StringIO()), patch("builtins.input"):
            escopo = {}
            exec(preparo, escopo)
            erro = escopo["__simap_executar"](codigo, entradas)
        return saida.getvalue(), erro

    def test_soma_com_duas_entradas_compara_apenas_o_resultado(self):
        saida, erro = self.executar("a = int(input())\nb = int(input())\nprint(a + b)", ["2", "3"])
        self.assertEqual(saida, "5\n")
        self.assertEqual(erro, "")

    def test_ler_uma_entrada_sem_imprimir_nao_produz_saida(self):
        saida, erro = self.executar("valor = input()", ["segredo"])
        self.assertEqual(saida, "")
        self.assertEqual(erro, "")

    def test_print_da_entrada_aparece_uma_unica_vez(self):
        saida, erro = self.executar("print(input())", ["7"])
        self.assertEqual(saida, "7\n")
        self.assertEqual(erro, "")

    def test_mensagem_do_input_e_impressao_explicita_sao_preservadas(self):
        saida, erro = self.executar('valor = input("Número: ")\nprint(int(valor) * 2)', ["7"])
        self.assertEqual(saida, "Número: 14\n")
        self.assertEqual(erro, "")

    def test_entrada_vazia_e_diferente_de_entrada_ausente(self):
        saida, erro = self.executar("print(repr(input()))", [""])
        self.assertEqual(saida, "''\n")
        self.assertEqual(erro, "")
        saida, erro = self.executar("input()", [])
        self.assertEqual(saida, "")
        self.assertIn("EOFError", erro)

    def test_espacos_e_quebras_impressos_pelo_programa_sao_preservados(self):
        saida, erro = self.executar('print("  *")\nprint()\nprint("***", end="")', [])
        self.assertEqual(saida, "  *\n\n***")
        self.assertEqual(erro, "")
