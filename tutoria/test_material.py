"""Busca de material quando a busca na web do Gemini não está disponível."""
from unittest import mock

from django.test import override_settings

from . import gemini, servicos
from .models import PedidoDeAjuda
from .tests import TutoriaBase

Status = PedidoDeAjuda.Status


class IASemBusca:
    """Recusa a busca na web (como a cota da chave gratuita) e responde o resto."""

    def __init__(self, busca_recusada=True, sem_busca_falha=False):
        self.busca_recusada = busca_recusada
        self.sem_busca_falha = sem_busca_falha
        self.pedidos = []

    def __call__(self, instrucoes, conteudo, buscar_na_web=False, max_tokens=700):
        self.pedidos.append({"instrucoes": instrucoes, "web": buscar_na_web})
        if buscar_na_web and self.busca_recusada:
            raise gemini.IAIndisponivel("429 RESOURCE_EXHAUSTED: grounding")
        if not buscar_na_web and self.sem_busca_falha:
            raise gemini.IAIndisponivel("fora do ar")
        if buscar_na_web:
            return gemini.RespostaDaIA(
                texto="1. Tutorial oficial: laços.",
                fontes=[{"titulo": "docs.python.org", "url": "https://docs.python.org/pt-br/3/tutorial/"}],
            )
        return gemini.RespostaDaIA(texto="1. Tutorial oficial do Python (docs.python.org): laços for e while.")


class MaterialSemBuscaTest(TutoriaBase):

    def pedir_material(self, ia):
        with mock.patch("tutoria.gemini.perguntar", ia):
            return servicos.pedir_ajuda(self.aluno, self.pratica, PedidoDeAjuda.Tipo.MATERIAL)

    def test_busca_recusada_cai_para_indicacao_sem_busca(self):
        ia = IASemBusca()
        pedido = self.pedir_material(ia)
        self.assertEqual([p["web"] for p in ia.pedidos], [True, False])
        self.assertIn(servicos.TAREFA_MATERIAL_SEM_BUSCA, ia.pedidos[1]["instrucoes"])
        self.assertNotIn(servicos.TAREFAS[(PedidoDeAjuda.Tipo.MATERIAL, 0)], ia.pedidos[1]["instrucoes"])
        self.assertEqual(pedido.status, Status.RESPONDIDO)
        self.assertIn("docs.python.org", pedido.resposta)
        self.assertTrue(pedido.resposta.endswith(servicos.AVISO_SEM_BUSCA))
        self.assertEqual(pedido.fontes, [])

    def test_regras_continuam_nas_instrucoes_sem_busca(self):
        ia = IASemBusca()
        self.pedir_material(ia)
        self.assertIn("Nunca entregue a solução", ia.pedidos[1]["instrucoes"])

    @override_settings(TUTORIA_BUSCA_NA_WEB=False)
    def test_busca_desligada_nem_tenta_buscar(self):
        ia = IASemBusca()
        pedido = self.pedir_material(ia)
        self.assertEqual([p["web"] for p in ia.pedidos], [False])
        self.assertTrue(pedido.resposta.endswith(servicos.AVISO_SEM_BUSCA))

    def test_com_busca_funcionando_nada_muda(self):
        ia = IASemBusca(busca_recusada=False)
        pedido = self.pedir_material(ia)
        self.assertEqual([p["web"] for p in ia.pedidos], [True])
        self.assertNotIn(servicos.AVISO_SEM_BUSCA, pedido.resposta)
        self.assertEqual(len(pedido.fontes), 1)

    @override_settings(TUTORIA_PEDIDOS_POR_DIA=1)
    def test_se_as_duas_falharem_e_erro_e_nao_gasta_a_cota(self):
        pedido = self.pedir_material(IASemBusca(sem_busca_falha=True))
        self.assertEqual(pedido.status, Status.ERRO)
        self.assertEqual(servicos.situacao(self.aluno, self.pratica).restantes_hoje, 1)
