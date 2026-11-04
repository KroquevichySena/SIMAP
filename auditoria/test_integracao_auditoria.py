"""
Testes de integração da consulta de auditoria (RegistroAuditoriaListView).

Aqui usamos o django.test.Client, que é o equivalente ao MockMvc da aula:
a requisição não abre uma porta de rede, mas passa por todo o caminho real
(middlewares de sessão, CSRF, autenticação e auditoria, a view, o ORM e o
banco de teste). Nada é mockado.

Os registros de auditoria nunca são criados direto no banco: eles nascem de
ações reais feitas pelos endpoints, como um login certo, um login errado ou
uma tentativa de acesso negado. Assim o teste também confere que o
middleware e os sinais gravaram o que deviam.

Isolamento: cada teste roda numa transação desfeita no final (TestCase), e
os logins usados levam time.time_ns() para não se repetirem.
"""
import csv
import io
import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Acao, RegistroAuditoria

Usuario = get_user_model()
SENHA = "SenhaDeTeste123"

AUDITORIA = reverse("auditoria:registro_list")
LOGIN = reverse("login")


class AuditoriaIntegracaoTest(TestCase):

    def setUp(self):
        sufixo = time.time_ns()
        self.coordenacao = Usuario.objects.create_superuser(
            username=f"coord.{sufixo}", password=SENHA, email=""
        )
        self.docente = Usuario.objects.create_user(
            username=f"prof.ana.{sufixo}", password=SENHA, perfil="DOCENTE"
        )

    # Helpers

    def entrar_como(self, usuario, client=None):
        """Login pela tela real, com o aceite dos termos."""
        client = client or self.client
        resposta = client.post(
            LOGIN,
            {"username": usuario.username, "password": SENHA, "aceite_termos": "on"},
        )
        self.assertEqual(resposta.status_code, 302, "o login deveria ter funcionado")

    def errar_login(self, login_digitado):
        """Gera um registro LOGIN_FALHA pela própria tela de login."""
        resposta = self.client_anonimo().post(
            LOGIN, {"username": login_digitado, "password": "senha-errada"}
        )
        self.assertEqual(resposta.status_code, 200)  # a tela volta com o erro

    def client_anonimo(self):
        return self.client_class()

    # Caminho feliz

    def test_listar_comoCoordenacao_deveRetornar200ComOsRegistros(self):
        # Arrange: o login do docente gera um registro LOGIN
        self.entrar_como(self.docente, client=self.client_anonimo())
        self.entrar_como(self.coordenacao)

        # Act
        resposta = self.client.get(AUDITORIA)

        # Assert
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Auditoria")
        self.assertContains(resposta, self.docente.username)
        logins_do_docente = [
            r for r in resposta.context["registros"]
            if r.acao == Acao.LOGIN and r.usuario_id == self.docente.pk
        ]
        self.assertEqual(len(logins_do_docente), 1)

    def test_listar_comFiltroDeAcao_deveRetornarSomenteAAcaoFiltrada(self):
        # Arrange
        login_errado = f"intruso.{time.time_ns()}"
        self.errar_login(login_errado)
        self.entrar_como(self.coordenacao)

        # Act
        resposta = self.client.get(AUDITORIA, {"acao": Acao.LOGIN_FALHA})

        # Assert
        self.assertEqual(resposta.status_code, 200)
        registros = list(resposta.context["registros"])
        self.assertGreaterEqual(len(registros), 1)
        self.assertTrue(all(r.acao == Acao.LOGIN_FALHA for r in registros))
        self.assertContains(resposta, f"Tentativa de login falhou para &#x27;{login_errado}&#x27;")

    def test_exportar_comFormatoCsv_deveRetornar200ComAnexoECabecalho(self):
        # Arrange
        self.entrar_como(self.docente, client=self.client_anonimo())
        self.entrar_como(self.coordenacao)

        # Act
        resposta = self.client.get(AUDITORIA, {"formato": "csv", "acao": Acao.LOGIN})

        # Assert
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "text/csv; charset=utf-8")
        self.assertRegex(
            resposta["Content-Disposition"],
            r'^attachment; filename="auditoria_simap_\d{8}_\d{4}\.csv"$',
        )
        conteudo = b"".join(resposta.streaming_content).decode("utf-8-sig")
        linhas = conteudo.strip().splitlines()
        self.assertEqual(
            linhas[0],
            "data_hora;acao;usuario;entidade;objeto_id;objeto;descricao;ip;metodo;caminho;status_http",
        )
        self.assertTrue(any(self.docente.username in linha for linha in linhas[1:]))

    def test_exportar_comLoginComFormula_deveNeutralizarACelulaNoCsv(self):
        # Arrange: alguém digita uma fórmula de planilha no campo de usuário
        formula = f'=HYPERLINK("http://malicioso.example/{time.time_ns()}")'
        self.errar_login(formula)
        self.entrar_como(self.coordenacao)

        # Act
        resposta = self.client.get(AUDITORIA, {"formato": "csv", "acao": Acao.LOGIN_FALHA})

        # Assert: a célula vai com apóstrofo na frente e o Excel não executa
        self.assertEqual(resposta.status_code, 200)
        conteudo = b"".join(resposta.streaming_content).decode("utf-8-sig")
        linhas = list(csv.reader(io.StringIO(conteudo), delimiter=";"))
        coluna_usuario = linhas[0].index("usuario")
        celulas = [linha[coluna_usuario] for linha in linhas[1:]]
        self.assertIn("'" + formula, celulas)
        self.assertNotIn(formula, celulas)

    # Erros

    def test_listar_comIpInvalidoNoFiltro_deveRetornar200SemRegistros(self):
        self.entrar_como(self.coordenacao)

        resposta = self.client.get(AUDITORIA, {"ip": "isso-nao-e-um-ip"})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["paginator"].count, 0)
        self.assertContains(resposta, "Nenhum registro encontrado.")

    def test_enviar_comMetodoPost_deveRetornar405ComMetodosPermitidos(self):
        self.entrar_como(self.coordenacao)
        alteracoes_de_dados = RegistroAuditoria.objects.filter(
            acao__in=[Acao.CRIACAO, Acao.ALTERACAO, Acao.EXCLUSAO]
        )
        total_antes = alteracoes_de_dados.count()

        resposta = self.client.post(AUDITORIA, {"acao": "LOGIN"})

        self.assertEqual(resposta.status_code, 405)
        self.assertIn("GET", resposta["Allow"])
        self.assertNotIn("POST", resposta["Allow"])
        # Uma consulta não pode mudar dado nenhum.
        self.assertEqual(alteracoes_de_dados.count(), total_antes)

    # Segurança

    def test_listar_semLogin_deveRetornar302ParaOLoginComNext(self):
        resposta = self.client.get(AUDITORIA)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"{LOGIN}?next={AUDITORIA}")

    def test_listar_comoDocente_deveRetornar403EGravarAcessoNegado(self):
        # Arrange
        self.entrar_como(self.docente)

        # Act
        resposta = self.client.get(AUDITORIA)

        # Assert: pela API...
        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, "403 Forbidden", status_code=403)
        # ...e no banco: a tentativa ficou registrada com quem tentou e onde.
        registro = RegistroAuditoria.objects.get(
            acao=Acao.ACESSO_NEGADO, usuario=self.docente, caminho=AUDITORIA
        )
        self.assertEqual(registro.status_http, 403)
        self.assertEqual(registro.metodo, "GET")
