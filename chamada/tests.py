"""
Testes da tela de confirmação de presença com login obrigatório.

O aluno não informa mais o próprio usuário: a presença é sempre registrada
para quem está logado, e só discentes entram na tela.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from turmas.models import Matricula, Turma
from usuarios.test_helpers import registrar_aceites_atuais

from .models import Chamada, Registro_de_Presenca

Usuario = get_user_model()
SENHA = "SenhaDeTeste123"


class ConfirmarPresencaViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(
            username="prof.ana", password=SENHA, perfil="DOCENTE"
        )
        cls.discente = Usuario.objects.create_user(
            username="aluno.carla", password=SENHA, perfil="DISCENTE"
        )
        cls.outro_discente = Usuario.objects.create_user(
            username="aluno.diego", password=SENHA, perfil="DISCENTE"
        )
        cls.turma = Turma.objects.create(
            nome="Algoritmos I", periodo="2026.2", docente=cls.docente
        )
        Matricula.objects.create(turma=cls.turma, discente=cls.discente)
        Matricula.objects.create(turma=cls.turma, discente=cls.outro_discente)
        cls.chamada = Chamada.objects.create(
            turma=cls.turma,
            token_chamada="AULA01",
            data_expiracao=timezone.now() + timedelta(hours=1),
            limite_uso=30,
        )
        cls.url = reverse("chamada:confirmar_presenca")

        registrar_aceites_atuais(Usuario.objects.all())

    def test_usuario_anonimo_e_redirecionado_para_login(self):
        resposta = self.client.get(self.url)

        self.assertRedirects(
            resposta,
            f"{resolve_url(settings.LOGIN_URL)}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_docente_nao_acessa_a_tela_do_aluno(self):
        self.client.login(username="prof.ana", password=SENHA)

        resposta = self.client.get(self.url)

        self.assertRedirects(resposta, reverse("core:dashboard"), fetch_redirect_response=False)

    def test_discente_logado_ve_o_formulario_sem_campo_de_usuario(self):
        self.client.login(username="aluno.carla", password=SENHA)

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("username", resposta.context["form"].fields)

    def test_presenca_e_registrada_para_o_aluno_logado(self):
        self.client.login(username="aluno.carla", password=SENHA)

        self.client.post(self.url, {"turma": self.turma.pk, "token_chamada": "aula01"})
        self.client.post(reverse("chamada:confirmar_leitura"))

        self.assertTrue(
            Registro_de_Presenca.objects.filter(
                chamada=self.chamada, discente=self.discente
            ).exists()
        )
        self.assertFalse(
            Registro_de_Presenca.objects.filter(discente=self.outro_discente).exists()
        )

    def test_campo_username_enviado_no_post_e_ignorado(self):
        """Mesmo forjando o usuário de um colega, a presença vai para quem está logado."""
        self.client.login(username="aluno.carla", password=SENHA)

        self.client.post(
            self.url,
            {"username": "aluno.diego", "turma": self.turma.pk, "token_chamada": "AULA01"},
        )
        self.client.post(reverse("chamada:confirmar_leitura"), {"username": "aluno.diego"})

        self.assertFalse(
            Registro_de_Presenca.objects.filter(discente=self.outro_discente).exists()
        )
        self.assertEqual(Registro_de_Presenca.objects.filter(discente=self.discente).count(), 1)
