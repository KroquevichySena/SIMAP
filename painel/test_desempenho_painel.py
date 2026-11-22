"""Comparacao local das consultas do painel, usando apenas dados ficticios."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.models import Atividade, ConclusaoAtividade, TrilhaAprendizagem
from entregas.models import AvaliacaoOficial, Submissao
from turmas.models import Matricula, Turma
from usuarios.models import AceiteTermos

from . import servicos


class DesempenhoPainelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuarios = get_user_model()
        cls.docente = usuarios.objects.create_user(username="docente.ficticio", perfil="DOCENTE")
        cls.aluno = usuarios.objects.create_user(username="aluno.ficticio", perfil="DISCENTE")
        cls.outro = usuarios.objects.create_user(username="outro.docente", perfil="DOCENTE")
        cls.turma = Turma.objects.create(nome="Turma ficticia", periodo="2026/2", docente=cls.docente)
        cls.matricula = Matricula.objects.create(turma=cls.turma, discente=cls.aluno)
        trilha = TrilhaAprendizagem.objects.create(turma=cls.turma, titulo="Trilha ficticia")
        cls.agora = timezone.now()
        cls.atividade = Atividade.objects.create(
            trilha=trilha, titulo="Atividade ficticia", enunciado="Exercicio ficticio",
            prazo=cls.agora + timedelta(days=1),
        )
        cls.submissao = Submissao.objects.create(
            atividade=cls.atividade, aluno=cls.aluno, resposta_texto="Resposta ficticia",
        )
        AvaliacaoOficial.objects.create(submissao=cls.submissao, nota=8, feedback_professor="Feedback ficticio")
        ConclusaoAtividade.objects.create(atividade=cls.atividade, discente=cls.aluno)
        for usuario in (cls.docente, cls.aluno, cls.outro):
            AceiteTermos.objects.create(usuario=usuario, versao="1.3")

    def test_painel_docente_consulta_os_dados_uma_vez(self):
        self.client.force_login(self.docente)
        with patch("painel.servicos.timezone.now", return_value=self.agora):
            with CaptureQueriesContext(connection) as consultas:
                resposta = self.client.get(reverse("painel:docente"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["resumo"]["total"], 1)
        self.assertEqual(resposta.context["resumo"]["entregas"], 100)
        self.assertEqual(resposta.context["resumo"]["progresso"], 100)
        self.assertEqual(float(resposta.context["resumo"]["media"]), 8)
        self.assertEqual(resposta.context["dados_grafico"]["alunos"][0]["id"], self.aluno.pk)
        leituras = [
            q["sql"] for q in consultas.captured_queries
            if q["sql"].startswith("SELECT") and 'FROM "chamada_chamada"' in q["sql"]
        ]
        print("PAINEL: consultas totais =", len(consultas), "; leituras de chamadas =", len(leituras))
        self.assertEqual(len(leituras), 1)

    def test_painel_sem_turma_continua_disponivel(self):
        self.client.force_login(self.outro)
        resposta = self.client.get(reverse("painel:docente"))
        self.assertEqual(resposta.status_code, 200)
        self.assertIsNone(resposta.context["turma"])

    def test_docente_nao_consulta_turma_alheia(self):
        self.client.force_login(self.outro)
        resposta = self.client.get(reverse("painel:docente"), {"turma": self.turma.pk})
        self.assertEqual(resposta.status_code, 404)

    def test_discente_nao_acessa_painel_docente(self):
        self.client.force_login(self.aluno)
        self.assertEqual(self.client.get(reverse("painel:docente")).status_code, 403)

    def test_dados_reutilizados_preservam_o_resultado_anterior(self):
        with patch("painel.servicos.timezone.now", return_value=self.agora):
            linhas = servicos.indicadores_da_turma(self.turma)
            anterior = {
                "linhas": linhas,
                "resumo": servicos.resumo_da_turma(linhas),
                "dados_grafico": servicos.dados_do_grafico(self.turma, linhas),
            }
            self.assertEqual(servicos.dados_do_painel_docente(self.turma), anterior)

    def test_nao_reutiliza_dados_entre_consultas_distintas(self):
        self.assertEqual(servicos.dados_do_painel_docente(self.turma)["resumo"]["total"], 1)
        self.matricula.status = "INATIVA"
        self.matricula.save(update_fields=["status"])
        self.assertEqual(servicos.dados_do_painel_docente(self.turma)["resumo"]["total"], 0)
