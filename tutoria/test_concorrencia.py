"""
Pedidos de ajuda simultâneos do mesmo aluno.

Antes da correção, os limites eram conferidos antes de chamar o Gemini, mas o
pedido só era gravado depois da resposta. Dois pedidos que chegassem juntos
passavam os dois pela conferência e estouravam o limite. Agora o pedido é
reservado ("em andamento") de forma atômica antes da chamada à IA.
"""
import threading
import time
from datetime import timedelta
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core.models import TIPO_PRATICA, Atividade

from . import gemini, servicos
from .models import PedidoDeAjuda
from .tests import TutoriaBase

Tipo = PedidoDeAjuda.Tipo
Status = PedidoDeAjuda.Status


class PedidoQueChegaDuranteAResposta:
    """
    Faz o papel do Gemini e, no meio da resposta ao primeiro pedido, dispara um
    segundo pedido do mesmo aluno, como se ele tivesse clicado de novo (ou
    aberto outra aba) enquanto a IA ainda pensava.
    """

    def __init__(self, aluno, atividade, tipo, nivel=0):
        self.segundo = dict(aluno=aluno, atividade=atividade, tipo=tipo, nivel=nivel)
        self.recusa = None
        self.disparou = False

    def __call__(self, instrucoes, conteudo, buscar_na_web=False, max_tokens=700):
        if instrucoes == servicos.VERIFICADOR:
            return gemini.RespostaDaIA(texto="NÃO")
        if not self.disparou:
            self.disparou = True
            try:
                servicos.pedir_ajuda(**self.segundo)
            except servicos.PedidoRecusado as motivo:
                self.recusa = str(motivo)
        return gemini.RespostaDaIA(texto="Pense no que se repete.")


class PedidoEmAndamentoContaNoLimiteTest(TutoriaBase):

    def disputar(self, primeiro, segundo):
        ia = PedidoQueChegaDuranteAResposta(self.aluno, self.pratica, **segundo)
        with mock.patch("tutoria.gemini.perguntar", ia):
            servicos.pedir_ajuda(self.aluno, self.pratica, **primeiro)
        return ia

    @override_settings(TUTORIA_PEDIDOS_POR_DIA=1)
    def test_limite_diario_de_um_aceita_so_um_pedido(self):
        ia = self.disputar({"tipo": Tipo.CONCEITO}, {"tipo": Tipo.MATERIAL})
        self.assertIn("todas as ajudas de hoje", ia.recusa)
        self.assertEqual(PedidoDeAjuda.objects.count(), 1)
        self.assertEqual(PedidoDeAjuda.objects.get().status, Status.RESPONDIDO)

    @override_settings(TUTORIA_INTERVALO_SEGUNDOS=15)
    def test_intervalo_vale_para_pedido_ainda_sem_resposta(self):
        ia = self.disputar({"tipo": Tipo.CONCEITO}, {"tipo": Tipo.MATERIAL})
        self.assertIn("Aguarde", ia.recusa)
        self.assertEqual(PedidoDeAjuda.objects.count(), 1)

    @override_settings(TUTORIA_DICAS_POR_NIVEL=1)
    def test_mesma_dica_nao_e_entregue_duas_vezes(self):
        Atividade.objects.filter(pk=self.pratica.pk).update(ajuda_ia_nivel_maximo=1)
        self.pratica.refresh_from_db()
        ia = self.disputar({"tipo": Tipo.DICA, "nivel": 1}, {"tipo": Tipo.DICA, "nivel": 1})
        self.assertIn("todas as dicas", ia.recusa)
        self.assertEqual(PedidoDeAjuda.objects.filter(tipo=Tipo.DICA).count(), 1)

    @override_settings(TUTORIA_PEDIDOS_POR_DIA=1)
    def test_falha_da_ia_libera_a_vaga_reservada(self):
        with mock.patch("tutoria.gemini.perguntar", side_effect=gemini.IAIndisponivel("fora do ar")):
            pedido = servicos.pedir_ajuda(self.aluno, self.pratica, Tipo.CONCEITO)
        self.assertEqual(pedido.status, Status.ERRO)
        with mock.patch("tutoria.gemini.perguntar", return_value=gemini.RespostaDaIA(texto="Ok.")):
            self.assertEqual(servicos.pedir_ajuda(self.aluno, self.pratica, Tipo.MATERIAL).status, Status.RESPONDIDO)

    @override_settings(TUTORIA_PEDIDOS_POR_DIA=1)
    def test_erro_inesperado_tambem_libera_a_vaga(self):
        with mock.patch("tutoria.gemini.perguntar", side_effect=RuntimeError("bug")):
            with self.assertRaises(RuntimeError):
                servicos.pedir_ajuda(self.aluno, self.pratica, Tipo.CONCEITO)
        self.assertEqual(PedidoDeAjuda.objects.get().status, Status.ERRO)
        self.assertEqual(servicos.situacao(self.aluno, self.pratica).restantes_hoje, 1)

    @override_settings(TUTORIA_PEDIDOS_POR_DIA=1)
    def test_reserva_abandonada_deixa_de_contar(self):
        reserva = PedidoDeAjuda.objects.create(
            aluno=self.aluno, atividade=self.pratica, tipo=Tipo.CONCEITO, status=Status.EM_ANDAMENTO
        )
        self.assertEqual(servicos.situacao(self.aluno, self.pratica).restantes_hoje, 0)
        PedidoDeAjuda.objects.filter(pk=reserva.pk).update(
            criado_em=timezone.now() - servicos.RESERVA_EXPIRA - timedelta(seconds=1)
        )
        self.assertEqual(servicos.situacao(self.aluno, self.pratica).restantes_hoje, 1)

    def test_reserva_em_andamento_nao_aparece_para_aluno_nem_professor(self):
        PedidoDeAjuda.objects.create(aluno=self.aluno, atividade=self.pratica, tipo=Tipo.CONCEITO,
                                     status=Status.EM_ANDAMENTO)
        self.assertEqual(servicos.resumo_para_o_professor(self.pratica), {})
        self.entrar(self.aluno)
        from django.urls import reverse

        resposta = self.client.get(reverse("entregas:resolver", args=[self.pratica.pk]))
        self.assertNotContains(resposta, "pedido-de-ajuda border")


@override_settings(TUTORIA_INTERVALO_SEGUNDOS=0, TUTORIA_PEDIDOS_POR_DIA=1, TUTORIA_DICAS_POR_NIVEL=2)
class DuasRequisicoesAoMesmoTempoTest(TransactionTestCase):
    """
    Duas threads, cada uma com a sua conexão ao banco, pedem ajuda no mesmo
    instante. A IA demora para responder, como na vida real. Com limite de um
    pedido por dia, só um pode ser aceito.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model

        from core.models import TrilhaAprendizagem
        from turmas.models import Matricula, Turma

        usuario = get_user_model()
        prof = usuario.objects.create_user("prof.conc", password="x", perfil="DOCENTE")
        self.aluno = usuario.objects.create_user("aluno.conc", password="x", perfil="DISCENTE")
        turma = Turma.objects.create(nome="Concorrência", periodo="2026.2", docente=prof)
        Matricula.objects.create(turma=turma, discente=self.aluno)
        trilha = TrilhaAprendizagem.objects.create(turma=turma, titulo="T", ordem=1, publicada=True)
        self.atividade = Atividade.objects.create(trilha=trilha, titulo="A", enunciado="x", ordem=1,
                                                  tipo=TIPO_PRATICA)

    def test_duas_requisicoes_simultaneas_respeitam_o_limite_de_um(self):
        largada = threading.Barrier(2)
        aceitos, recusados, falhas = [], [], []

        def ia_lenta(instrucoes, conteudo, buscar_na_web=False, max_tokens=700):
            if instrucoes == servicos.VERIFICADOR:
                return gemini.RespostaDaIA(texto="NÃO")
            time.sleep(0.3)
            return gemini.RespostaDaIA(texto="Pense no que se repete.")

        def pedir(tipo):
            try:
                largada.wait(timeout=5)
                servicos.pedir_ajuda(self.aluno, self.atividade, tipo)
                aceitos.append(tipo)
            except servicos.PedidoRecusado:
                recusados.append(tipo)
            except Exception as erro:  # o teste mostra qualquer outro problema
                falhas.append(repr(erro))
            finally:
                connection.close()

        with mock.patch("tutoria.gemini.perguntar", ia_lenta):
            threads = [threading.Thread(target=pedir, args=(t,)) for t in (Tipo.CONCEITO, Tipo.MATERIAL)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=20)

        self.assertEqual(falhas, [])
        self.assertEqual(len(aceitos), 1, f"aceitos={aceitos} recusados={recusados}")
        self.assertEqual(len(recusados), 1)
        self.assertEqual(PedidoDeAjuda.objects.exclude(status=Status.ERRO).count(), 1)
