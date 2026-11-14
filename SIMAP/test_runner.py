"""
Separa os testes em unitários e de integração para a pipeline de CI.

A regra é a mesma que o próprio Django usa para isolar o banco:

- Testes unitários: classes que herdam de SimpleTestCase (ou unittest.TestCase)
  e não de TransactionTestCase. O Django proíbe acesso ao banco nelas, então
  são testes de regra pura, sem banco e sem servidor.
- Testes de integração: classes que herdam de TestCase, TransactionTestCase ou
  LiveServerTestCase. Usam o banco de teste (SQLite em memória, criado e
  descartado a cada execução), o cliente HTTP do Django ou um servidor real.

Uso:
    python manage.py test --settings=SIMAP.settings_test --tipo unitarios
    python manage.py test --settings=SIMAP.settings_test --tipo integracao
    python manage.py test --settings=SIMAP.settings_test            (todos)
"""
import unittest

from django.test import TransactionTestCase
from django.test.runner import DiscoverRunner

TIPOS = ("unitarios", "integracao")


def _testes(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _testes(item)
        else:
            yield item


def eh_integracao(teste):
    return isinstance(teste, TransactionTestCase)


class SeparadorDeTestesRunner(DiscoverRunner):

    def __init__(self, tipo=None, **kwargs):
        super().__init__(**kwargs)
        self.tipo = tipo

    @classmethod
    def add_arguments(cls, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--tipo",
            choices=TIPOS,
            help="Roda só os testes unitários (sem banco) ou só os de integração (com banco).",
        )

    def build_suite(self, *args, **kwargs):
        suite = super().build_suite(*args, **kwargs)
        if not self.tipo:
            return suite

        querer_integracao = self.tipo == "integracao"
        escolhidos = [t for t in _testes(suite) if eh_integracao(t) == querer_integracao]
        if not escolhidos:
            # Uma seleção vazia passaria "verde" sem testar nada: isso é erro.
            raise SystemExit(f"Nenhum teste do tipo '{self.tipo}' foi encontrado.")
        return self.test_suite(escolhidos)
