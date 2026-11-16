"""Gestão pela coordenação: confirmação, preservação do histórico e bloqueio de acesso."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from auditoria.models import Acao, RegistroAuditoria
from turmas.models import Matricula, Turma

from .gestao import possui_historico
from .models import AceiteTermos
from .test_helpers import registrar_aceites_atuais


class GestaoUsuariosTest(TestCase):
    def setUp(self):
        self.Usuario = get_user_model()
        self.coord = self.Usuario.objects.create_superuser("coord")
        self.prof = self.Usuario.objects.create_user("prof", perfil="DOCENTE", password="SenhaProfessor123!")
        self.aluno = self.Usuario.objects.create_user(
            "aluno",
            perfil="DISCENTE",
            password="SenhaAluno123!",
            troca_senha_obrigatoria=True,
        )
        registrar_aceites_atuais([self.coord])
        self.client.force_login(self.coord)

    def url(self, acao, pessoa=None):
        return reverse("usuario_acao", args=[(pessoa or self.aluno).pk, acao])

    def confirmar(self, acao, pessoa=None):
        return self.client.post(self.url(acao, pessoa), {"confirmar": "on"})

    def test_lista_oferece_exclusao_desativacao_e_reativacao(self):
        self.prof.is_active = False
        self.prof.save(update_fields=["is_active"])
        resposta = self.client.get(reverse("usuarios_lista"))
        self.assertContains(resposta, self.url("desativar"))
        self.assertContains(resposta, self.url("reativar", self.prof))
        self.assertContains(resposta, self.url("excluir"))

    def test_get_nao_modifica_e_post_precisa_confirmacao(self):
        for acao in ("desativar", "reativar", "excluir"):
            with self.subTest(acao=acao):
                self.assertEqual(self.client.get(self.url(acao)).status_code, 200)
                resposta = self.client.post(self.url(acao), {})
                self.assertEqual(resposta.status_code, 200)
                self.assertIn("confirmar", resposta.context["form"].errors)
                self.aluno.refresh_from_db()
                self.assertTrue(self.aluno.is_active)

    def test_exclui_apenas_conta_nova_e_preserva_auditoria(self):
        pk = self.aluno.pk
        registro = RegistroAuditoria.objects.create(
            usuario=self.aluno,
            usuario_login="aluno",
            acao=Acao.ACESSO,
            descricao="Registro preservado",
        )
        self.assertFalse(possui_historico(self.aluno))
        self.assertRedirects(self.confirmar("excluir"), reverse("usuarios_lista"))
        self.assertFalse(self.Usuario.objects.filter(pk=pk).exists())
        registro.refresh_from_db()
        self.assertIsNone(registro.usuario_id)
        self.assertEqual(registro.usuario_login, "aluno")
        exclusao = RegistroAuditoria.objects.get(acao=Acao.EXCLUSAO, entidade="usuarios.Usuario", objeto_id=str(pk))
        self.assertEqual(exclusao.usuario, self.coord)

    def test_docente_novo_sem_turma_tambem_pode_ser_excluido(self):
        pk = self.prof.pk
        self.assertRedirects(self.confirmar("excluir", self.prof), reverse("usuarios_lista"))
        self.assertFalse(self.Usuario.objects.filter(pk=pk).exists())

    def test_conta_que_ja_entrou_e_orientada_a_desativacao(self):
        cliente_aluno = Client()
        cliente_aluno.force_login(self.aluno)
        self.aluno.refresh_from_db()
        self.assertTrue(possui_historico(self.aluno))
        pagina = self.client.get(self.url("excluir"))
        self.assertContains(pagina, "Esta conta possui histórico")
        self.assertContains(pagina, self.url("desativar"))
        resposta = self.confirmar("excluir")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].non_field_errors())
        self.assertTrue(self.Usuario.objects.filter(pk=self.aluno.pk).exists())

    def test_exclusao_reverifica_vinculos_criados_apos_abrir_confirmacao(self):
        self.assertFalse(self.client.get(self.url("excluir")).context["exclusao_bloqueada"])
        turma = Turma.objects.create(nome="Algoritmos", periodo="2026/2", docente=self.prof)
        matricula = Matricula.objects.create(turma=turma, discente=self.aluno)
        self.assertEqual(self.confirmar("excluir").status_code, 200)
        self.assertTrue(Matricula.objects.filter(pk=matricula.pk).exists())
        self.assertTrue(self.Usuario.objects.filter(pk=self.aluno.pk).exists())

    def test_professor_com_turma_nao_e_excluido_e_pode_ser_desativado(self):
        turma = Turma.objects.create(nome="Algoritmos", periodo="2026/2", docente=self.prof)
        self.assertEqual(self.confirmar("excluir", self.prof).status_code, 200)
        self.assertRedirects(self.confirmar("desativar", self.prof), reverse("usuarios_lista"))
        self.prof.refresh_from_db()
        self.assertFalse(self.prof.is_active)
        self.assertTrue(Turma.objects.filter(pk=turma.pk, docente=self.prof).exists())

    def test_aceites_tambem_impedem_exclusao_por_cascata(self):
        registrar_aceites_atuais([self.aluno])
        self.assertEqual(self.confirmar("excluir").status_code, 200)
        self.assertTrue(AceiteTermos.objects.filter(usuario=self.aluno).exists())

    def test_desativacao_interrompe_sessao_e_reativacao_preserva_dados_e_senha(self):
        registrar_aceites_atuais([self.aluno])
        self.aluno.troca_senha_obrigatoria = False
        self.aluno.save()
        turma = Turma.objects.create(nome="Algoritmos", periodo="2026/2", docente=self.prof)
        matricula = Matricula.objects.create(turma=turma, discente=self.aluno, status="INATIVA")
        cliente_aluno = Client()
        cliente_aluno.force_login(self.aluno)
        self.assertRedirects(self.confirmar("desativar"), reverse("usuarios_lista"))
        self.assertEqual(cliente_aluno.get(reverse("core:minhas_trilhas")).status_code, 302)
        self.assertFalse(Client().login(username="aluno", password="SenhaAluno123!"))
        self.assertRedirects(self.confirmar("reativar"), reverse("usuarios_lista"))
        self.aluno.refresh_from_db()
        matricula.refresh_from_db()
        self.assertTrue(self.aluno.check_password("SenhaAluno123!"))
        self.assertFalse(self.aluno.troca_senha_obrigatoria)
        self.assertEqual(matricula.status, "INATIVA")
        self.assertTrue(Client().login(username="aluno", password="SenhaAluno123!"))

    def test_repetir_desativar_nao_reativa_a_conta(self):
        self.confirmar("desativar")
        self.confirmar("desativar")
        self.aluno.refresh_from_db()
        self.assertFalse(self.aluno.is_active)

    def test_docentes_e_discentes_nao_gerenciam_contas_por_url_ou_post(self):
        self.aluno.troca_senha_obrigatoria = False
        self.aluno.save(update_fields=["troca_senha_obrigatoria"])
        registrar_aceites_atuais([self.prof, self.aluno])
        for pessoa in (self.prof, self.aluno):
            self.client.force_login(pessoa)
            for acao in ("desativar", "reativar", "excluir"):
                self.assertEqual(self.client.get(self.url(acao)).status_code, 403)
                self.assertEqual(self.confirmar(acao).status_code, 403)
        self.aluno.refresh_from_db()
        self.assertTrue(self.aluno.is_active)

    def test_post_nao_altera_perfil_privilegios_ou_senha(self):
        resposta = self.client.post(
            self.url("desativar"),
            {
                "confirmar": "on",
                "perfil": "COORDENACAO",
                "is_superuser": "on",
                "is_staff": "on",
                "password": "forjada",
            },
        )
        self.assertRedirects(resposta, reverse("usuarios_lista"))
        self.aluno.refresh_from_db()
        self.assertEqual(self.aluno.perfil, "DISCENTE")
        self.assertFalse(self.aluno.is_staff)
        self.assertFalse(self.aluno.is_superuser)
        self.assertTrue(self.aluno.check_password("SenhaAluno123!"))

    def test_contas_administrativas_e_propria_conta_nao_sao_alvos(self):
        staff = self.Usuario.objects.create_user("staff", perfil="DOCENTE", is_staff=True)
        superusuario = self.Usuario.objects.create_user("super", perfil="DOCENTE", is_superuser=True)
        outra_coord = self.Usuario.objects.create_user("gestora", perfil="COORDENACAO")
        for pessoa in (self.coord, staff, superusuario, outra_coord):
            for acao in ("desativar", "reativar", "excluir"):
                with self.subTest(pessoa=pessoa.username, acao=acao):
                    self.assertEqual(self.client.get(self.url(acao, pessoa)).status_code, 404)
                    self.assertEqual(self.confirmar(acao, pessoa).status_code, 404)
                    self.assertTrue(self.Usuario.objects.filter(pk=pessoa.pk, is_active=True).exists())

    def test_csrf_visitante_e_acao_desconhecida(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.coord)
        self.assertEqual(cliente.post(self.url("excluir"), {"confirmar": "on"}).status_code, 403)
        self.assertEqual(self.client.get(self.url("inexistente")).status_code, 404)
        self.client.logout()
        self.assertEqual(self.confirmar("excluir").status_code, 302)

    def test_protecao_referencial_e_tratada_sem_apagar_conta(self):
        from django.db.models.deletion import ProtectedError

        with patch.object(self.Usuario, "delete", side_effect=ProtectedError("Vínculo", [])):
            resposta = self.confirmar("excluir")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(self.Usuario.objects.filter(pk=self.aluno.pk).exists())
