"""Na tela de matrícula, o docente busca o aluno por nome e filtra, em vez de rolar uma lista com todos."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from usuarios.test_helpers import registrar_aceites_atuais

from .forms import LIMITE_DA_BUSCA
from .models import Matricula, Turma


class BuscaNaMatriculaTest(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.docente = Usuario.objects.create_user("prof.busca", perfil="DOCENTE")
        self.ana = Usuario.objects.create_user(
            "ana.lima", perfil="DISCENTE", first_name="Ana", last_name="Lima", rgm="11230001234"
        )
        self.bruno = Usuario.objects.create_user("bruno.reis", perfil="DISCENTE", first_name="Bruno", last_name="Reis")
        self.carla = Usuario.objects.create_user("carla.dias", perfil="DISCENTE", first_name="Carla", last_name="Dias")
        registrar_aceites_atuais([self.docente])
        self.turma = Turma.objects.create(nome="Algoritmos", periodo="2026/2", docente=self.docente)
        self.outra = Turma.objects.create(nome="Redes", periodo="2026/2", docente=self.docente)
        self.client.force_login(self.docente)
        self.url = reverse("criar_matricula")

    def opcoes(self, resposta):
        return list(resposta.context["form"].fields["discente"].queryset)

    def test_busca_por_nome_sobrenome_usuario_ou_rgm(self):
        for termo in ("ana", "Lima", "ana.li", "1234", "ana lima"):
            with self.subTest(termo=termo):
                self.assertEqual(self.opcoes(self.client.get(self.url, {"q": termo})), [self.ana])

    def test_opcao_mostra_nome_usuario_e_rgm_mascarado(self):
        resposta = self.client.get(self.url, {"q": "ana"})
        self.assertContains(resposta, "Ana Lima · ana.lima · RGM ***1234")
        self.assertEqual(resposta.context["form"].initial["discente"], self.ana)
        self.assertNotContains(resposta, "11230001234")

    def test_filtro_sem_matricula_ativa(self):
        Matricula.objects.create(turma=self.outra, discente=self.bruno, status="ATIVA")
        resposta = self.client.get(self.url, {"filtro": "sem_turma"})
        self.assertEqual(self.opcoes(resposta), [self.ana, self.carla])

    def test_filtro_fora_da_turma_escolhida_e_turma_ja_vem_selecionada(self):
        Matricula.objects.create(turma=self.turma, discente=self.carla, status="ATIVA")
        resposta = self.client.get(self.url, {"filtro": "fora_da_turma", "turma": self.turma.pk})
        self.assertEqual(self.opcoes(resposta), [self.ana, self.bruno])
        self.assertEqual(resposta.context["form"].initial["turma"], self.turma)

    def test_lista_limitada_com_aviso(self):
        get_user_model().objects.bulk_create(
            get_user_model()(username=f"volume.alu{i:05d}", perfil="DISCENTE") for i in range(LIMITE_DA_BUSCA + 5)
        )
        resposta = self.client.get(self.url)
        self.assertEqual(len(self.opcoes(resposta)), LIMITE_DA_BUSCA)
        self.assertContains(resposta, f"Mostrando {LIMITE_DA_BUSCA} de {LIMITE_DA_BUSCA + 8} encontrados")

    def test_matricula_aceita_aluno_fora_da_lista_mostrada(self):
        resposta = self.client.post(
            self.url + "?q=bruno", {"turma": self.turma.pk, "discente": self.ana.pk, "status": "ATIVA"}
        )
        self.assertRedirects(resposta, reverse("lista_turmas"))
        self.assertTrue(Matricula.objects.filter(turma=self.turma, discente=self.ana).exists())

    def test_tela_tem_campo_de_busca(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'name="q"')
        self.assertContains(resposta, 'id="busca_turma"')
        self.assertContains(resposta, 'id="id_turma"')
