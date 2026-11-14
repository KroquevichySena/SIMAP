"""
Testes das melhorias das trilhas: material de apoio, avisos de publicação,
lembrete de prazo e links clicáveis na tela do aluno.
"""
import io
import shutil
import tempfile
from datetime import timedelta

from usuarios.test_helpers import registrar_aceites_atuais

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from comunicacao.models import Notificacao
from comunicacao.arquivos_teste import PDF_OK
from entregas.models import Submissao
from turmas.models import Matricula, Turma

from .models import Atividade, MaterialDeApoio, TrilhaAprendizagem

Usuario = get_user_model()


class TrilhasBase(TestCase):
    """Turma com professor, dois alunos ativos, um inativo e um de fora."""

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
        cls.prof = Usuario.objects.create_user("prof.ana", password="x", perfil="DOCENTE")
        cls.outro_prof = Usuario.objects.create_user("prof.bia", password="x", perfil="DOCENTE")
        cls.aluno = Usuario.objects.create_user("aluno.caio", password="x", perfil="DISCENTE")
        cls.colega = Usuario.objects.create_user("aluno.duda", password="x", perfil="DISCENTE")
        cls.inativo = Usuario.objects.create_user("aluno.fabio", password="x", perfil="DISCENTE")
        cls.intruso = Usuario.objects.create_user("aluno.eva", password="x", perfil="DISCENTE")
        cls.turma = Turma.objects.create(nome="Algoritmos", periodo="2026.2", docente=cls.prof)
        outra = Turma.objects.create(nome="Banco de Dados", periodo="2026.2", docente=cls.outro_prof)
        Matricula.objects.create(turma=cls.turma, discente=cls.aluno)
        Matricula.objects.create(turma=cls.turma, discente=cls.colega)
        Matricula.objects.create(turma=cls.turma, discente=cls.inativo, status="INATIVA")
        Matricula.objects.create(turma=outra, discente=cls.intruso)
        cls.trilha = TrilhaAprendizagem.objects.create(
            turma=cls.turma, titulo="Módulo 1", ordem=1, publicada=True,
            descricao="Leia https://docs.python.org/3/ antes da aula.",
        )

        registrar_aceites_atuais(Usuario.objects.all())

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def dados_trilha(self, **extra):
        dados = {"turma": self.turma.pk, "titulo": "Módulo 2", "descricao": "", "ordem": 2}
        dados.update(extra)
        return dados

    def dados_atividade(self, **extra):
        dados = {
            "trilha": self.trilha.pk, "titulo": "Exercício 1", "enunciado": "Faça o exercício.",
            "tipo": Atividade._meta.get_field("tipo").default, "ordem": 1, "prazo": "",
        }
        dados.update(extra)
        return dados

    def avisos(self, tipo):
        return Notificacao.objects.filter(tipo=tipo)


class MaterialDeApoioTest(TrilhasBase):

    def test_professor_anexa_material_ao_criar_trilha(self):
        self.entrar(self.prof)
        resposta = self.client.post(reverse("core:trilha_create"), self.dados_trilha(
            materiais=[SimpleUploadedFile("slides.pdf", PDF_OK), SimpleUploadedFile("exemplo.py", b"print(1)\n")],
        ))
        self.assertRedirects(resposta, reverse("core:trilha_list"))
        trilha = TrilhaAprendizagem.objects.get(titulo="Módulo 2")
        self.assertEqual(sorted(trilha.materiais.values_list("nome_original", flat=True)), ["exemplo.py", "slides.pdf"])

    def test_bat_e_bloqueado_e_a_trilha_nao_e_criada(self):
        self.entrar(self.prof)
        resposta = self.client.post(reverse("core:trilha_create"), self.dados_trilha(
            materiais=[SimpleUploadedFile("shutdown.bat", b"shutdown /s /t 0")],
        ))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "não é permitido")
        self.assertFalse(TrilhaAprendizagem.objects.filter(titulo="Módulo 2").exists())
        self.assertFalse(MaterialDeApoio.objects.exists())

    def test_documento_office_falso_nao_cria_atividade(self):
        self.entrar(self.prof)
        resposta = self.client.post(reverse("core:atividade_create"), self.dados_atividade(
            materiais=[SimpleUploadedFile("aula.docx", b"PK\x03\x04nao e um documento Office")],
        ))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "corrompido")
        self.assertFalse(Atividade.objects.exists())
        self.assertFalse(MaterialDeApoio.objects.exists())

    def test_material_da_atividade_e_removido_na_edicao(self):
        self.entrar(self.prof)
        self.client.post(reverse("core:atividade_create"), self.dados_atividade(
            materiais=[SimpleUploadedFile("lista.pdf", PDF_OK)],
        ))
        atividade = Atividade.objects.get(titulo="Exercício 1")
        material = atividade.materiais.get()

        resposta = self.client.post(
            reverse("core:atividade_update", args=[atividade.pk]),
            self.dados_atividade(remover_materiais=[material.pk]),
        )
        self.assertRedirects(resposta, reverse("core:atividade_list"))
        self.assertFalse(atividade.materiais.exists())

    def test_nao_remove_material_de_outro_objeto_pelo_formulario(self):
        alheio = MaterialDeApoio.objects.create(
            trilha=self.trilha, arquivo="core/x.pdf", nome_original="x.pdf", extensao="pdf",
            tipo_conteudo="application/pdf", tamanho=10, sha256="0" * 64,
        )
        self.entrar(self.prof)
        self.client.post(reverse("core:atividade_create"), self.dados_atividade())
        atividade = Atividade.objects.get(titulo="Exercício 1")
        self.client.post(
            reverse("core:atividade_update", args=[atividade.pk]),
            self.dados_atividade(remover_materiais=[alheio.pk]),
        )
        self.assertTrue(MaterialDeApoio.objects.filter(pk=alheio.pk).exists())

    def _material_publicado(self):
        self.entrar(self.prof)
        self.client.post(reverse("core:trilha_update", args=[self.trilha.pk]), {
            "turma": self.turma.pk, "titulo": self.trilha.titulo, "descricao": self.trilha.descricao,
            "ordem": 1, "publicada": "on", "materiais": [SimpleUploadedFile("apostila.pdf", PDF_OK)],
        })
        self.client.logout()
        return self.trilha.materiais.get()

    def test_aluno_da_turma_baixa_o_material_com_cabecalhos_seguros(self):
        material = self._material_publicado()
        self.entrar(self.aluno)
        resposta = self.client.get(reverse("core:baixar_material", args=[material.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["X-Content-Type-Options"], "nosniff")
        self.assertIn("attachment", resposta["Content-Disposition"])
        self.assertEqual(b"".join(resposta.streaming_content), PDF_OK)

    def test_quem_nao_e_da_turma_recebe_404(self):
        material = self._material_publicado()
        for pessoa in (self.intruso, self.inativo, self.outro_prof):
            with self.subTest(pessoa=pessoa.username):
                self.entrar(pessoa)
                resposta = self.client.get(reverse("core:baixar_material", args=[material.pk]))
                self.assertEqual(resposta.status_code, 404)

    def test_material_de_trilha_em_rascunho_nao_sai_para_o_aluno(self):
        material = self._material_publicado()
        TrilhaAprendizagem.objects.filter(pk=self.trilha.pk).update(publicada=False)
        self.entrar(self.aluno)
        self.assertEqual(self.client.get(reverse("core:baixar_material", args=[material.pk])).status_code, 404)
        self.entrar(self.prof)
        self.assertEqual(self.client.get(reverse("core:baixar_material", args=[material.pk])).status_code, 200)


class AvisosDePublicacaoTest(TrilhasBase):

    def test_trilha_criada_publicada_avisa_so_os_alunos_ativos(self):
        self.entrar(self.prof)
        self.client.post(reverse("core:trilha_create"), self.dados_trilha(publicada="on"))
        avisados = set(self.avisos(Notificacao.Tipo.TRILHA).values_list("destinatario__username", flat=True))
        self.assertEqual(avisados, {"aluno.caio", "aluno.duda"})

    def test_rascunho_nao_avisa_e_publicar_depois_avisa_uma_vez(self):
        self.entrar(self.prof)
        self.client.post(reverse("core:trilha_create"), self.dados_trilha())
        self.assertFalse(self.avisos(Notificacao.Tipo.TRILHA).exists())

        trilha = TrilhaAprendizagem.objects.get(titulo="Módulo 2")
        url = reverse("core:trilha_update", args=[trilha.pk])
        self.client.post(url, self.dados_trilha(publicada="on"))
        self.assertEqual(self.avisos(Notificacao.Tipo.TRILHA).count(), 2)

        # Editar algo que já estava publicado não manda outro aviso.
        self.client.post(url, self.dados_trilha(publicada="on", descricao="corrigido"))
        self.assertEqual(self.avisos(Notificacao.Tipo.TRILHA).count(), 2)

    def test_nova_atividade_avisa_com_link_para_ela(self):
        self.entrar(self.prof)
        self.client.post(reverse("core:atividade_create"), self.dados_atividade(publicada="on"))
        atividade = Atividade.objects.get(titulo="Exercício 1")
        aviso = self.avisos(Notificacao.Tipo.ATIVIDADE).get(destinatario=self.aluno)
        self.assertEqual(aviso.url, f"{reverse('core:minhas_trilhas')}#atividade-{atividade.pk}")
        self.assertEqual(self.avisos(Notificacao.Tipo.ATIVIDADE).count(), 2)

    def test_atividade_em_trilha_rascunho_nao_avisa(self):
        TrilhaAprendizagem.objects.filter(pk=self.trilha.pk).update(publicada=False)
        self.entrar(self.prof)
        self.client.post(reverse("core:atividade_create"), self.dados_atividade(publicada="on"))
        self.assertTrue(Atividade.objects.filter(titulo="Exercício 1").exists())
        self.assertFalse(self.avisos(Notificacao.Tipo.ATIVIDADE).exists())


class LembreteDePrazoTest(TrilhasBase):

    def _atividade(self, horas, **extra):
        dados = {"trilha": self.trilha, "titulo": f"Prazo em {horas}h", "enunciado": "x",
                 "ordem": abs(horas), "prazo": timezone.now() + timedelta(hours=horas)}
        dados.update(extra)
        return Atividade.objects.create(**dados)

    def rodar(self, *args):
        saida = io.StringIO()
        call_command("notificar_prazos", *args, stdout=saida)
        return saida.getvalue()

    def test_avisa_quem_nao_entregou_e_nao_repete(self):
        atividade = self._atividade(5)
        Submissao.objects.create(atividade=atividade, aluno=self.colega, resposta_texto="feito")
        self.assertIn("1 lembrete", self.rodar())
        self.assertEqual(
            list(self.avisos(Notificacao.Tipo.PRAZO).values_list("destinatario__username", flat=True)),
            ["aluno.caio"],
        )
        self.assertIn("0 lembrete", self.rodar())

    def test_ignora_prazo_longe_vencido_e_rascunho(self):
        self._atividade(72)
        self._atividade(-2)
        self._atividade(3, publicada=False)
        self.rodar()
        self.assertFalse(self.avisos(Notificacao.Tipo.PRAZO).exists())

    def test_janela_configuravel(self):
        self._atividade(40)
        self.rodar("--horas", "48")
        self.assertEqual(self.avisos(Notificacao.Tipo.PRAZO).count(), 2)


class TelaDoAlunoTest(TrilhasBase):

    def test_descricao_tem_link_seguro_e_ancora_da_trilha(self):
        Atividade.objects.create(
            trilha=self.trilha, titulo="Ex", ordem=1,
            enunciado="Use https://replit.com e não javascript:alert(1)",
        )
        self.entrar(self.aluno)
        resposta = self.client.get(reverse("core:minhas_trilhas"))
        self.assertContains(resposta, f'id="trilha-{self.trilha.pk}"')
        self.assertContains(resposta, 'href="https://docs.python.org/3/"')
        self.assertContains(resposta, 'href="https://replit.com"')
        self.assertContains(resposta, 'rel="noopener noreferrer nofollow"')
        self.assertNotContains(resposta, 'href="javascript:')
        self.assertContains(resposta, 'enctype="multipart/form-data"')
