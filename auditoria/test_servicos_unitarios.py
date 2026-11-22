"""Regras do serviço de auditoria, sem banco: o que é escondido, cortado e como a falha é tratada."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from . import servicos
from .contexto import ContextoRequisicao
from .models import Acao


def _usuario(login="maria"):
    return SimpleNamespace(get_username=lambda: login)


class _Instancia:
    """Imita um objeto de modelo: só o que o serviço lê dele."""

    def __init__(self, pk=7, texto="Atividade 1", quebra=False):
        self.pk = pk
        self._meta = SimpleNamespace(label="core.Atividade", verbose_name="atividade")
        self._texto = texto
        self._quebra = quebra

    def __str__(self):
        if self._quebra:
            raise RuntimeError("relacionado já apagado")
        return self._texto


@mock.patch.object(servicos.transaction, "atomic", mock.MagicMock())
@mock.patch.object(servicos.RegistroAuditoria.objects, "create")
class RegistrarTest(SimpleTestCase):
    def test_grava_usuario_e_dados_da_requisicao(self, create):
        ctx = ContextoRequisicao(ip="10.0.0.1", user_agent="Chrome", metodo="POST", caminho="/turmas/")

        servicos.registrar(Acao.LOGIN, usuario=_usuario(), ctx=ctx, descricao="Login realizado.")

        campos = create.call_args.kwargs
        self.assertEqual(campos["usuario_login"], "maria")
        self.assertEqual(campos["ip"], "10.0.0.1")
        self.assertEqual(campos["caminho"], "/turmas/")
        self.assertEqual(campos["acao"], Acao.LOGIN)

    def test_usuario_vem_do_contexto_quando_nao_e_informado(self, create):
        ctx = ContextoRequisicao(usuario=_usuario("docente"))

        servicos.registrar(Acao.ACESSO, ctx=ctx)

        self.assertEqual(create.call_args.kwargs["usuario_login"], "docente")

    def test_login_com_falha_guarda_so_o_nome_digitado(self, create):
        servicos.registrar(Acao.LOGIN_FALHA, usuario_login="x" * 300)

        campos = create.call_args.kwargs
        self.assertNotIn("usuario", campos)
        self.assertEqual(len(campos["usuario_login"]), 150)

    def test_fora_de_requisicao_fica_sem_usuario_e_sem_ip(self, create):
        servicos.registrar(Acao.EXPURGO, descricao="d" * 400)

        campos = create.call_args.kwargs
        self.assertNotIn("usuario_login", campos)
        self.assertNotIn("ip", campos)
        self.assertEqual(len(campos["descricao"]), 255)

    def test_instancia_preenche_entidade_id_e_nome(self, create):
        servicos.registrar(Acao.CRIACAO, instancia=_Instancia())

        campos = create.call_args.kwargs
        self.assertEqual(campos["entidade"], "core.Atividade")
        self.assertEqual(campos["objeto_id"], "7")
        self.assertEqual(campos["objeto_repr"], "Atividade 1")

    def test_exclusao_usa_a_foto_tirada_antes_de_apagar(self, create):
        alvo = {"entidade": "turmas.Turma", "pk": 3, "repr": "Turma A"}

        servicos.registrar(Acao.EXCLUSAO, alvo=alvo)

        campos = create.call_args.kwargs
        self.assertEqual((campos["entidade"], campos["objeto_id"], campos["objeto_repr"]),
                         ("turmas.Turma", "3", "Turma A"))

    def test_falha_ao_gravar_nao_derruba_o_sistema(self, create):
        create.side_effect = RuntimeError("banco fora do ar")

        with self.assertLogs("simap.auditoria", level="ERROR"):
            resultado = servicos.registrar(Acao.LOGIN, usuario=_usuario())

        self.assertIsNone(resultado)


class DadosSensiveisTest(SimpleTestCase):
    def test_campos_de_senha_e_token_sao_escondidos(self):
        for nome in ("password", "nova_senha", "token_chamada", "API_KEY", "client_secret"):
            with self.subTest(nome=nome):
                self.assertEqual(servicos.valor_para_json(nome, "segredo"), "***")

    def test_campo_comum_nao_e_sensivel(self):
        self.assertFalse(servicos.campo_sensivel("titulo"))

    def test_numeros_booleanos_e_nulo_ficam_como_estao(self):
        for valor in (None, True, 10, 7.5):
            with self.subTest(valor=valor):
                self.assertEqual(servicos.valor_para_json("nota", valor), valor)

    def test_texto_longo_e_cortado(self):
        valor = servicos.valor_para_json("resposta", "a" * 500)

        self.assertEqual(len(valor), servicos.LIMITE_VALOR + 1)
        self.assertTrue(valor.endswith("…"))

    def test_nome_do_objeto_tem_alternativa_quando_o_str_falha(self):
        self.assertEqual(servicos._repr_seguro(_Instancia(pk=9, quebra=True)), "atividade #9")
