
from unittest.mock import MagicMock, patch

import requests
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings

from usuarios.email_backend import MailgunEmailBackend

POST = "usuarios.email_backend.requests.post"
LOGGER = "usuarios.email_backend"

CONFIG_MAILGUN = {
    "MAILGUN_API_KEY": "chave-de-teste",
    "MAILGUN_DOMAIN": "sandbox-teste.mailgun.org",
    "MAILGUN_API_URL": "https://api.mailgun.net",
}


def montar_email(destinatarios=("aluno@exemplo.com",), corpo="Olá, aluno."):
    return EmailMessage(
        "Assunto de teste", corpo, "sistema@simap.local", list(destinatarios)
    )


def resposta_com_erro_http(mensagem="401 Unauthorized"):
    resposta = MagicMock()
    resposta.raise_for_status.side_effect = requests.HTTPError(mensagem)
    return resposta


@override_settings(**CONFIG_MAILGUN)
class MailgunEmailBackendTest(SimpleTestCase):

    # ---------- caminho feliz ----------
    @patch(POST)
    def test_deve_enviar_ao_mailgun_e_retornar_um_quando_a_api_aceita(self, post):
        # Arrange
        post.return_value = MagicMock()
        backend = MailgunEmailBackend()

        # Act
        enviados = backend.send_messages([montar_email()])

        # Assert
        self.assertEqual(enviados, 1)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(
            args[0], "https://api.mailgun.net/v3/sandbox-teste.mailgun.org/messages"
        )
        self.assertEqual(kwargs["auth"], ("api", "chave-de-teste"))
        self.assertEqual(kwargs["timeout"], 15)
        self.assertEqual(kwargs["data"]["to"], "aluno@exemplo.com")
        self.assertEqual(kwargs["data"]["subject"], "Assunto de teste")

    # ---------- violações / exceções ----------
    @override_settings(MAILGUN_API_KEY="")
    @patch(POST)
    def test_deve_lancar_improperly_configured_quando_falta_a_chave(self, post):
        backend = MailgunEmailBackend()

        with self.assertRaisesMessage(ImproperlyConfigured, "MAILGUN_API_KEY"):
            backend.send_messages([montar_email()])

        post.assert_not_called()

    @patch(POST)
    def test_deve_propagar_erro_http_quando_fail_silently_for_falso(self, post):
        post.return_value = resposta_com_erro_http("401 Unauthorized")
        backend = MailgunEmailBackend(fail_silently=False)

        with self.assertLogs(LOGGER, level="ERROR") as logs:
            with self.assertRaises(requests.HTTPError) as contexto:
                backend.send_messages([montar_email()])

        self.assertIn("401", str(contexto.exception))
        self.assertIn("Falha ao enviar e-mail pelo Mailgun", logs.output[0])

    # ---------- casos-limite ----------
    @patch(POST)
    def test_deve_retornar_zero_e_nao_chamar_a_api_quando_a_lista_for_vazia(self, post):
        backend = MailgunEmailBackend()

        enviados = backend.send_messages([])

        self.assertEqual(enviados, 0)
        post.assert_not_called()

    @patch(POST)
    def test_deve_registrar_log_e_retornar_zero_quando_fail_silently_for_verdadeiro(
        self, post
    ):
        post.return_value = resposta_com_erro_http("500 Server Error")
        backend = MailgunEmailBackend(fail_silently=True)

        with self.assertLogs(LOGGER, level="ERROR"):
            enviados = backend.send_messages([montar_email()])

        self.assertEqual(enviados, 0)
        post.assert_called_once()

    @patch(POST)
    def test_deve_juntar_varios_destinatarios_com_virgula(self, post):
        post.return_value = MagicMock()
        backend = MailgunEmailBackend()

        backend.send_messages([montar_email(("a@exemplo.com", "b@exemplo.com"))])

        self.assertEqual(
            post.call_args.kwargs["data"]["to"], "a@exemplo.com,b@exemplo.com"
        )

    # ---------- parametrizado (subTest) ----------
    @patch(POST)
    def test_deve_enviar_o_corpo_no_campo_conforme_o_tipo_de_conteudo(self, post):
        casos = [("plain", "text"), ("html", "html")]
        for tipo, campo_esperado in casos:
            with self.subTest(tipo=tipo):
                post.reset_mock()
                post.return_value = MagicMock()
                email = montar_email(corpo="<b>Olá</b>")
                email.content_subtype = tipo

                MailgunEmailBackend().send_messages([email])

                dados = post.call_args.kwargs["data"]
                self.assertEqual(dados[campo_esperado], "<b>Olá</b>")
