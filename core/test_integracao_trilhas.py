"""
Testes de integração das trilhas de aprendizagem (TrilhaListView,
TrilhaCreateView, TrilhaUpdateView e TrilhaDeleteView).

Aqui nada é simulado: o LiveServerTestCase sobe o SIMAP de verdade numa
porta livre (o equivalente ao RANDOM_PORT da aula), e o requests faz as
chamadas HTTP como um navegador faria. Cada requisição passa pelos
middlewares (sessão, CSRF, autenticação e auditoria), pela view, pelo
formulário, pelo ORM e chega ao banco de teste em memória.

O login também é feito pela tela real (/contas/login/), com o aceite dos
termos, para a sessão nascer do mesmo jeito que nasce em produção.

Isolamento: o LiveServerTestCase limpa o banco depois de cada teste, e os
nomes de usuários e títulos levam time.time_ns() para nunca colidir.
"""
import time

import requests
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase
from django.urls import reverse

from auditoria.models import Acao, RegistroAuditoria
from turmas.models import Matricula, Turma

from .models import TrilhaAprendizagem

Usuario = get_user_model()
SENHA = "SenhaDeTeste123"

LISTA = reverse("core:trilha_list")
NOVA = reverse("core:trilha_create")
LOGIN = reverse("login")


def editar(pk):
    return reverse("core:trilha_update", args=[pk])


def excluir(pk):
    return reverse("core:trilha_delete", args=[pk])


class TrilhaIntegracaoBase(LiveServerTestCase):
    """Cenário comum: um docente com turma, outro docente com turma e um aluno."""

    def setUp(self):
        sufixo = time.time_ns()
        self.docente = Usuario.objects.create_user(
            username=f"prof.ana.{sufixo}", password=SENHA, perfil="DOCENTE"
        )
        self.outro_docente = Usuario.objects.create_user(
            username=f"prof.bruno.{sufixo}", password=SENHA, perfil="DOCENTE"
        )
        self.discente = Usuario.objects.create_user(
            username=f"aluno.carla.{sufixo}", password=SENHA, perfil="DISCENTE"
        )
        self.turma = Turma.objects.create(
            nome=f"Algoritmos {sufixo}", periodo="2026.2", docente=self.docente
        )
        self.turma_alheia = Turma.objects.create(
            nome=f"Banco de Dados {sufixo}", periodo="2026.2", docente=self.outro_docente
        )
        Matricula.objects.create(turma=self.turma, discente=self.discente)

        # Cliente HTTP que não segue redirecionamentos sozinho, para os testes
        # conseguirem conferir o 302 e o header Location.
        self.http = requests.Session()

    # Helpers

    def url(self, caminho):
        return self.live_server_url + caminho

    def get(self, caminho, **kwargs):
        return self.http.get(self.url(caminho), allow_redirects=False, timeout=10, **kwargs)

    def post(self, caminho, dados):
        # O Django exige o token CSRF em todo POST; ele vem do cookie csrftoken.
        dados = {**dados, "csrfmiddlewaretoken": self.http.cookies.get("csrftoken", "")}
        return self.http.post(
            self.url(caminho), data=dados, allow_redirects=False, timeout=10
        )

    def entrar_como(self, usuario):
        """Faz login pela tela real, aceitando os termos de uso."""
        self.get(LOGIN)  # gera o cookie csrftoken
        resposta = self.post(
            LOGIN,
            {"username": usuario.username, "password": SENHA, "aceite_termos": "on"},
        )
        self.assertEqual(resposta.status_code, 302, "o login deveria ter funcionado")
        return resposta

    def criar_trilha_pela_api(self, titulo, turma=None, ordem=1):
        """Cria uma trilha pelo próprio endpoint, como na aula (criarLivro)."""
        self.get(NOVA)  # garante o cookie csrftoken na sessão
        return self.post(NOVA, self.montar_trilha(titulo, turma=turma, ordem=ordem))

    def montar_trilha(self, titulo, turma=None, ordem=1):
        return {
            "turma": (turma or self.turma).pk,
            "titulo": titulo,
            "descricao": "Conteúdo de teste",
            "ordem": ordem,
            "publicada": "on",
        }


class TrilhaListagemIntegracaoTest(TrilhaIntegracaoBase):

    def test_listar_comoDocente_deveRetornar200ComAsTrilhasDaPropriaTurma(self):
        # Arrange
        sufixo = time.time_ns()
        TrilhaAprendizagem.objects.create(turma=self.turma, titulo=f"Minha trilha {sufixo}")
        TrilhaAprendizagem.objects.create(
            turma=self.turma_alheia, titulo=f"Trilha de outro professor {sufixo}"
        )
        self.entrar_como(self.docente)

        # Act
        resposta = self.get(LISTA)

        # Assert
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Trilhas de Aprendizagem", resposta.text)
        self.assertIn(f"Minha trilha {sufixo}", resposta.text)
        self.assertNotIn(f"Trilha de outro professor {sufixo}", resposta.text)

    def test_listar_semLogin_deveRetornar302ParaOLoginComNext(self):
        resposta = self.get(LISTA)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.headers["Location"], f"{LOGIN}?next={LISTA}")

    def test_listar_comoDiscente_deveRetornar403ComMensagem(self):
        self.entrar_como(self.discente)

        resposta = self.get(LISTA)

        self.assertEqual(resposta.status_code, 403)
        self.assertIn("403 Forbidden", resposta.text)


class TrilhaCriacaoIntegracaoTest(TrilhaIntegracaoBase):

    def test_novaTrilha_comoDocente_deveRetornar200ComFormularioSoComTurmasDoDocente(self):
        self.entrar_como(self.docente)

        resposta = self.get(NOVA)

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Nova Trilha", resposta.text)
        self.assertIn(self.turma.nome, resposta.text)
        self.assertNotIn(self.turma_alheia.nome, resposta.text)

    def test_criar_comDadosValidos_deveRetornar302ComLocationEPersistir(self):
        # Arrange
        titulo = f"Módulo 1 - Variáveis {time.time_ns()}"
        self.entrar_como(self.docente)

        # Act
        resposta = self.criar_trilha_pela_api(titulo, ordem=3)

        # Assert
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.headers["Location"], LISTA)
        trilha = TrilhaAprendizagem.objects.get(titulo=titulo)
        self.assertEqual(trilha.turma, self.turma)
        self.assertEqual(trilha.ordem, 3)
        self.assertTrue(trilha.publicada)

    def test_criar_comTituloDuplicadoNaTurma_deveRetornar200ComMensagemENaoDuplicar(self):
        # Arrange
        titulo = f"Módulo repetido {time.time_ns()}"
        self.entrar_como(self.docente)
        self.criar_trilha_pela_api(titulo)

        # Act
        resposta = self.criar_trilha_pela_api(titulo)

        # Assert
        self.assertEqual(resposta.status_code, 200)  # o formulário volta com o erro
        self.assertIn("já existe", resposta.text)
        self.assertEqual(TrilhaAprendizagem.objects.filter(titulo=titulo).count(), 1)

    def test_criar_comTurmaDeOutroDocente_deveRetornar200ComErroENaoPersistir(self):
        # Arrange: POST forjado com o ID de uma turma que não é do docente
        titulo = f"Trilha forjada {time.time_ns()}"
        self.entrar_como(self.docente)

        # Act
        resposta = self.criar_trilha_pela_api(titulo, turma=self.turma_alheia)

        # Assert
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Faça uma escolha válida", resposta.text)
        self.assertFalse(TrilhaAprendizagem.objects.filter(titulo=titulo).exists())


class TrilhaEdicaoIntegracaoTest(TrilhaIntegracaoBase):

    def setUp(self):
        super().setUp()
        self.trilha = TrilhaAprendizagem.objects.create(
            turma=self.turma, titulo=f"Título antigo {time.time_ns()}", ordem=1
        )

    def test_editar_comoDono_deveRetornar200ComOsDadosAtuais(self):
        self.entrar_como(self.docente)

        resposta = self.get(editar(self.trilha.pk))

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Editar Trilha", resposta.text)
        self.assertIn(f'value="{self.trilha.titulo}"', resposta.text)

    def test_editar_comNovoTitulo_deveRetornar302EGravarOTituloNovo(self):
        # Arrange
        novo_titulo = f"Título novo {time.time_ns()}"
        self.entrar_como(self.docente)
        self.get(editar(self.trilha.pk))

        # Act
        resposta = self.post(editar(self.trilha.pk), self.montar_trilha(novo_titulo, ordem=2))

        # Assert
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.headers["Location"], LISTA)
        self.trilha.refresh_from_db()
        self.assertEqual(self.trilha.titulo, novo_titulo)
        self.assertEqual(self.trilha.ordem, 2)
        # E a lista passa a mostrar o título novo.
        self.assertIn(novo_titulo, self.get(LISTA).text)

    def test_editar_trilhaDeOutroDocente_deveRetornar404ENaoAlterar(self):
        # Arrange: tentativa de IDOR, trocando o ID na URL
        titulo_original = self.trilha.titulo
        self.entrar_como(self.outro_docente)
        self.get(LISTA)

        # Act
        resposta = self.post(
            editar(self.trilha.pk),
            self.montar_trilha("Invadido", turma=self.turma_alheia),
        )

        # Assert
        self.assertEqual(resposta.status_code, 404)
        self.assertIn("Not Found", resposta.text)
        self.trilha.refresh_from_db()
        self.assertEqual(self.trilha.titulo, titulo_original)

    def test_editar_comIdInexistente_deveRetornar404(self):
        self.entrar_como(self.docente)

        resposta = self.get(editar(999_999))

        self.assertEqual(resposta.status_code, 404)
        self.assertIn("Not Found", resposta.text)


class TrilhaExclusaoIntegracaoTest(TrilhaIntegracaoBase):

    def setUp(self):
        super().setUp()
        self.trilha = TrilhaAprendizagem.objects.create(
            turma=self.turma, titulo=f"Para excluir {time.time_ns()}"
        )

    def test_excluir_get_deveRetornar200ComAConfirmacao(self):
        self.entrar_como(self.docente)

        resposta = self.get(excluir(self.trilha.pk))

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Confirmar exclusão", resposta.text)
        self.assertIn(self.trilha.titulo, resposta.text)

    def test_excluir_comoDono_deveRetornar302ETrilhaDeixaDeExistir(self):
        # Arrange
        self.entrar_como(self.docente)
        self.get(excluir(self.trilha.pk))

        # Act
        resposta = self.post(excluir(self.trilha.pk), {})

        # Assert
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.headers["Location"], LISTA)
        self.assertFalse(TrilhaAprendizagem.objects.filter(pk=self.trilha.pk).exists())
        # Efeito observável pela própria API: a trilha não abre mais.
        self.assertEqual(self.get(editar(self.trilha.pk)).status_code, 404)

    def test_excluir_trilhaDeOutroDocente_deveRetornar404ENaoApagar(self):
        self.entrar_como(self.outro_docente)
        self.get(LISTA)

        resposta = self.post(excluir(self.trilha.pk), {})

        self.assertEqual(resposta.status_code, 404)
        self.assertIn("Not Found", resposta.text)
        self.assertTrue(TrilhaAprendizagem.objects.filter(pk=self.trilha.pk).exists())


class TrilhaComAuditoriaIntegracaoTest(TrilhaIntegracaoBase):
    """Fluxo que cruza dois recursos: a trilha criada aparece na auditoria."""

    def test_criarTrilha_eConsultarAuditoria_deveListarACriacaoComOAutor(self):
        # Arrange
        titulo = f"Trilha auditada {time.time_ns()}"
        coordenacao = Usuario.objects.create_superuser(
            username=f"coord.{time.time_ns()}", password=SENHA, email=""
        )
        self.entrar_como(self.docente)
        self.criar_trilha_pela_api(titulo)
        trilha = TrilhaAprendizagem.objects.get(titulo=titulo)

        # Act: a coordenação consulta a auditoria, filtrando pela entidade
        self.http = requests.Session()
        self.entrar_como(coordenacao)
        resposta = self.get(
            reverse("auditoria:registro_list"),
            params={"acao": "CRIACAO", "entidade": "core.TrilhaAprendizagem"},
        )

        # Assert: pela API...
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(titulo, resposta.text)
        self.assertIn(self.docente.username, resposta.text)
        # ...e no banco: o registro aponta para a trilha e para quem a criou.
        registro = RegistroAuditoria.objects.get(
            acao=Acao.CRIACAO, entidade="core.TrilhaAprendizagem", objeto_id=str(trilha.pk)
        )
        self.assertEqual(registro.usuario, self.docente)
        self.assertEqual(registro.dados["titulo"], titulo)
