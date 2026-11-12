"""Testes da entrega com arquivo anexo."""
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core.models import Atividade
from core.test_materiais import PDF_OK, TrilhasBase
from comunicacao.arquivos_teste import PNG_OK

from .models import AnexoSubmissao, Submissao


@mock.patch("entregas.views.gerar_analise")
class EntregaComAnexoTest(TrilhasBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.atividade = Atividade.objects.create(
            trilha=cls.trilha, titulo="Exercício 1", enunciado="Some dois números.", ordem=1
        )

    def enviar(self, *arquivos, texto="a = 1 + 2"):
        return self.client.post(
            reverse("entregas:submeter", args=[self.atividade.pk]),
            {"resposta_texto": texto, "anexos": list(arquivos)},
        )

    def test_entrega_com_codigo_anexado(self, gerar_analise):
        self.entrar(self.aluno)
        resposta = self.enviar(SimpleUploadedFile("soma.py", b"print(1 + 2)\n"))
        self.assertRedirects(resposta, reverse("core:minhas_trilhas"))
        submissao = Submissao.objects.get(aluno=self.aluno)
        self.assertEqual(submissao.anexos.get().nome_original, "soma.py")
        gerar_analise.assert_called_once_with(submissao)

    def test_entrega_sem_anexo_continua_funcionando(self, gerar_analise):
        self.entrar(self.aluno)
        self.enviar()
        self.assertTrue(Submissao.objects.filter(aluno=self.aluno).exists())
        self.assertFalse(AnexoSubmissao.objects.exists())

    def test_bat_barra_a_entrega_inteira(self, gerar_analise):
        self.entrar(self.aluno)
        resposta = self.enviar(SimpleUploadedFile("shutdown.bat", b"shutdown /s /t 0"))
        self.assertRedirects(resposta, reverse("core:minhas_trilhas"), fetch_redirect_response=False)
        self.assertFalse(Submissao.objects.exists())
        self.assertFalse(AnexoSubmissao.objects.exists())
        gerar_analise.assert_not_called()
        mensagens = [str(m) for m in resposta.wsgi_request._messages]
        self.assertTrue(any("não é permitido" in m for m in mensagens))

    def test_arquivo_falso_barra_todo_o_envio_inclusive_anexo_valido(self, gerar_analise):
        self.entrar(self.aluno)
        for nome, conteudo in (("falso.pdf", b"%PDF-1.7\nnao e um documento\n%%EOF"),
                               ("falso.png", b"\x89PNG\r\n\x1a\n" + b"falso")):
            with self.subTest(nome=nome):
                resposta = self.enviar(SimpleUploadedFile("valido.pdf", PDF_OK), SimpleUploadedFile(nome, conteudo))
                self.assertEqual(resposta.status_code, 302)
                self.assertFalse(Submissao.objects.exists())
                self.assertFalse(AnexoSubmissao.objects.exists())
                gerar_analise.assert_not_called()

    def test_imagem_da_entrega_e_salva_reconstruida(self, gerar_analise):
        self.entrar(self.aluno)
        marcador = b"NAO-DEVE-SER-SALVO"
        self.enviar(SimpleUploadedFile("foto.png", PNG_OK + marcador))
        anexo = AnexoSubmissao.objects.get()
        with anexo.arquivo.open("rb") as arquivo:
            self.assertNotIn(marcador, arquivo.read())

    def test_exe_disfarcado_de_pdf_e_barrado(self, gerar_analise):
        self.entrar(self.aluno)
        self.enviar(SimpleUploadedFile("trabalho.pdf", b"MZ\x90\x00" + b"\x00" * 60))
        self.assertFalse(Submissao.objects.exists())

    def test_download_so_para_o_aluno_e_o_professor(self, gerar_analise):
        self.entrar(self.aluno)
        self.enviar(SimpleUploadedFile("relatorio.pdf", PDF_OK))
        anexo = AnexoSubmissao.objects.get()
        url = reverse("entregas:baixar_anexo", args=[anexo.pk])

        for pessoa, esperado in [(self.aluno, 200), (self.prof, 200), (self.colega, 404),
                                 (self.outro_prof, 404), (self.intruso, 404)]:
            with self.subTest(pessoa=pessoa.username):
                self.entrar(pessoa)
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, esperado)
                if esperado == 200:
                    self.assertEqual(resposta["X-Content-Type-Options"], "nosniff")

    def test_professor_ve_o_arquivo_na_correcao(self, gerar_analise):
        self.entrar(self.aluno)
        self.enviar(SimpleUploadedFile("soma.py", b"print(3)\n"))
        anexo = AnexoSubmissao.objects.get()
        self.entrar(self.prof)
        resposta = self.client.get(reverse("entregas:corrigir", args=[self.atividade.pk]))
        self.assertContains(resposta, reverse("entregas:baixar_anexo", args=[anexo.pk]))
        self.assertContains(resposta, "soma.py")
