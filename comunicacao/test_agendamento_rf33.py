"""Contrato do processador com o agendador, sem banco ou e-mails reais."""

import os
import runpy
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

MODULO = "comunicacao.management.commands.notificar_acompanhamento"


class ResultadoAgendamentoTest(SimpleTestCase):
    @patch(f"{MODULO}.verificar_atencao", return_value=0)
    @patch(f"{MODULO}.processar_pendentes", return_value={"falha": 1})
    def test_falha_de_envio_retorna_erro_para_o_agendador(self, processar, verificar):
        with self.assertRaisesMessage(CommandError, "permanecem pendentes"):
            call_command("notificar_acompanhamento", falhar_em_erro=True, stdout=StringIO())
        processar.assert_called_once_with(200)
        verificar.assert_called_once_with()

    @patch(f"{MODULO}.verificar_atencao", return_value=0)
    @patch(f"{MODULO}.processar_pendentes", return_value={"sem_email": 1, "aguardando_publicacao": 1})
    def test_avisos_aguardando_nao_sao_reportados_como_falha_do_provedor(self, processar, verificar):
        call_command("notificar_acompanhamento", falhar_em_erro=True, stdout=StringIO())

    @patch(f"{MODULO}.verificar_atencao", return_value=0)
    @patch(f"{MODULO}.processar_pendentes", return_value={"falha": 1})
    def test_comportamento_anterior_preservado_sem_opcao_estrita(self, processar, verificar):
        call_command("notificar_acompanhamento", stdout=StringIO())

    @patch(f"{MODULO}.verificar_atencao", return_value=1)
    @patch(f"{MODULO}.processar_pendentes", return_value={"enviado": 1})
    def test_envio_confirmado_produz_resumo(self, processar, verificar):
        saida = StringIO()
        call_command("notificar_acompanhamento", falhar_em_erro=True, stdout=saida)
        self.assertIn("Novos alertas de atenção: 1", saida.getvalue())
        self.assertIn("'enviado': 1", saida.getvalue())


class ExecucaoProtegidaTest(SimpleTestCase):
    def setUp(self):
        caminho = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "executar_rf33.py"
        self.executar = runpy.run_path(str(caminho))["executar"]
        self.ambiente = {
            "SECRET_KEY": "chave-ficticia-exclusiva-do-teste",
            "DATABASE_URL": "postgresql://ficticio:credencial-ficticia@banco.invalid/teste",
            "MAILGUN_API_KEY": "api-ficticia-do-teste",
            "MAILGUN_DOMAIN": "sandbox.invalid",
            "DEFAULT_FROM_EMAIL": "teste@sandbox.invalid",
            "EMAIL_BACKEND": "usuarios.email_backend.MailgunEmailBackend",
        }

    def test_sem_configuracao_nao_inicializa_django(self):
        with patch.dict(os.environ, {}, clear=True), patch("django.setup") as setup, redirect_stdout(StringIO()):
            self.assertEqual(self.executar(), 1)
        setup.assert_not_called()

    def test_backend_console_nao_pode_produzir_sucesso(self):
        self.ambiente["EMAIL_BACKEND"] = "django.core.mail.backends.console.EmailBackend"
        with patch.dict(os.environ, self.ambiente, clear=True), patch("django.setup") as setup, \
                redirect_stdout(StringIO()):
            self.assertEqual(self.executar(), 1)
        setup.assert_not_called()

    def test_excecao_nao_expoe_credenciais_nos_logs(self):
        saida = StringIO()
        with patch.dict(os.environ, self.ambiente, clear=True), patch("django.setup"), \
                patch("django.core.management.call_command", side_effect=RuntimeError(self.ambiente["DATABASE_URL"])), \
                redirect_stdout(saida):
            self.assertEqual(self.executar(), 1)
        self.assertNotIn("credencial-ficticia", saida.getvalue())
        self.assertNotIn("Traceback", saida.getvalue())

    def test_sucesso_executa_comando_com_verificacao_de_falha(self):
        with patch.dict(os.environ, self.ambiente, clear=True), patch("django.setup"), \
                patch("django.core.management.call_command") as comando, redirect_stdout(StringIO()):
            self.assertEqual(self.executar(), 0)
        self.assertEqual(comando.call_args.args, ("notificar_acompanhamento",))
        self.assertTrue(comando.call_args.kwargs["falhar_em_erro"])
