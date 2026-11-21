"""E-mail e RGM mascarados nas listagens e completos só onde a coordenação precisa conferir a conta."""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from turmas.models import Matricula, Turma

from .mascaras import mascarar_email, mascarar_rgm
from .test_helpers import registrar_aceites_atuais

EMAIL = "ana.martins@alunos.umc.br"
RGM = "11231102733"


class MascarasTest(SimpleTestCase):
    def test_email_mostra_o_comeco_e_o_dominio(self):
        self.assertEqual(mascarar_email(EMAIL), "an***@alunos.umc.br")
        self.assertEqual(mascarar_email("jo@umc.br"), "j***@umc.br")
        self.assertEqual(mascarar_email("a@umc.br"), "a***@umc.br")

    def test_rgm_mostra_os_quatro_ultimos_digitos(self):
        self.assertEqual(mascarar_rgm(RGM), "***2733")
        self.assertEqual(mascarar_rgm("1234"), "***")

    def test_mascara_nao_revela_o_tamanho_do_dado(self):
        self.assertEqual(len(mascarar_rgm("12345")), len(mascarar_rgm(RGM)))
        self.assertEqual(mascarar_email("abc@x.br"), mascarar_email("abcdefghij@x.br"))

    def test_vazio_continua_vazio_para_o_template_mostrar_nao_informado(self):
        for valor in ("", None):
            self.assertEqual(mascarar_email(valor), "")
            self.assertEqual(mascarar_rgm(valor), "")

    def test_texto_sem_arroba_nao_e_exibido(self):
        self.assertEqual(mascarar_email("sem-arroba"), "***")


class ListagensMascaradasTest(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.coord = Usuario.objects.create_superuser("coord", password="SenhaCoordenacao123!")
        self.prof = Usuario.objects.create_user("prof", perfil="DOCENTE")
        self.aluno = Usuario.objects.create_user(
            "ana", perfil="DISCENTE", email=EMAIL, rgm=RGM, first_name="Ana", last_name="Martins"
        )
        registrar_aceites_atuais(Usuario.objects.all())
        self.turma = Turma.objects.create(nome="Algoritmos", periodo="2026/2", docente=self.prof)
        Matricula.objects.create(turma=self.turma, discente=self.aluno)

    def test_lista_de_usuarios_da_coordenacao_mascara_email_e_rgm(self):
        self.client.force_login(self.coord)
        resposta = self.client.get(reverse("usuarios_lista"))
        self.assertContains(resposta, "an***@alunos.umc.br")
        self.assertContains(resposta, "***2733")
        self.assertNotContains(resposta, EMAIL)
        self.assertNotContains(resposta, RGM)

    def test_busca_pelo_dado_completo_continua_funcionando(self):
        self.client.force_login(self.coord)
        for termo in (EMAIL, RGM):
            with self.subTest(termo=termo):
                resposta = self.client.get(reverse("usuarios_lista"), {"q": termo})
                self.assertEqual(list(resposta.context["usuarios"]), [self.aluno])

    def test_confirmacao_de_acao_mostra_o_dado_completo_para_conferencia(self):
        self.client.force_login(self.coord)
        resposta = self.client.get(reverse("usuario_acao", args=[self.aluno.pk, "desativar"]))
        self.assertContains(resposta, EMAIL)
        self.assertContains(resposta, RGM)

    def test_lista_de_alunos_da_turma_mascara_o_rgm(self):
        self.client.force_login(self.prof)
        resposta = self.client.get(reverse("matriculas_turma", args=[self.turma.pk]))
        self.assertContains(resposta, "***2733")
        self.assertNotContains(resposta, RGM)

    def test_admin_mascara_na_lista_e_mostra_completo_na_edicao(self):
        self.client.force_login(self.coord)
        lista = self.client.get(reverse("admin:usuarios_usuario_changelist"))
        self.assertContains(lista, "an***@alunos.umc.br")
        self.assertNotContains(lista, EMAIL)
        self.assertNotContains(lista, RGM)
        edicao = self.client.get(reverse("admin:usuarios_usuario_change", args=[self.aluno.pk]))
        self.assertContains(edicao, EMAIL)
        self.assertContains(edicao, RGM)
