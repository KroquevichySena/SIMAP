"""
Testes da comunicação: segurança dos anexos e dos links, regras de quem vê o
quê, notificações e o download protegido.

Os arquivos de teste são montados aqui mesmo, byte a byte, para cada cenário
ser explícito: um PDF de verdade, um .exe renomeado para .pdf, um Word com
macro etc. Os uploads vão para uma pasta temporária, apagada no final.
"""
import hashlib
import io
import shutil
import tempfile
import zipfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.models import Atividade, TrilhaAprendizagem
from turmas.models import Matricula, Turma
from usuarios.test_helpers import registrar_aceites_atuais

from .arquivos_teste import PDF_OK, PNG_OK, adicionar_javascript, pdf_teste
from .arquivos_teste import office_teste as office
from .models import Anexo, Notificacao, Publicacao, Resposta
from .seguranca import limpar_nome, nome_para_download, validar_anexo
from .templatetags.comunicacao_tags import texto_com_links

Usuario = get_user_model()

EXE = b"MZ\x90\x00" + b"\x00" * 60 + b"This program cannot be run in DOS mode"


def arquivo(nome, conteudo):
    return SimpleUploadedFile(nome, conteudo)


class ValidacaoDeAnexosTest(SimpleTestCase):

    def test_aceita_pdf_imagem_word_e_codigo_validos(self):
        for nome, conteudo in [
            ("trabalho.pdf", PDF_OK),
            ("print.png", PNG_OK),
            ("relatorio.docx", office()),
            ("planilha.xlsx", office("xl/workbook.xml")),
            ("exercicio.py", b"print('ola')\n"),
            ("Main.java", "class Main { /* acentuação */ }".encode()),
        ]:
            with self.subTest(nome=nome):
                self.assertEqual(validar_anexo(arquivo(nome, conteudo)).nome_original, nome)

    def test_bloqueia_extensoes_perigosas(self):
        for nome in ["shutdown.bat", "virus.exe", "script.ps1", "macro.vbs", "setup.msi",
                     "atalho.lnk", "pacote.zip", "pagina.svg", "sem_extensao"]:
            with self.subTest(nome=nome):
                with self.assertRaisesMessage(ValidationError, "não é permitido"):
                    validar_anexo(arquivo(nome, b"qualquer coisa"))

    def test_bloqueia_dupla_extensao_que_termina_em_executavel(self):
        with self.assertRaisesMessage(ValidationError, "o tipo .bat não é permitido"):
            validar_anexo(arquivo("trabalho.pdf.bat", b"shutdown /s /t 0"))

    def test_bloqueia_executavel_renomeado_para_pdf(self):
        with self.assertRaisesMessage(ValidationError, "executável disfarçado"):
            validar_anexo(arquivo("trabalho.pdf", EXE))

    def test_bloqueia_executavel_renomeado_para_codigo(self):
        with self.assertRaisesMessage(ValidationError, "executável disfarçado"):
            validar_anexo(arquivo("programa.py", EXE))

    def test_bloqueia_conteudo_que_nao_bate_com_a_extensao(self):
        with self.assertRaisesMessage(ValidationError, "não é um PDF de verdade"):
            validar_anexo(arquivo("trabalho.pdf", b"<html><script>alert(1)</script></html>"))
        with self.assertRaisesMessage(ValidationError, "não é uma imagem"):
            validar_anexo(arquivo("foto.png", PDF_OK))

    def test_bloqueia_pdf_com_javascript(self):
        malicioso = pdf_teste(adicionar_javascript)
        with self.assertRaisesMessage(ValidationError, "conteúdo ativo"):
            validar_anexo(arquivo("boleto.pdf", malicioso))

    def test_bloqueia_word_com_macro(self):
        with self.assertRaisesMessage(ValidationError, "macros"):
            validar_anexo(arquivo("relatorio.docx", office(extras=["word/vbaProject.bin"])))

    def test_bloqueia_word_com_arquivo_embutido(self):
        with self.assertRaisesMessage(ValidationError, "arquivos embutidos"):
            validar_anexo(arquivo("relatorio.docx", office(extras=["word/embeddings/oleObject1.bin"])))

    def test_bloqueia_zip_renomeado_para_docx(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as pacote:
            pacote.writestr("shutdown.bat", "shutdown /s")
        with self.assertRaisesMessage(ValidationError, "não corresponde"):
            validar_anexo(arquivo("relatorio.docx", buffer.getvalue()))

    def test_bloqueia_codigo_com_conteudo_binario(self):
        with self.assertRaisesMessage(ValidationError, "conteúdo binário"):
            validar_anexo(arquivo("dados.txt", b"abc\x00\x01\x02"))

    @override_settings(COMUNICACAO_TAMANHO_MAXIMO_ANEXO=1024)
    def test_bloqueia_arquivo_acima_do_limite(self):
        with self.assertRaisesMessage(ValidationError, "passa do limite"):
            validar_anexo(arquivo("grande.txt", b"a" * 2048))

    def test_bloqueia_arquivo_vazio(self):
        with self.assertRaisesMessage(ValidationError, "está vazio"):
            validar_anexo(arquivo("vazio.txt", b""))

    def test_remove_caractere_que_inverte_o_nome(self):
        # "trabalho\u202Efdp.exe" aparece na tela como "trabalhoexe.pdf"
        self.assertEqual(limpar_nome("trabalho\u202efdp.exe"), "trabalhofdp.exe")
        with self.assertRaisesMessage(ValidationError, ".exe não é permitido"):
            validar_anexo(arquivo("trabalho\u202efdp.exe", EXE))

    def test_remove_caminho_do_nome(self):
        self.assertEqual(limpar_nome("../../SIMAP/settings.py"), "settings.py")
        self.assertEqual(limpar_nome("C:\\Windows\\win.ini").endswith("win.ini"), True)

    def test_codigo_e_baixado_com_txt_no_fim(self):
        self.assertEqual(nome_para_download("exercicio.py", ".py"), "exercicio.py.txt")
        self.assertEqual(nome_para_download("trabalho.pdf", ".pdf"), "trabalho.pdf")


class LinksSegurosTest(SimpleTestCase):

    def test_link_https_vira_clicavel_e_abre_em_outra_aba_isolada(self):
        html = texto_com_links("Leia https://docs.djangoproject.com/pt-br/5.2/ antes da aula.")
        self.assertIn('href="https://docs.djangoproject.com/pt-br/5.2/"', html)
        self.assertIn('rel="noopener noreferrer nofollow"', html)
        self.assertIn('target="_blank"', html)
        self.assertIn("(docs.djangoproject.com)", html)

    def test_pontuacao_final_nao_entra_no_link(self):
        html = texto_com_links("Veja https://exemplo.com.br.")
        self.assertIn('href="https://exemplo.com.br"', html)

    def test_javascript_e_data_nao_viram_link(self):
        for perigoso in ["javascript:alert(document.cookie)", "data:text/html;base64,PHNjcmlwdD4=",
                         "file:///C:/Windows/System32/shutdown.exe"]:
            with self.subTest(perigoso=perigoso):
                self.assertNotIn("<a ", texto_com_links(f"clique: {perigoso}"))

    def test_link_com_usuario_embutido_nao_vira_link(self):
        html = texto_com_links("https://www.umc.br@site-falso.com/login")
        self.assertNotIn("<a ", html)

    def test_html_digitado_e_mostrado_como_texto(self):
        html = texto_com_links('<script>alert(1)</script><img src=x onerror="alert(2)">')
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)

    def test_link_que_tenta_fechar_o_atributo_nao_injeta_html(self):
        html = texto_com_links('https://exemplo.com/"onmouseover="alert(1)')
        self.assertNotIn('onmouseover="alert', html)


class ComunicacaoBase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._pasta = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls._pasta)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._pasta, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.prof = Usuario.objects.create_user("prof.ana", password="x", perfil="DOCENTE", first_name="Ana")
        cls.outro_prof = Usuario.objects.create_user("prof.bia", password="x", perfil="DOCENTE")
        cls.aluno = Usuario.objects.create_user("aluno.caio", password="x", perfil="DISCENTE", first_name="Caio")
        cls.colega = Usuario.objects.create_user("aluno.duda", password="x", perfil="DISCENTE", first_name="Duda")
        cls.intruso = Usuario.objects.create_user("aluno.eva", password="x", perfil="DISCENTE")
        cls.inativo = Usuario.objects.create_user("aluno.fabio", password="x", perfil="DISCENTE")
        cls.turma = Turma.objects.create(nome="Algoritmos", periodo="2026.2", docente=cls.prof)
        cls.outra_turma = Turma.objects.create(nome="Banco de Dados", periodo="2026.2", docente=cls.outro_prof)
        Matricula.objects.create(turma=cls.turma, discente=cls.aluno)
        Matricula.objects.create(turma=cls.turma, discente=cls.colega)
        Matricula.objects.create(turma=cls.turma, discente=cls.inativo, status="INATIVA")
        Matricula.objects.create(turma=cls.outra_turma, discente=cls.intruso)
        trilha = TrilhaAprendizagem.objects.create(turma=cls.turma, titulo="Módulo 1")
        cls.atividade = Atividade.objects.create(trilha=trilha, titulo="Laços", enunciado="Faça um for")
        cls.rascunho = Atividade.objects.create(trilha=trilha, titulo="Rascunho", enunciado="x", publicada=False)

        registrar_aceites_atuais(Usuario.objects.all())

    def mural(self, turma=None):
        return reverse("comunicacao:mural", args=[(turma or self.turma).pk])

    def publicar(self, usuario, texto="Olá turma", **extras):
        self.client.force_login(usuario)
        return self.client.post(self.mural(), {"texto": texto, **extras})


class MuralTest(ComunicacaoBase):

    def test_professor_publica_e_os_alunos_ativos_sao_notificados(self):
        resposta = self.publicar(self.prof, "Prova na sexta! Material: https://exemplo.com/prova")

        publicacao = Publicacao.objects.get()
        self.assertRedirects(resposta, publicacao.get_absolute_url())
        avisados = set(Notificacao.objects.values_list("destinatario__username", flat=True))
        self.assertEqual(avisados, {"aluno.caio", "aluno.duda"})  # o inativo e o intruso não

    def test_aluno_publica_e_so_o_professor_e_notificado(self):
        self.publicar(self.aluno, "Professor, a aula de amanhã está mantida?")
        self.assertEqual(
            list(Notificacao.objects.values_list("destinatario__username", flat=True)), ["prof.ana"]
        )

    def test_quem_nao_e_da_turma_recebe_404(self):
        for usuario in (self.intruso, self.inativo, self.outro_prof):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(self.mural()).status_code, 404)
                self.assertEqual(self.client.post(self.mural(), {"texto": "oi"}).status_code, 404)
        self.assertFalse(Publicacao.objects.exists())

    def test_upload_de_bat_e_recusado_e_nada_e_gravado(self):
        resposta = self.publicar(
            self.aluno, "segue o trabalho", anexos=[arquivo("trabalho.pdf.bat", b"shutdown /s /t 0")]
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "o tipo .bat não é permitido")
        self.assertFalse(Publicacao.objects.exists())
        self.assertFalse(Anexo.objects.exists())

    @override_settings(COMUNICACAO_MAXIMO_ANEXOS=2)
    def test_limite_de_anexos_por_mensagem(self):
        anexos = [arquivo(f"a{i}.txt", b"oi") for i in range(3)]
        resposta = self.publicar(self.aluno, "três arquivos", anexos=anexos)
        self.assertContains(resposta, "no máximo 2 arquivos")
        self.assertFalse(Publicacao.objects.exists())

    def test_texto_com_html_e_mostrado_escapado_no_mural(self):
        self.publicar(self.aluno, '<script>alert("xss")</script>')
        resposta = self.client.get(self.mural())
        self.assertContains(resposta, "&lt;script&gt;")
        self.assertNotContains(resposta, '<script>alert("xss")</script>')


class MensagemPrivadaTest(ComunicacaoBase):

    def test_professor_manda_privada_e_so_o_destinatario_ve(self):
        self.publicar(self.prof, "Caio, sua nota foi revisada.", destinatario=self.aluno.pk)
        privada = Publicacao.objects.get()
        self.assertTrue(privada.privada)

        self.client.force_login(self.aluno)
        self.assertContains(self.client.get(self.mural()), "sua nota foi revisada")
        self.assertEqual(self.client.get(privada.get_absolute_url()).status_code, 200)

        self.client.force_login(self.colega)
        self.assertNotContains(self.client.get(self.mural()), "sua nota foi revisada")
        self.assertEqual(self.client.get(privada.get_absolute_url()).status_code, 404)

        self.assertEqual(
            list(Notificacao.objects.values_list("destinatario__username", flat=True)), ["aluno.caio"]
        )

    def test_aluno_so_pode_mandar_privada_para_o_professor(self):
        resposta = self.publicar(self.aluno, "Duda, me passa a cola?", destinatario=self.colega.pk)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Faça uma escolha válida")
        self.assertFalse(Publicacao.objects.exists())

        self.publicar(self.aluno, "Professor, posso entregar amanhã?", destinatario=self.prof.pk)
        self.assertEqual(Publicacao.objects.get().destinatario, self.prof)

    def test_professor_nao_manda_privada_para_aluno_de_outra_turma(self):
        resposta = self.publicar(self.prof, "oi", destinatario=self.intruso.pk)
        self.assertContains(resposta, "Faça uma escolha válida")

    def test_resposta_na_privada_avisa_so_a_outra_pessoa(self):
        self.publicar(self.aluno, "Professor, tenho uma dúvida", destinatario=self.prof.pk)
        privada = Publicacao.objects.get()
        Notificacao.objects.all().delete()

        self.client.force_login(self.prof)
        self.client.post(privada.get_absolute_url(), {"texto": "Pode perguntar."})

        self.assertEqual(
            list(Notificacao.objects.values_list("destinatario__username", flat=True)), ["aluno.caio"]
        )


class ComentariosDeAtividadeTest(ComunicacaoBase):

    def url(self, atividade):
        return reverse("comunicacao:atividade", args=[atividade.pk])

    def test_aluno_comenta_na_atividade_e_o_professor_e_avisado(self):
        self.client.force_login(self.aluno)
        resposta = self.client.post(self.url(self.atividade), {"texto": "Posso usar while?"})

        comentario = Publicacao.objects.get()
        self.assertRedirects(resposta, comentario.get_absolute_url())
        self.assertEqual(comentario.atividade, self.atividade)
        self.assertIsNone(comentario.destinatario)
        notificacao = Notificacao.objects.get()
        self.assertEqual(notificacao.destinatario, self.prof)
        self.assertIn("Laços", notificacao.mensagem)

    def test_atividade_nao_publicada_nao_aparece_para_aluno(self):
        self.client.force_login(self.aluno)
        self.assertEqual(self.client.get(self.url(self.rascunho)).status_code, 404)
        self.client.force_login(self.prof)
        self.assertEqual(self.client.get(self.url(self.rascunho)).status_code, 200)

    def test_aluno_de_outra_turma_nao_ve_os_comentarios(self):
        self.client.force_login(self.intruso)
        self.assertEqual(self.client.get(self.url(self.atividade)).status_code, 404)


class RespostasTest(ComunicacaoBase):

    def test_resposta_avisa_autor_e_quem_ja_respondeu(self):
        self.publicar(self.prof, "Alguém tem dúvida sobre a lista?")
        publicacao = Publicacao.objects.get()
        Notificacao.objects.all().delete()

        self.client.force_login(self.aluno)
        self.client.post(publicacao.get_absolute_url(), {"texto": "Eu tenho, na questão 3."})
        self.assertEqual(
            list(Notificacao.objects.values_list("destinatario__username", flat=True)), ["prof.ana"]
        )
        Notificacao.objects.all().delete()

        self.client.force_login(self.colega)
        resposta = self.client.post(publicacao.get_absolute_url(), {"texto": "Eu também!"})
        self.assertRedirects(resposta, Resposta.objects.last().get_absolute_url(), fetch_redirect_response=False)
        avisados = set(Notificacao.objects.values_list("destinatario__username", flat=True))
        self.assertEqual(avisados, {"prof.ana", "aluno.caio"})

    def test_aluno_nao_apaga_publicacao_de_outro_mas_professor_apaga(self):
        self.publicar(self.colega, "Mensagem da Duda")
        publicacao = Publicacao.objects.get()
        url = reverse("comunicacao:publicacao_apagar", args=[publicacao.pk])

        self.client.force_login(self.aluno)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Publicacao.objects.exists())

        self.client.force_login(self.prof)
        self.assertRedirects(self.client.post(url), self.mural())
        self.assertFalse(Publicacao.objects.exists())


class DownloadDeAnexoTest(ComunicacaoBase):

    def enviar(self, nome, conteudo, **extras):
        self.publicar(self.aluno, "segue o anexo", anexos=[arquivo(nome, conteudo)], **extras)
        return Anexo.objects.get()

    def test_arquivo_e_salvo_com_nome_aleatorio_e_baixado_com_protecoes(self):
        anexo = self.enviar("Meu Trabalho.pdf", PDF_OK)
        self.assertNotIn("Trabalho", anexo.arquivo.name)
        self.assertTrue(anexo.arquivo.name.startswith("comunicacao/"))

        self.client.force_login(self.colega)
        resposta = self.client.get(reverse("comunicacao:anexo", args=[anexo.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertIn("attachment", resposta["Content-Disposition"])
        self.assertIn("Meu_Trabalho.pdf", resposta["Content-Disposition"])
        self.assertEqual(resposta["X-Content-Type-Options"], "nosniff")
        self.assertIn("sandbox", resposta["Content-Security-Policy"])
        self.assertEqual(b"".join(resposta.streaming_content), PDF_OK)

    def test_codigo_fonte_e_baixado_como_texto_com_txt_no_fim(self):
        anexo = self.enviar("exercicio.py", b"import os\nos.system('shutdown /s')\n")
        self.client.force_login(self.prof)
        resposta = self.client.get(reverse("comunicacao:anexo", args=[anexo.pk]))
        self.assertEqual(resposta["Content-Type"], "text/plain")
        self.assertIn('filename="exercicio.py.txt"', resposta["Content-Disposition"])

    def test_download_de_imagem_entrega_apenas_o_conteudo_reconstruido(self):
        marcador = b"CONTEUDO-EXTRA-QUE-NAO-DEVE-SER-SALVO"
        anexo = self.enviar("foto.png", PNG_OK + marcador)
        self.client.force_login(self.prof)
        resposta = self.client.get(reverse("comunicacao:anexo", args=[anexo.pk]))
        conteudo = b"".join(resposta.streaming_content)
        self.assertNotIn(marcador, conteudo)
        self.assertEqual(anexo.tamanho, len(conteudo))
        self.assertEqual(anexo.sha256, hashlib.sha256(conteudo).hexdigest())

    def test_download_de_office_entrega_pacote_reconstruido(self):
        marcador = b"CONTEUDO-EXTRA-FORA-DO-ZIP"
        anexo = self.enviar("aula.docx", office() + marcador)
        self.client.force_login(self.prof)
        resposta = self.client.get(reverse("comunicacao:anexo", args=[anexo.pk]))
        conteudo = b"".join(resposta.streaming_content)
        self.assertNotIn(marcador, conteudo)
        self.assertEqual(anexo.sha256, hashlib.sha256(conteudo).hexdigest())
        with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
            self.assertIn("word/document.xml", pacote.namelist())

    def test_quem_nao_pode_ver_a_mensagem_nao_baixa_o_anexo(self):
        anexo = self.enviar("privado.pdf", PDF_OK, destinatario=self.prof.pk)
        url = reverse("comunicacao:anexo", args=[anexo.pk])
        for usuario in (self.colega, self.intruso):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)  # vai para o login

    def test_apagar_a_publicacao_apaga_o_arquivo_do_disco(self):
        anexo = self.enviar("trabalho.pdf", PDF_OK)
        storage, nome = anexo.arquivo.storage, anexo.arquivo.name
        self.assertTrue(storage.exists(nome))

        self.client.force_login(self.prof)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("comunicacao:publicacao_apagar", args=[anexo.publicacao_id]))
        self.assertFalse(storage.exists(nome))


class NotificacoesTest(ComunicacaoBase):

    def test_abrir_notificacao_marca_como_lida_e_leva_a_mensagem(self):
        self.publicar(self.prof, "Aviso importante")
        notificacao = Notificacao.objects.get(destinatario=self.aluno)

        self.client.force_login(self.aluno)
        self.assertContains(self.client.get(reverse("comunicacao:notificacoes")), "publicou no mural")
        resposta = self.client.get(reverse("comunicacao:notificacao_abrir", args=[notificacao.pk]))

        self.assertRedirects(resposta, Publicacao.objects.get().get_absolute_url())
        notificacao.refresh_from_db()
        self.assertTrue(notificacao.lida)

    def test_nao_abre_notificacao_de_outra_pessoa(self):
        self.publicar(self.prof, "Aviso")
        notificacao = Notificacao.objects.get(destinatario=self.aluno)
        self.client.force_login(self.colega)
        self.assertEqual(
            self.client.get(reverse("comunicacao:notificacao_abrir", args=[notificacao.pk])).status_code, 404
        )

    def test_notificacao_com_endereco_externo_nao_redireciona_para_fora(self):
        notificacao = Notificacao.objects.create(
            destinatario=self.aluno, tipo="PUBLICACAO", mensagem="x", url="//site-falso.com/login"
        )
        self.client.force_login(self.aluno)
        resposta = self.client.get(reverse("comunicacao:notificacao_abrir", args=[notificacao.pk]))
        self.assertRedirects(resposta, reverse("comunicacao:notificacoes"))

    def test_sino_mostra_quantidade_de_nao_lidas(self):
        self.publicar(self.prof, "Um")
        self.publicar(self.prof, "Dois")
        self.client.force_login(self.aluno)
        resposta = self.client.get(reverse("comunicacao:inicio"))
        self.assertEqual(resposta.context["notificacoes_nao_lidas"], 2)

    def test_marcar_todas_como_lidas(self):
        self.publicar(self.prof, "Um")
        self.client.force_login(self.aluno)
        self.client.post(reverse("comunicacao:notificacoes_marcar_todas"))
        self.assertFalse(Notificacao.objects.filter(destinatario=self.aluno, lida=False).exists())


class AuditoriaDaComunicacaoTest(ComunicacaoBase):

    def test_auditoria_registra_a_publicacao_sem_copiar_o_texto(self):
        from auditoria.models import Acao, RegistroAuditoria

        self.publicar(self.aluno, "Professor, estou com problemas em casa.", destinatario=self.prof.pk)
        registro = RegistroAuditoria.objects.get(acao=Acao.CRIACAO, entidade="comunicacao.Publicacao")
        self.assertEqual(registro.usuario, self.aluno)
        self.assertEqual(registro.dados["texto"], "[conteúdo não registrado]")
        self.assertNotIn("problemas em casa", str(registro.dados))
