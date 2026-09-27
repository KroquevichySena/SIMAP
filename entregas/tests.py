"""
Testes das integrações externas do app de entregas (Gemini e Mailgun).

As APIs de verdade nunca são chamadas aqui: simulamos as respostas, inclusive
as falhas, para provar que o sistema continua funcionando quando elas caem.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Atividade, TrilhaAprendizagem
from turmas.models import Matricula, Turma

from .ia_services import gerar_analise
from .models import STATUS_CONCLUIDO, STATUS_ERRO, Submissao

Usuario = get_user_model()
SENHA = "SenhaDeTeste123"


class BaseEntregasTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(
            username="prof", password=SENHA, perfil="DOCENTE"
        )
        cls.aluno = Usuario.objects.create_user(
            username="joao.silva", password=SENHA, perfil="DISCENTE",
            first_name="João", last_name="Silva", rgm="11200099",
            email="joao.silva@exemplo.com",
        )
        cls.turma = Turma.objects.create(nome="Algoritmos", periodo="2026.2", docente=cls.docente)
        Matricula.objects.create(turma=cls.turma, discente=cls.aluno)
        trilha = TrilhaAprendizagem.objects.create(turma=cls.turma, titulo="Módulo 1")
        cls.atividade = Atividade.objects.create(
            trilha=trilha, titulo="Exercício", enunciado="Explique o que é uma variável."
        )


class GeminiTests(BaseEntregasTestCase):
    def setUp(self):
        self.submissao = Submissao.objects.create(
            atividade=self.atividade, aluno=self.aluno, resposta_texto="Um espaço na memória."
        )

    @mock.patch("entregas.ia_services.genai")
    def test_parecer_gravado_quando_a_api_responde(self, genai):
        genai.GenerativeModel.return_value.generate_content.return_value.text = "Boa resposta."
        analise = gerar_analise(self.submissao)
        self.assertEqual(analise.status, STATUS_CONCLUIDO)
        self.assertEqual(analise.parecer_texto, "Boa resposta.")

    @mock.patch("entregas.ia_services.genai")
    def test_so_enunciado_e_resposta_sao_enviados(self, genai):
        """Nome, login e e-mail do aluno não podem sair do sistema (LGPD)."""
        genai.GenerativeModel.return_value.generate_content.return_value.text = "ok"
        gerar_analise(self.submissao)
        prompt = genai.GenerativeModel.return_value.generate_content.call_args.args[0]
        self.assertIn("Explique o que é uma variável.", prompt)
        self.assertIn("Um espaço na memória.", prompt)
        for dado_pessoal in ("joao.silva", "João", "Silva", "11200099", "joao.silva@exemplo.com"):
            self.assertNotIn(dado_pessoal, prompt)

    @mock.patch("entregas.ia_services.genai")
    def test_falha_da_api_marca_erro_sem_quebrar(self, genai):
        genai.GenerativeModel.return_value.generate_content.side_effect = TimeoutError("sem resposta")
        with self.assertLogs("entregas.ia_services", level="ERROR"):
            analise = gerar_analise(self.submissao)
        self.assertEqual(analise.status, STATUS_ERRO)

    @mock.patch("entregas.ia_services.genai")
    def test_submissao_nao_se_perde_quando_a_api_falha(self, genai):
        genai.GenerativeModel.return_value.generate_content.side_effect = RuntimeError("fora do ar")
        Submissao.objects.all().delete()
        self.client.force_login(self.aluno)
        with self.assertLogs("entregas.ia_services", level="ERROR"):
            resposta = self.client.post(
                reverse("entregas:submeter", args=[self.atividade.pk]),
                {"resposta_texto": "Minha resposta."},
            )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Submissao.objects.filter(aluno=self.aluno).exists())


class MailgunTests(BaseEntregasTestCase):
    def setUp(self):
        self.client.force_login(self.docente)
        self.url = reverse("entregas:notificar_pendentes", args=[self.atividade.pk])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_aviso_de_pendencia_enviado(self):
        from django.core import mail

        self.client.post(self.url, {"mensagem": "Falta entregar!"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["joao.silva@exemplo.com"])

    @override_settings(
        EMAIL_BACKEND="usuarios.email_backend.MailgunEmailBackend",
        MAILGUN_API_KEY="chave-falsa", MAILGUN_DOMAIN="exemplo.mailgun.org",
    )
    @mock.patch("usuarios.email_backend.requests.post")
    def test_chamada_http_ao_mailgun(self, post):
        post.return_value.raise_for_status.return_value = None
        self.client.post(self.url, {"mensagem": "Falta entregar!"})
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.mailgun.net/v3/exemplo.mailgun.org/messages")
        self.assertEqual(kwargs["auth"], ("api", "chave-falsa"))
        self.assertEqual(kwargs["data"]["to"], "joao.silva@exemplo.com")
        self.assertEqual(kwargs["timeout"], 15)

    @override_settings(
        EMAIL_BACKEND="usuarios.email_backend.MailgunEmailBackend",
        MAILGUN_API_KEY="chave-falsa", MAILGUN_DOMAIN="exemplo.mailgun.org",
    )
    @mock.patch("usuarios.email_backend.requests.post")
    def test_mailgun_fora_do_ar_nao_derruba_a_tela(self, post):
        import requests

        post.side_effect = requests.ConnectionError("sem conexão")
        with self.assertLogs("simap.integracoes", level="ERROR"):
            resposta = self.client.post(self.url, {"mensagem": "Falta entregar!"}, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Não foi possível enviar os e-mails agora")
