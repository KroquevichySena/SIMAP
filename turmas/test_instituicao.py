"""Cadastro de instituição pela coordenação e vínculo com as turmas."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditoria.models import Acao, RegistroAuditoria
from usuarios.models import AceiteTermos

from .models import Instituicao, Turma
from .periodos import periodo_atual


def criar_usuario(username, perfil="COORDENACAO"):
    Usuario = get_user_model()
    if perfil == "COORDENACAO":
        usuario = Usuario.objects.create_superuser(username=username)
    else:
        usuario = Usuario.objects.create_user(username=username, perfil=perfil)
    AceiteTermos.objects.create(usuario=usuario, versao=settings.TERMOS_DE_USO_VERSAO)
    return usuario


class InstituicaoTest(TestCase):
    def setUp(self):
        self.coord = criar_usuario("coord")
        self.docente = criar_usuario("prof", perfil="DOCENTE")
        self.turma_a = Turma.objects.create(nome="Algoritmos", periodo="2026/2", docente=self.docente)
        self.turma_b = Turma.objects.create(nome="Logica", periodo="2026/2", docente=self.docente)
        self.client.force_login(self.coord)
        self.dados = {
            "nome": "Campus Mogi",
            "coordenadas": "23°31'02.1\"S 46°10'58.5\"W",
            "raio_metros": "150",
            "precisao_minima": "100",
        }

    def test_coordenacao_cadastra_instituicao_e_vincula_turmas(self):
        resposta = self.client.post(reverse("criar_instituicao"), {**self.dados, "turmas": [self.turma_a.pk]})

        instituicao = Instituicao.objects.get(nome="Campus Mogi")
        self.assertRedirects(resposta, reverse("editar_instituicao", args=[instituicao.pk]))
        self.turma_a.refresh_from_db()
        self.turma_b.refresh_from_db()
        self.assertEqual(self.turma_a.instituicao, instituicao)
        self.assertIsNone(self.turma_b.instituicao)

    def test_desmarcar_turma_na_edicao_remove_o_vinculo(self):
        instituicao = Instituicao.objects.create(nome="Campus", latitude=-23.5, longitude=-46.1)
        Turma.objects.filter(pk__in=[self.turma_a.pk, self.turma_b.pk]).update(instituicao=instituicao)

        url = reverse("editar_instituicao", args=[instituicao.pk])
        self.client.post(url, {**self.dados, "turmas": [self.turma_b.pk]})

        self.turma_a.refresh_from_db()
        self.turma_b.refresh_from_db()
        self.assertIsNone(self.turma_a.instituicao)
        self.assertEqual(self.turma_b.instituicao, instituicao)

    def test_edicao_ja_vem_com_as_turmas_vinculadas_marcadas(self):
        instituicao = Instituicao.objects.create(nome="Campus")
        Turma.objects.filter(pk=self.turma_a.pk).update(instituicao=instituicao)

        form = self.client.get(reverse("editar_instituicao", args=[instituicao.pk])).context["form"]

        self.assertEqual(list(form["turmas"].value()), [self.turma_a.pk])

    def test_turma_de_outra_instituicao_nao_aparece_nem_e_aceita(self):
        outra = Instituicao.objects.create(nome="Outra")
        Turma.objects.filter(pk=self.turma_a.pk).update(instituicao=outra)

        form = self.client.get(reverse("criar_instituicao")).context["form"]
        self.assertNotIn(self.turma_a, form.fields["turmas"].queryset)

        resposta = self.client.post(reverse("criar_instituicao"), {**self.dados, "turmas": [self.turma_a.pk]})

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Instituicao.objects.filter(nome="Campus Mogi").exists())
        self.turma_a.refresh_from_db()
        self.assertEqual(self.turma_a.instituicao, outra)

    def test_coordenacao_cria_turma_dentro_da_instituicao(self):
        instituicao = Instituicao.objects.create(nome="Campus")
        url = reverse("criar_turma_instituicao", args=[instituicao.pk])
        dados = {"nome": "Estrutura de Dados", "periodo": periodo_atual(), "docente": self.docente.pk,
                 "ativa": "on", "limite_atencao": "60"}

        resposta = self.client.post(url, dados)

        self.assertRedirects(resposta, reverse("editar_instituicao", args=[instituicao.pk]))
        turma = Turma.objects.get(nome="Estrutura de Dados")
        self.assertEqual(turma.instituicao, instituicao)
        self.assertEqual(turma.docente, self.docente)

    def test_turma_nova_so_aceita_docente_ativo(self):
        discente = criar_usuario("aluno", perfil="DISCENTE")
        instituicao = Instituicao.objects.create(nome="Campus")
        url = reverse("criar_turma_instituicao", args=[instituicao.pk])

        resposta = self.client.post(url, {"nome": "X", "periodo": "2026/2", "docente": discente.pk})

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Turma.objects.filter(nome="X").exists())

    def test_botao_nova_turma_so_aparece_na_edicao(self):
        instituicao = Instituicao.objects.create(nome="Campus")
        url_nova_turma = reverse("criar_turma_instituicao", args=[instituicao.pk])

        self.assertContains(self.client.get(reverse("editar_instituicao", args=[instituicao.pk])), url_nova_turma)
        self.assertNotContains(self.client.get(reverse("criar_instituicao")), "/turmas/nova/")

    def test_mudanca_de_vinculo_fica_na_auditoria(self):
        self.client.post(reverse("criar_instituicao"), {**self.dados, "turmas": [self.turma_a.pk]})

        registro = RegistroAuditoria.objects.get(
            acao=Acao.ALTERACAO, entidade="turmas.Turma", objeto_id=str(self.turma_a.pk)
        )
        self.assertEqual(registro.usuario, self.coord)
        self.assertIn("instituicao", registro.dados)

    def test_coordenadas_do_maps_sao_gravadas_em_decimal(self):
        self.client.post(reverse("criar_instituicao"), self.dados)

        instituicao = Instituicao.objects.get()
        self.assertEqual(str(instituicao.latitude), "-23.517250")
        self.assertEqual(str(instituicao.longitude), "-46.182917")

    def test_edicao_mostra_as_coordenadas_salvas(self):
        instituicao = Instituicao.objects.create(nome="Campus", latitude="-23.517250", longitude="-46.182917")

        resposta = self.client.get(reverse("editar_instituicao", args=[instituicao.pk]))

        self.assertContains(resposta, 'value="-23.517250, -46.182917"')

    def test_so_a_latitude_e_recusada(self):
        resposta = self.client.post(reverse("criar_instituicao"), {**self.dados, "coordenadas": "23°31'02.1\"S"})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Informe a latitude e a longitude")
        self.assertFalse(Instituicao.objects.exists())

    def test_raio_fora_do_limite_e_recusado(self):
        resposta = self.client.post(reverse("criar_instituicao"), {**self.dados, "raio_metros": "10"})

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Instituicao.objects.exists())

    def test_instituicao_sem_coordenadas_e_aceita(self):
        dados = {**self.dados, "coordenadas": ""}

        self.assertEqual(self.client.post(reverse("criar_instituicao"), dados).status_code, 302)
        self.assertFalse(Instituicao.objects.get().tem_localizacao)

    def test_lista_mostra_quantidade_de_turmas(self):
        instituicao = Instituicao.objects.create(nome="Campus Centro")
        Turma.objects.filter(pk=self.turma_a.pk).update(instituicao=instituicao)

        resposta = self.client.get(reverse("lista_instituicoes"))

        self.assertContains(resposta, "Campus Centro")
        self.assertEqual(resposta.context["instituicoes"][0].total_turmas, 1)

    def test_docente_e_discente_recebem_403(self):
        discente = criar_usuario("aluno", perfil="DISCENTE")
        instituicao = Instituicao.objects.create(nome="Campus")
        urls = [
            reverse("lista_instituicoes"),
            reverse("criar_instituicao"),
            reverse("editar_instituicao", args=[instituicao.pk]),
            reverse("criar_turma_instituicao", args=[instituicao.pk]),
        ]
        for usuario in (self.docente, discente):
            self.client.force_login(usuario)
            for url in urls:
                with self.subTest(perfil=usuario.perfil, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, self.dados).status_code, 403)
        self.assertEqual(Instituicao.objects.count(), 1)

    def test_visitante_vai_para_o_login(self):
        self.client.logout()

        resposta = self.client.get(reverse("lista_instituicoes"))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("login"), resposta["Location"])
