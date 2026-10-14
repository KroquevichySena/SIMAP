from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

Usuario = get_user_model()


class RecuperarSenhaTests(TestCase):
    """Se o Mailgun cair, a recuperação de senha segue sem erro 500."""

    @override_settings(
        EMAIL_BACKEND="usuarios.email_backend.MailgunEmailBackend",
        MAILGUN_API_KEY="chave-falsa", MAILGUN_DOMAIN="exemplo.mailgun.org",
    )
    @mock.patch("usuarios.email_backend.requests.post")
    def test_mailgun_fora_do_ar_nao_quebra_a_recuperacao_de_senha(self, post):
        import requests

        Usuario.objects.create_user(
            username="aluno", password="SenhaDeTeste123", perfil="DISCENTE",
            email="aluno@exemplo.com",
        )
        post.side_effect = requests.ConnectionError("sem conexão")
        # O próprio Django captura a falha do envio e registra no log dele.
        with self.assertLogs("django.contrib.auth", level="ERROR"):
            resposta = self.client.post(reverse("password_reset"), {"email": "aluno@exemplo.com"})
        self.assertRedirects(resposta, reverse("password_reset_done"))
