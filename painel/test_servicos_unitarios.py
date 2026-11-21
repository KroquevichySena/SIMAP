"""Cálculo dos indicadores do painel, sem banco: os dados da turma entram prontos."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from . import servicos

AGORA = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
ONTEM = AGORA - timedelta(days=1)
SEMANA_PASSADA = AGORA - timedelta(days=7)
AMANHA = AGORA + timedelta(days=1)


def _aluno(pk, nome=""):
    return SimpleNamespace(pk=pk, username=f"aluno{pk}", get_full_name=lambda: nome)


def _matricula(aluno_id, desde=SEMANA_PASSADA - timedelta(days=1)):
    return SimpleNamespace(discente_id=aluno_id, discente=_aluno(aluno_id), data_matricula=desde)


def _dados(**extra):
    dados = {
        "agora": AGORA,
        # duas chamadas já encerradas
        "chamadas": [(1, SEMANA_PASSADA), (2, ONTEM)],
        "presencas": {(10, 1), (10, 2), (20, 1)},
        # uma atividade vencida, uma com prazo no futuro e uma sem prazo
        "atividades": [(100, ONTEM), (101, AMANHA), (102, None)],
        "entregas": {(10, 100), (10, 101)},
        "conclusoes": {(10, 100)},
        "notas": {10: [8, 9], 20: []},
    }
    dados.update(extra)
    return dados


class IndicadoresDoAlunoTest(SimpleTestCase):
    def test_percentual_e_media_ignoram_total_zero_e_valores_nulos(self):
        self.assertIsNone(servicos._percentual(0, 0))
        self.assertEqual(servicos._percentual(1, 3), 33.3)
        self.assertIsNone(servicos._media([None, None]))
        self.assertEqual(servicos._media([8, None, 9]), 8.5)

    def test_aluno_presente_em_tudo(self):
        matricula, dados = _matricula(10), _dados()

        self.assertEqual(servicos.calcular_frequencia(matricula, dados), 100.0)
        self.assertEqual(servicos.contar_faltas(matricula, dados), 0)
        self.assertEqual(servicos.calcular_media(matricula, dados), 8.5)

    def test_atividade_do_futuro_so_conta_se_ja_foi_entregue(self):
        # A 101 vence amanhã: entra na conta do aluno 10 porque ele já entregou.
        self.assertEqual(servicos.calcular_taxa_entrega(_matricula(10), _dados()), 100.0)
        self.assertEqual(servicos.calcular_taxa_entrega(_matricula(20), _dados()), 0.0)

    def test_falta_e_frequencia_do_aluno_que_perdeu_uma_chamada(self):
        matricula, dados = _matricula(20), _dados()

        self.assertEqual(servicos.calcular_frequencia(matricula, dados), 50.0)
        self.assertEqual(servicos.contar_faltas(matricula, dados), 1)
        self.assertIsNone(servicos.calcular_media(matricula, dados))

    def test_chamada_anterior_a_matricula_nao_conta_como_falta(self):
        matricula = _matricula(30, desde=ONTEM - timedelta(hours=1))

        self.assertEqual(servicos.contar_faltas(matricula, _dados()), 1)
        self.assertEqual(servicos.calcular_frequencia(matricula, _dados()), 0.0)

    def test_aluno_abaixo_do_limite_fica_em_atencao(self):
        linha = servicos._indicadores(_matricula(20), _dados(), limite=60)

        self.assertTrue(linha["em_atencao"])
        self.assertEqual(linha["abaixo"], {"frequencia", "entregas", "progresso"})

    def test_valor_igual_ao_limite_nao_gera_alerta(self):
        linha = servicos._indicadores(_matricula(20), _dados(), limite=50)

        self.assertNotIn("frequencia", linha["abaixo"])

    def test_sem_nada_para_calcular_nao_ha_alerta(self):
        dados = _dados(chamadas=[], atividades=[])

        linha = servicos._indicadores(_matricula(20), dados, limite=60)

        self.assertIsNone(linha["frequencia"])
        self.assertFalse(linha["em_atencao"])


class TurmaTest(SimpleTestCase):
    def setUp(self):
        self.turma = SimpleNamespace(pk=1, limite_atencao=60)

    def _matriculas(self, *matriculas):
        consulta = mock.MagicMock()
        consulta.select_related.return_value.order_by.return_value = list(matriculas)
        consulta.select_related.return_value.first.return_value = matriculas[0] if matriculas else None
        return mock.patch.object(servicos.Matricula.objects, "filter", return_value=consulta)

    def test_alunos_em_atencao_aparecem_primeiro(self):
        with mock.patch.object(servicos, "_dados_da_turma", return_value=_dados()), \
                self._matriculas(_matricula(10), _matricula(20)):
            linhas = servicos.indicadores_da_turma(self.turma)
            em_atencao = servicos.listar_alunos_em_atencao(self.turma)

        self.assertEqual([linha["discente"].pk for linha in linhas], [20, 10])
        self.assertEqual([linha["discente"].pk for linha in em_atencao], [20])

    def test_indicadores_de_um_aluno(self):
        with mock.patch.object(servicos, "_dados_da_turma", return_value=_dados()), \
                self._matriculas(_matricula(10)):
            linha = servicos.indicadores_do_aluno(self.turma, _aluno(10))

        self.assertFalse(linha["em_atencao"])

    def test_aluno_sem_matricula_ativa_nao_tem_indicadores(self):
        with self._matriculas():
            self.assertIsNone(servicos.indicadores_do_aluno(self.turma, _aluno(99)))

    def test_resumo_da_turma(self):
        linhas = [
            {"frequencia": 100.0, "entregas": 100.0, "progresso": None, "media": 8.0, "em_atencao": False},
            {"frequencia": 50.0, "entregas": 0.0, "progresso": None, "media": None, "em_atencao": True},
        ]

        resumo = servicos.resumo_da_turma(linhas)

        self.assertEqual(resumo["frequencia"], 75.0)
        self.assertIsNone(resumo["progresso"])
        self.assertEqual((resumo["em_atencao"], resumo["total"]), (1, 2))

    def test_evolucao_marca_cada_chamada_e_prazo_vencido(self):
        matriculas = mock.MagicMock()
        matriculas.values_list.return_value = [(10, SEMANA_PASSADA - timedelta(days=1)), (20, AGORA)]
        notas = mock.MagicMock()
        notas.values_list.return_value = [(100, 8), (100, 6)]

        with mock.patch.object(servicos, "_dados_da_turma", return_value=_dados()), \
                mock.patch.object(servicos.Matricula.objects, "filter", return_value=matriculas), \
                mock.patch.object(servicos.AvaliacaoOficial.objects, "filter", return_value=notas):
            evolucao = servicos.evolucao_da_turma(self.turma)

        # semana passada (chamada 1) e ontem (chamada 2 + prazo da atividade 100)
        self.assertEqual(len(evolucao["rotulos"]), 2)
        self.assertEqual(evolucao["frequencia"], [100.0, 100.0])
        self.assertEqual(evolucao["notas"], [None, 7.0])

    def test_dados_do_grafico_convertem_para_o_chart_js(self):
        linhas = [{
            "discente": _aluno(10, "Ana Lima"), "frequencia": 100.0, "faltas": 0,
            "entregas": 50.0, "progresso": None, "media": 8.5, "em_atencao": False,
        }]
        evolucao = {"rotulos": ["19/11"], "frequencia": [100.0], "entregas": [50.0],
                    "progresso": [None], "notas": [7]}

        with mock.patch.object(servicos, "evolucao_da_turma", return_value=evolucao):
            grafico = servicos.dados_do_grafico(self.turma, linhas)

        self.assertEqual(grafico["alunos"][0]["nome"], "Ana Lima")
        self.assertEqual(grafico["evolucao"]["notas"], [7.0])
        self.assertEqual(grafico["limite"], 60.0)


class SituacaoDaEntregaTest(SimpleTestCase):
    def test_situacoes(self):
        vencida = SimpleNamespace(prazo=ONTEM)
        aberta = SimpleNamespace(prazo=AMANHA)

        self.assertEqual(servicos._situacao_da_entrega(vencida, SimpleNamespace(is_atrasado=True), AGORA), "atrasada")
        self.assertEqual(servicos._situacao_da_entrega(vencida, SimpleNamespace(is_atrasado=False), AGORA), "no_prazo")
        self.assertEqual(servicos._situacao_da_entrega(vencida, None, AGORA), "pendente")
        self.assertEqual(servicos._situacao_da_entrega(aberta, None, AGORA), "aberta")
