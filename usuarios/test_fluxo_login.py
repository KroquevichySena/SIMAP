"""Login no caminho da chamada: conta e aceite continuam obrigatórios."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import AceiteTermos


class LoginParaChamadaTest(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="aluno.token", password="SenhaTeste123", perfil="DISCENTE"
        )
        self.destino = reverse("chamada:confirmar_presenca")

    def test_chamada_exige_login_e_tela_explica_o_codigo(self):
        self.assertRedirects(
            self.client.get(self.destino),
            f"{reverse('login')}?next={self.destino}",
        )
        resposta = self.client.get(reverse("login"), {"next": self.destino})
        self.assertContains(resposta, 'name="next"')
        self.assertContains(resposta, f'value="{self.destino}"')
        self.assertContains(resposta, "não substitui seu usuário e senha")
        self.assertNotContains(resposta, "Acessar Entrada Direta por Token")

    def test_login_preserva_destino_e_aceite_por_versao(self):
        dados = {"username": self.usuario.username, "password": "SenhaTeste123", "next": self.destino}
        sem_aceite = self.client.post(reverse("login"), dados)
        self.assertEqual(sem_aceite.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            self.client.post(reverse("login"), {**dados, "aceite_termos": "on"}),
            self.destino,
        )
        self.assertEqual(AceiteTermos.objects.filter(
            usuario=self.usuario, versao=settings.TERMOS_DE_USO_VERSAO
        ).count(), 1)
        self.client.logout()
        self.assertRedirects(self.client.post(reverse("login"), dados), self.destino)

    def test_destino_externo_nao_e_aceito(self):
        resposta = self.client.post(reverse("login"), {
            "username": self.usuario.username, "password": "SenhaTeste123",
            "aceite_termos": "on", "next": "https://externo.example/",
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("externo.example", resposta.url)
