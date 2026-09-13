"""
Testes da Funcionalidade 7 — Trilhas de Aprendizagem e Publicação de Atividades.

Cobrem os critérios de aceitação da Ficha de Caracterização:
  - docente cria trilha vinculada a uma turma e publica atividades;
  - atividades exibidas ao discente na ordem definida pela trilha;
  - discente visualiza apenas as trilhas das turmas em que está matriculado;
  - progresso registrado por atividade concluída.
E os requisitos não funcionais de segurança (autorização por perfil, anti-IDOR).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from turmas.models import Matricula, Turma

from .models import Atividade, ConclusaoAtividade, TrilhaAprendizagem

Usuario = get_user_model()
SENHA = "SenhaDeTeste123"


class BaseSIMAPTestCase(TestCase):
    """Cenário comum: dois docentes, dois discentes, duas turmas."""

    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(
            username="prof.ana", password=SENHA, perfil="DOCENTE"
        )
        cls.outro_docente = Usuario.objects.create_user(
            username="prof.bruno", password=SENHA, perfil="DOCENTE"
        )
        cls.discente = Usuario.objects.create_user(
            username="aluno.carla", password=SENHA, perfil="DISCENTE"
        )
        cls.outro_discente = Usuario.objects.create_user(
            username="aluno.diego", password=SENHA, perfil="DISCENTE"
        )

        cls.turma = Turma.objects.create(
            nome="Algoritmos I", periodo="2026.2", docente=cls.docente, ativa=True
        )
        cls.turma_alheia = Turma.objects.create(
            nome="Banco de Dados", periodo="2026.2", docente=cls.outro_docente, ativa=True
        )

        Matricula.objects.create(
            turma=cls.turma, discente=cls.discente, status="ATIVA"
        )

        cls.trilha = TrilhaAprendizagem.objects.create(
            turma=cls.turma, titulo="Módulo 1 - Variáveis", ordem=1, publicada=True
        )
        cls.atividade = Atividade.objects.create(
            trilha=cls.trilha,
            titulo="Exercício de tipos primitivos",
            enunciado="Descreva os tipos primitivos.",
            ordem=1,
            publicada=True,
        )


class ModeloTrilhaTests(BaseSIMAPTestCase):
    def test_titulo_da_trilha_e_unico_dentro_da_turma(self):
        with self.assertRaises(IntegrityError):
            TrilhaAprendizagem.objects.create(
                turma=self.turma, titulo="Módulo 1 - Variáveis", ordem=2
            )

    def test_total_atividades_reflete_atividades_vinculadas(self):
        self.assertEqual(self.trilha.total_atividades, 1)

    def test_prazo_expirado_identifica_atividade_vencida(self):
        vencida = Atividade.objects.create(
            trilha=self.trilha,
            titulo="Atividade vencida",
            enunciado="...",
            prazo=timezone.now() - timedelta(days=1),
        )
        self.assertTrue(vencida.prazo_expirado)
        self.assertFalse(self.atividade.prazo_expirado)


class ControleDeAcessoTests(BaseSIMAPTestCase):
    """RN: aluno recebe negação de acesso a funcionalidade exclusiva do docente."""

    def test_discente_recebe_403_em_rota_de_docente(self):
        self.client.login(username="aluno.carla", password=SENHA)
        self.assertEqual(self.client.get(reverse("listar_trilhas")).status_code, 403)
        self.assertEqual(self.client.get(reverse("criar_trilha")).status_code, 403)
        self.assertEqual(self.client.get(reverse("listar_atividades")).status_code, 403)

    def test_docente_recebe_403_em_rota_de_discente(self):
        self.client.login(username="prof.ana", password=SENHA)
        self.assertEqual(self.client.get(reverse("minhas_trilhas")).status_code, 403)

    def test_usuario_anonimo_nao_acessa_trilhas(self):
        self.assertEqual(self.client.get(reverse("listar_trilhas")).status_code, 403)

    def test_dashboard_encaminha_conforme_perfil(self):
        self.client.login(username="prof.ana", password=SENHA)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("listar_trilhas"))
        self.client.logout()

        self.client.login(username="aluno.carla", password=SENHA)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("minhas_trilhas"))


class TrilhaDocenteTests(BaseSIMAPTestCase):
    def setUp(self):
        self.client.login(username="prof.ana", password=SENHA)

    def test_docente_cria_trilha_vinculada_a_sua_turma(self):
        resposta = self.client.post(
            reverse("criar_trilha"),
            {
                "turma": self.turma.pk,
                "titulo": "Módulo 2 - Condicionais",
                "descricao": "Estruturas de decisão.",
                "ordem": 2,
                "publicada": "on",
            },
        )
        self.assertRedirects(resposta, reverse("listar_trilhas"))
        self.assertTrue(
            TrilhaAprendizagem.objects.filter(titulo="Módulo 2 - Condicionais").exists()
        )

    def test_docente_nao_cria_trilha_em_turma_de_outro_docente(self):
        """Anti-tampering: POST forjado com turma alheia deve ser rejeitado."""
        resposta = self.client.post(
            reverse("criar_trilha"),
            {
                "turma": self.turma_alheia.pk,
                "titulo": "Trilha invasora",
                "descricao": "",
                "ordem": 1,
                "publicada": "on",
            },
        )
        self.assertEqual(resposta.status_code, 200)  # reexibe o form com erro
        self.assertFalse(
            TrilhaAprendizagem.objects.filter(titulo="Trilha invasora").exists()
        )

    def test_listagem_mostra_apenas_trilhas_do_proprio_docente(self):
        TrilhaAprendizagem.objects.create(
            turma=self.turma_alheia, titulo="Trilha do Bruno", ordem=1
        )
        resposta = self.client.get(reverse("listar_trilhas"))
        titulos = [t.titulo for t in resposta.context["trilhas"]]
        self.assertIn("Módulo 1 - Variáveis", titulos)
        self.assertNotIn("Trilha do Bruno", titulos)

    def test_docente_nao_edita_trilha_alheia(self):
        """Anti-IDOR: acesso direto por PK a objeto de terceiro retorna 404."""
        trilha_alheia = TrilhaAprendizagem.objects.create(
            turma=self.turma_alheia, titulo="Trilha do Bruno", ordem=1
        )
        resposta = self.client.get(reverse("editar_trilha", args=[trilha_alheia.pk]))
        self.assertEqual(resposta.status_code, 404)


class AtividadeDocenteTests(BaseSIMAPTestCase):
    def setUp(self):
        self.client.login(username="prof.ana", password=SENHA)

    def test_docente_publica_atividade_com_titulo_enunciado_tipo_e_prazo(self):
        prazo = timezone.now() + timedelta(days=7)
        resposta = self.client.post(
            reverse("criar_atividade"),
            {
                "trilha": self.trilha.pk,
                "titulo": "Lista de exercícios 1",
                "enunciado": "Resolva os exercícios do capítulo 1.",
                "tipo": "TEORICA",
                "ordem": 2,
                "prazo": prazo.strftime("%Y-%m-%dT%H:%M"),
                "publicada": "on",
            },
        )
        self.assertRedirects(resposta, reverse("listar_atividades"))
        nova = Atividade.objects.get(titulo="Lista de exercícios 1")
        self.assertEqual(nova.trilha, self.trilha)
        self.assertEqual(nova.tipo, "TEORICA")
        self.assertIsNotNone(nova.prazo)

    def test_prazo_no_passado_e_rejeitado_na_criacao(self):
        resposta = self.client.post(
            reverse("criar_atividade"),
            {
                "trilha": self.trilha.pk,
                "titulo": "Atividade com prazo vencido",
                "enunciado": "...",
                "tipo": "TEORICA",
                "ordem": 3,
                "prazo": (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "publicada": "on",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(
            Atividade.objects.filter(titulo="Atividade com prazo vencido").exists()
        )

    def test_docente_nao_publica_atividade_em_trilha_alheia(self):
        trilha_alheia = TrilhaAprendizagem.objects.create(
            turma=self.turma_alheia, titulo="Trilha do Bruno", ordem=1
        )
        self.client.post(
            reverse("criar_atividade"),
            {
                "trilha": trilha_alheia.pk,
                "titulo": "Atividade invasora",
                "enunciado": "...",
                "tipo": "TEORICA",
                "ordem": 1,
                "publicada": "on",
            },
        )
        self.assertFalse(Atividade.objects.filter(titulo="Atividade invasora").exists())


class MinhasTrilhasDiscenteTests(BaseSIMAPTestCase):
    def setUp(self):
        self.client.login(username="aluno.carla", password=SENHA)

    def test_discente_visualiza_apenas_trilhas_de_turmas_em_que_esta_matriculado(self):
        TrilhaAprendizagem.objects.create(
            turma=self.turma_alheia, titulo="Trilha não matriculada", publicada=True
        )
        resposta = self.client.get(reverse("minhas_trilhas"))
        titulos = [t.titulo for t in resposta.context["trilhas"]]
        self.assertIn("Módulo 1 - Variáveis", titulos)
        self.assertNotIn("Trilha não matriculada", titulos)

    def test_trilha_nao_publicada_fica_oculta_ao_discente(self):
        TrilhaAprendizagem.objects.create(
            turma=self.turma, titulo="Rascunho do docente", publicada=False
        )
        resposta = self.client.get(reverse("minhas_trilhas"))
        titulos = [t.titulo for t in resposta.context["trilhas"]]
        self.assertNotIn("Rascunho do docente", titulos)

    def test_atividade_nao_publicada_fica_oculta_ao_discente(self):
        Atividade.objects.create(
            trilha=self.trilha, titulo="Atividade rascunho", enunciado="...", publicada=False
        )
        resposta = self.client.get(reverse("minhas_trilhas"))
        trilha = resposta.context["trilhas"][0]
        titulos = [a.titulo for a in trilha.atividades_visiveis]
        self.assertNotIn("Atividade rascunho", titulos)

    def test_atividades_seguem_a_ordem_definida_na_trilha(self):
        Atividade.objects.create(
            trilha=self.trilha, titulo="Terceira", enunciado="...", ordem=3, publicada=True
        )
        Atividade.objects.create(
            trilha=self.trilha, titulo="Segunda", enunciado="...", ordem=2, publicada=True
        )
        resposta = self.client.get(reverse("minhas_trilhas"))
        trilha = resposta.context["trilhas"][0]
        ordens = [a.ordem for a in trilha.atividades_visiveis]
        self.assertEqual(ordens, sorted(ordens))
        self.assertEqual(
            [a.titulo for a in trilha.atividades_visiveis],
            ["Exercício de tipos primitivos", "Segunda", "Terceira"],
        )

    def test_discente_sem_matricula_ativa_nao_ve_trilhas(self):
        self.client.logout()
        self.client.login(username="aluno.diego", password=SENHA)
        resposta = self.client.get(reverse("minhas_trilhas"))
        self.assertEqual(len(resposta.context["trilhas"]), 0)

    def test_matricula_inativa_nao_da_acesso_as_trilhas(self):
        Matricula.objects.filter(discente=self.discente).update(status="INATIVA")
        resposta = self.client.get(reverse("minhas_trilhas"))
        self.assertEqual(len(resposta.context["trilhas"]), 0)


class ProgressoAtividadeTests(BaseSIMAPTestCase):
    """Critério de aceitação: progresso registrado por atividade concluída."""

    def setUp(self):
        self.client.login(username="aluno.carla", password=SENHA)
        self.url = reverse("concluir_atividade", args=[self.atividade.pk])

    def test_discente_marca_atividade_como_concluida(self):
        resposta = self.client.post(self.url)
        self.assertRedirects(resposta, reverse("minhas_trilhas"))
        self.assertTrue(
            ConclusaoAtividade.objects.filter(
                atividade=self.atividade, discente=self.discente
            ).exists()
        )

    def test_nova_requisicao_desfaz_a_conclusao(self):
        self.client.post(self.url)
        self.client.post(self.url)
        self.assertFalse(
            ConclusaoAtividade.objects.filter(
                atividade=self.atividade, discente=self.discente
            ).exists()
        )

    def test_conclusao_nao_pode_ser_duplicada(self):
        ConclusaoAtividade.objects.create(
            atividade=self.atividade, discente=self.discente
        )
        with self.assertRaises(IntegrityError):
            ConclusaoAtividade.objects.create(
                atividade=self.atividade, discente=self.discente
            )

    def test_percentual_de_progresso_e_calculado_por_trilha(self):
        Atividade.objects.create(
            trilha=self.trilha, titulo="Segunda", enunciado="...", ordem=2, publicada=True
        )
        self.client.post(self.url)

        resposta = self.client.get(reverse("minhas_trilhas"))
        trilha = resposta.context["trilhas"][0]
        self.assertEqual(trilha.total_visiveis, 2)
        self.assertEqual(trilha.total_concluidas, 1)
        self.assertEqual(trilha.percentual, 50)
        self.assertEqual(resposta.context["percentual_geral"], 50)

    def test_discente_nao_conclui_atividade_de_turma_em_que_nao_esta_matriculado(self):
        """Anti-IDOR no registro de progresso."""
        self.client.logout()
        self.client.login(username="aluno.diego", password=SENHA)
        resposta = self.client.post(self.url)
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(ConclusaoAtividade.objects.exists())

    def test_docente_nao_registra_progresso(self):
        self.client.logout()
        self.client.login(username="prof.ana", password=SENHA)
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_conclusao_exige_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_progresso_de_um_aluno_nao_afeta_o_de_outro(self):
        Matricula.objects.create(
            turma=self.turma, discente=self.outro_discente, status="ATIVA"
        )
        self.client.post(self.url)

        self.client.logout()
        self.client.login(username="aluno.diego", password=SENHA)
        resposta = self.client.get(reverse("minhas_trilhas"))
        self.assertEqual(resposta.context["total_concluidas"], 0)
