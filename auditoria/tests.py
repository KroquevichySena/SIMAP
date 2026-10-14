"""
Testes da auditoria/log de acessos e ações do usuário.
"""
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Atividade, ConclusaoAtividade, TrilhaAprendizagem
from usuarios.models import AceiteTermos
from turmas.models import Matricula, Turma

from .contexto import obter_ip
from .models import Acao, RegistroAuditoria, RegistroImutavelError

Usuario = get_user_model()
SENHA = "SenhaDeTeste123"
NAVEGADOR = "Mozilla/5.0 (Teste SIMAP)"


class BaseAuditoriaTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(
            username="prof.ana", password=SENHA, perfil="DOCENTE"
        )
        cls.discente = Usuario.objects.create_user(
            username="aluno.carla", password=SENHA, perfil="DISCENTE"
        )
        cls.coordenador = Usuario.objects.create_superuser(
            username="coord", password=SENHA, perfil="DOCENTE"
        )
        cls.turma = Turma.objects.create(
            nome="Algoritmos I", periodo="2026.2", docente=cls.docente
        )
        Matricula.objects.create(turma=cls.turma, discente=cls.discente)
        cls.trilha = TrilhaAprendizagem.objects.create(turma=cls.turma, titulo="Módulo 1")
        cls.atividade = Atividade.objects.create(
            trilha=cls.trilha, titulo="Exercício 1", enunciado="Descreva."
        )

    def setUp(self):
        # Descarta os registros gerados pela montagem do cenário.
        RegistroAuditoria.objects.all().delete()
        self.client.defaults["HTTP_USER_AGENT"] = NAVEGADOR

    def registros(self, **filtros):
        return RegistroAuditoria.objects.filter(**filtros)


class AutenticacaoTests(BaseAuditoriaTestCase):
    def test_login_registra_usuario_ip_e_navegador(self):
        # O login do admin só aceita a equipe, por isso usamos o coordenador.
        self.client.post(reverse("admin:login"), {"username": "coord", "password": SENHA})
        registro = self.registros(acao=Acao.LOGIN).get()
        self.assertEqual(registro.usuario, self.coordenador)
        self.assertEqual(registro.usuario_login, "coord")
        self.assertEqual(registro.ip, "127.0.0.1")
        self.assertEqual(registro.user_agent, NAVEGADOR)

    def test_login_com_falha_registra_login_digitado_sem_a_senha(self):
        self.client.post(reverse("admin:login"), {"username": "prof.ana", "password": "errada!"})
        registro = self.registros(acao=Acao.LOGIN_FALHA).get()
        self.assertIsNone(registro.usuario)
        self.assertEqual(registro.usuario_login, "prof.ana")
        # A senha digitada não pode aparecer em lugar nenhum do registro.
        conteudo = " ".join(str(v) for v in registro.__dict__.values())
        self.assertNotIn("errada!", conteudo)

    def test_logout_registrado(self):
        self.client.login(username="coord", password=SENHA)
        self.client.post(reverse("admin:logout"))
        self.assertTrue(self.registros(acao=Acao.LOGOUT, usuario=self.coordenador).exists())

    def test_atualizacao_do_ultimo_login_nao_gera_alteracao(self):
        self.client.login(username="prof.ana", password=SENHA)
        self.assertFalse(self.registros(acao=Acao.ALTERACAO).exists())


class AceiteDosTermosTests(BaseAuditoriaTestCase):
    """O login pela tela do SIMAP exige aceitar os termos, e o aceite fica registrado."""

    url = reverse("login")

    def test_login_sem_aceitar_os_termos_e_barrado(self):
        resposta = self.client.post(self.url, {"username": "prof.ana", "password": SENHA})
        self.assertEqual(resposta.status_code, 200)  # a tela volta com o erro
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(AceiteTermos.objects.filter(usuario=self.docente).exists())

    def test_aceite_e_gravado_com_a_versao_e_entra_na_auditoria(self):
        self.client.post(self.url, {
            "username": "prof.ana", "password": SENHA, "aceite_termos": "on",
        })
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.docente.pk)
        aceite = AceiteTermos.objects.get(usuario=self.docente)
        self.assertEqual(aceite.versao, settings.TERMOS_DE_USO_VERSAO)
        registro = self.registros(acao=Acao.CRIACAO, entidade="usuarios.AceiteTermos").get()
        self.assertEqual(registro.usuario, self.docente)

    def test_quem_ja_aceitou_a_versao_atual_nao_precisa_marcar_de_novo(self):
        AceiteTermos.objects.create(usuario=self.docente, versao=settings.TERMOS_DE_USO_VERSAO)
        self.client.post(self.url, {"username": "prof.ana", "password": SENHA})
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.docente.pk)


class AcessoTests(BaseAuditoriaTestCase):
    def test_acesso_a_pagina_por_usuario_autenticado(self):
        self.client.force_login(self.docente)
        self.client.get(reverse("core:trilha_list"))
        registro = self.registros(acao=Acao.ACESSO).get()
        self.assertEqual(registro.usuario, self.docente)
        self.assertEqual(registro.caminho, reverse("core:trilha_list"))
        self.assertEqual(registro.metodo, "GET")
        self.assertEqual(registro.status_http, 200)

    def test_visitante_nao_gera_registro_de_acesso(self):
        self.client.get(reverse("core:trilha_list"))
        self.assertFalse(self.registros(acao=Acao.ACESSO).exists())

    def test_arquivos_estaticos_sao_ignorados(self):
        self.client.force_login(self.docente)
        self.client.get("/static/css/qualquer.css")
        self.client.get("/favicon.ico")
        self.assertFalse(self.registros(acao=Acao.ACESSO).exists())

    def test_acesso_negado_e_registrado(self):
        """Discente tentando abrir rota exclusiva do docente."""
        self.client.force_login(self.discente)
        resposta = self.client.get(reverse("core:trilha_list"))
        self.assertEqual(resposta.status_code, 403)
        registro = self.registros(acao=Acao.ACESSO_NEGADO).get()
        self.assertEqual(registro.usuario, self.discente)
        self.assertEqual(registro.status_http, 403)

    def test_tentativa_de_idor_fica_registrada(self):
        """Discente forçando a exclusão de uma trilha pelo ID."""
        self.client.force_login(self.discente)
        self.client.post(reverse("core:trilha_delete", args=[self.trilha.pk]))
        self.assertTrue(TrilhaAprendizagem.objects.filter(pk=self.trilha.pk).exists())
        self.assertTrue(self.registros(acao=Acao.ACESSO_NEGADO, usuario=self.discente).exists())


class AlteracaoDeDadosTests(BaseAuditoriaTestCase):
    def test_criacao_pela_tela_registra_autor(self):
        self.client.force_login(self.docente)
        self.client.post(reverse("core:trilha_create"), {
            "turma": self.turma.pk, "titulo": "Módulo 2", "descricao": "",
            "ordem": 2, "publicada": "on",
        })
        nova = TrilhaAprendizagem.objects.get(titulo="Módulo 2")
        registro = self.registros(acao=Acao.CRIACAO, entidade="core.TrilhaAprendizagem").get()
        self.assertEqual(registro.usuario, self.docente)
        self.assertEqual(registro.objeto_id, str(nova.pk))
        self.assertEqual(registro.dados["titulo"], "Módulo 2")
        self.assertEqual(registro.metodo, "POST")

    def test_alteracao_guarda_somente_campos_alterados_com_antes_e_depois(self):
        self.client.force_login(self.docente)
        self.client.post(reverse("core:atividade_update", args=[self.atividade.pk]), {
            "trilha": self.trilha.pk, "titulo": "Exercício 1 revisado",
            "enunciado": "Descreva.", "tipo": "TEORICA", "ordem": 1, "publicada": "on",
        })
        registro = self.registros(acao=Acao.ALTERACAO, entidade="core.Atividade").get()
        self.assertEqual(
            registro.dados,
            {"titulo": {"antes": "Exercício 1", "depois": "Exercício 1 revisado"}},
        )

    def test_salvar_sem_mudancas_nao_gera_registro(self):
        self.atividade.save()
        self.assertFalse(self.registros(acao=Acao.ALTERACAO).exists())

    def test_exclusao_registra_objeto_e_exclusoes_em_cascata(self):
        self.client.force_login(self.docente)
        pk_trilha, pk_atividade = self.trilha.pk, self.atividade.pk
        self.client.post(reverse("core:trilha_delete", args=[pk_trilha]))

        trilha = self.registros(acao=Acao.EXCLUSAO, entidade="core.TrilhaAprendizagem").get()
        self.assertEqual(trilha.objeto_id, str(pk_trilha))
        self.assertEqual(trilha.objeto_repr, "Módulo 1")
        self.assertEqual(trilha.usuario, self.docente)
        # A atividade apagada em cascata também fica registrada.
        self.assertTrue(self.registros(
            acao=Acao.EXCLUSAO, entidade="core.Atividade", objeto_id=str(pk_atividade)
        ).exists())

    def test_conclusao_de_atividade_pelo_discente(self):
        self.client.force_login(self.discente)
        self.client.post(reverse("core:atividade_concluir", args=[self.atividade.pk]))
        conclusao = ConclusaoAtividade.objects.get()
        registro = self.registros(acao=Acao.CRIACAO, entidade="core.ConclusaoAtividade").get()
        self.assertEqual(registro.objeto_id, str(conclusao.pk))
        self.assertEqual(registro.usuario, self.discente)

    def test_senha_nunca_e_gravada(self):
        self.docente.set_password("NovaSenha456!")
        self.docente.save()
        registro = self.registros(acao=Acao.ALTERACAO, entidade="usuarios.Usuario").get()
        self.assertEqual(registro.dados["password"], {"antes": "***", "depois": "***"})

    def test_acao_fora_de_requisicao_fica_como_sistema(self):
        Turma.objects.create(nome="Banco de Dados", periodo="2026.2", docente=self.docente)
        registro = self.registros(acao=Acao.CRIACAO, entidade="turmas.Turma").get()
        self.assertIsNone(registro.usuario)
        self.assertEqual(registro.origem, "sistema")


class ImutabilidadeTests(BaseAuditoriaTestCase):
    def test_registro_nao_pode_ser_alterado(self):
        registro = RegistroAuditoria.objects.create(acao=Acao.ACESSO)
        registro.descricao = "adulterado"
        with self.assertRaises(RegistroImutavelError):
            registro.save()

    def test_registro_nao_pode_ser_excluido_individualmente(self):
        registro = RegistroAuditoria.objects.create(acao=Acao.ACESSO)
        with self.assertRaises(RegistroImutavelError):
            registro.delete()

    def test_admin_e_somente_leitura(self):
        self.client.force_login(self.coordenador)
        url = reverse("admin:auditoria_registroauditoria_changelist")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin:auditoria_registroauditoria_add")).status_code, 403
        )


class ResilienciaTests(BaseAuditoriaTestCase):
    def test_falha_na_auditoria_nao_derruba_a_requisicao(self):
        self.client.force_login(self.docente)
        with mock.patch(
            "auditoria.servicos.RegistroAuditoria.objects.create",
            side_effect=RuntimeError("banco de auditoria fora do ar"),
        ), self.assertLogs("simap.auditoria", level="ERROR"):
            resposta = self.client.get(reverse("core:trilha_list"))
        self.assertEqual(resposta.status_code, 200)


class IpTests(TestCase):
    def _request(self, remote, encaminhado=None):
        from django.test import RequestFactory

        meta = {"REMOTE_ADDR": remote}
        if encaminhado:
            meta["HTTP_X_FORWARDED_FOR"] = encaminhado
        return RequestFactory().get("/", **meta)

    @override_settings(AUDITORIA_PROXIES_CONFIAVEIS=0)
    def test_sem_proxy_ignora_cabecalho_que_pode_ser_forjado(self):
        request = self._request("10.0.0.5", encaminhado="1.2.3.4")
        self.assertEqual(obter_ip(request), "10.0.0.5")

    @override_settings(AUDITORIA_PROXIES_CONFIAVEIS=1)
    def test_com_proxy_usa_ip_anexado_pelo_proxy(self):
        # O cliente tentou forjar "6.6.6.6"; o proxy anexou o IP real no fim.
        request = self._request("10.0.0.1", encaminhado="6.6.6.6, 200.100.50.25")
        self.assertEqual(obter_ip(request), "200.100.50.25")

    @override_settings(AUDITORIA_PROXIES_CONFIAVEIS=1)
    def test_ip_invalido_no_cabecalho_cai_para_remote_addr(self):
        request = self._request("10.0.0.1", encaminhado="<script>")
        self.assertEqual(obter_ip(request), "10.0.0.1")


class ConsultaTests(BaseAuditoriaTestCase):
    url = reverse("auditoria:registro_list")

    def test_coordenacao_consulta(self):
        self.client.force_login(self.coordenador)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_docente_nao_consulta(self):
        self.client.force_login(self.docente)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_visitante_vai_para_o_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_filtro_por_acao(self):
        RegistroAuditoria.objects.create(acao=Acao.LOGIN_FALHA, usuario_login="intruso")
        RegistroAuditoria.objects.create(acao=Acao.LOGIN, usuario_login="prof.ana")
        self.client.force_login(self.coordenador)
        resposta = self.client.get(self.url, {"acao": Acao.LOGIN_FALHA})
        logins = {r.usuario_login for r in resposta.context["registros"]}
        self.assertEqual(logins, {"intruso"})

    def test_filtro_por_periodo(self):
        antigo = RegistroAuditoria.objects.create(
            acao=Acao.LOGIN, usuario_login="antigo",
            data_hora=timezone.now() - timedelta(days=10),
        )
        self.client.force_login(self.coordenador)
        hoje = timezone.localdate().isoformat()
        resposta = self.client.get(self.url, {"de": hoje, "acao": Acao.LOGIN})
        self.assertNotIn(antigo, resposta.context["registros"])

    def test_exportacao_csv_neutraliza_formulas(self):
        RegistroAuditoria.objects.create(
            acao=Acao.LOGIN_FALHA, usuario_login='=HYPERLINK("http://mal.example")'
        )
        self.client.force_login(self.coordenador)
        resposta = self.client.get(self.url, {"formato": "csv"})
        conteudo = b"".join(resposta.streaming_content).decode("utf-8")
        self.assertIn("'=HYPERLINK", conteudo)
        self.assertNotIn(";=HYPERLINK", conteudo)


class RetencaoTests(BaseAuditoriaTestCase):
    def _criar(self, dias_atras):
        return RegistroAuditoria.objects.create(
            acao=Acao.ACESSO, data_hora=timezone.now() - timedelta(days=dias_atras)
        )

    def test_remove_apenas_registros_fora_do_prazo_e_registra_o_expurgo(self):
        antigo, recente = self._criar(200), self._criar(10)
        call_command("limpar_auditoria", dias=180, stdout=StringIO())
        self.assertFalse(RegistroAuditoria.objects.filter(pk=antigo.pk).exists())
        self.assertTrue(RegistroAuditoria.objects.filter(pk=recente.pk).exists())
        expurgo = RegistroAuditoria.objects.get(acao=Acao.EXPURGO)
        self.assertEqual(expurgo.dados, {"removidos": 1, "retencao_dias": 180})

    def test_simulacao_nao_remove_nada(self):
        self._criar(200)
        call_command("limpar_auditoria", dias=180, simular=True, stdout=StringIO())
        self.assertEqual(RegistroAuditoria.objects.count(), 1)
