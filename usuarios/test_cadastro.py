"""Cadastro exclusivo da coordenação e separação entre conta e matrícula."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from auditoria.models import Acao, RegistroAuditoria
from turmas.models import Matricula

from .models import AceiteTermos


class CadastroUsuarioTest(TestCase):
    def setUp(self):
        self.Usuario = get_user_model()
        self.coord = self.Usuario.objects.create_superuser(username="coord")
        AceiteTermos.objects.create(usuario=self.coord, versao=settings.TERMOS_DE_USO_VERSAO)
        self.client.force_login(self.coord)
        self.url = reverse("usuario_criar")
        self.dados = {
            "first_name": "Maria", "last_name": "Silva", "username": "maria.silva",
            "email": "maria@example.test", "perfil": "DISCENTE", "rgm": "12345",
            "password1": "SenhaInicialForte123!", "password2": "SenhaInicialForte123!",
        }

    def test_coord_cadastra_discente_sem_privilegios_sem_aceite_sem_matricula(self):
        r = self.client.post(
            self.url, {**self.dados, "is_staff": "on", "is_superuser": "on", "is_active": "", "aceite_termos": "on"}
        )
        self.assertRedirects(r, reverse("usuarios_lista"))
        usuario = self.Usuario.objects.get(username="maria.silva")
        self.assertTrue(usuario.check_password(self.dados["password1"]))
        self.assertNotEqual(usuario.password, self.dados["password1"])
        self.assertTrue(usuario.is_active)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(AceiteTermos.objects.filter(usuario=usuario).exists())
        self.assertFalse(Matricula.objects.filter(discente=usuario).exists())
        log = RegistroAuditoria.objects.get(acao=Acao.CRIACAO, entidade="usuarios.Usuario", objeto_id=str(usuario.pk))
        self.assertEqual(log.usuario, self.coord)
        self.assertNotIn(self.dados["password1"], str(log.dados))

    def test_coord_cadastra_docente_sem_rgm(self):
        self.assertRedirects(
            self.client.post(self.url, {**self.dados, "perfil": "DOCENTE", "rgm": ""}), reverse("usuarios_lista")
        )
        self.assertTrue(self.Usuario.objects.get(username="maria.silva").is_docente)

    def test_docente_e_discente_nao_podem_listar_nem_cadastrar_mesmo_com_post_forjado(self):
        for perfil, superusuario in [("DOCENTE", False), ("DISCENTE", False), ("DISCENTE", True)]:
            usuario = self.Usuario.objects.create_user(
                username=f"{perfil}-{superusuario}", perfil=perfil, is_superuser=superusuario, is_staff=superusuario
            )
            AceiteTermos.objects.create(usuario=usuario, versao=settings.TERMOS_DE_USO_VERSAO)
            self.client.force_login(usuario)
            with self.subTest(perfil=perfil, superusuario=superusuario):
                self.assertEqual(self.client.get(reverse("usuarios_lista")).status_code, 403)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, self.dados).status_code, 403)
                self.assertNotContains(self.client.get(reverse("termos_de_uso")), f'href="{reverse("usuarios_lista")}"')
        self.assertFalse(self.Usuario.objects.filter(username="maria.silva").exists())

    def test_campos_obrigatorios_senha_fraca_e_perfil_administrativo_sao_recusados(self):
        for alteracoes, campo in [
            ({"rgm": ""}, "rgm"),
            ({"email": "invalido"}, "email"),
            ({"perfil": "COORDENACAO"}, "perfil"),
            ({"first_name": ""}, "first_name"),
            ({"password1": "123", "password2": "123"}, "password2"),
        ]:
            with self.subTest(campo=campo):
                r = self.client.post(self.url, {**self.dados, **alteracoes})
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.context["form"].errors)
                self.assertFalse(self.Usuario.objects.filter(username="maria.silva").exists())

    def test_username_duplicado_e_recusado(self):
        self.client.post(self.url, self.dados)
        r = self.client.post(self.url, self.dados)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"]["username"].errors)
        self.assertEqual(self.Usuario.objects.filter(username="maria.silva").count(), 1)

    def test_listagem_filtra_preserva_paginacao_e_nao_inclui_administradores(self):
        for indice in range(21):
            self.Usuario.objects.create_user(username=f"aluno-{indice}", perfil="DISCENTE", first_name="Aluno")
        r = self.client.get(reverse("usuarios_lista"), {"perfil": "DISCENTE", "q": "Aluno"})
        self.assertEqual(r.context["paginator"].count, 21)
        self.assertNotIn(self.coord, r.context["usuarios"])
        self.assertContains(r, "perfil=DISCENTE")
        r = self.client.get(reverse("usuarios_lista"), {"perfil": "DISCENTE", "q": "Aluno", "page": "2"})
        self.assertEqual(len(r.context["usuarios"]), 1)

    def test_visitante_e_redirecionado_e_cadastro_exige_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.get(reverse("admin:login")).status_code, 200)
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.coord)
        self.assertEqual(c.post(self.url, self.dados).status_code, 403)

    def test_coordenacao_tem_entrada_propria_e_menu(self):
        self.assertRedirects(self.client.get(reverse("core:dashboard")), reverse("usuarios_lista"))
        self.assertContains(self.client.get(reverse("usuarios_lista")), "Coordenação")

    def test_admin_tambem_reserva_cadastro_e_edicao_para_coordenacao(self):
        from django.contrib.auth.models import Permission

        for perfil, superusuario in [("DOCENTE", False), ("DISCENTE", True)]:
            usuario = self.Usuario.objects.create_user(
                username=f"staff-{perfil}",
                perfil=perfil,
                is_staff=True,
                is_superuser=superusuario,
            )
            usuario.user_permissions.add(
                *Permission.objects.filter(content_type__app_label="usuarios", content_type__model="usuario")
            )
            AceiteTermos.objects.create(usuario=usuario, versao=settings.TERMOS_DE_USO_VERSAO)
            self.client.force_login(usuario)
            for url in [
                reverse("admin:usuarios_usuario_add"),
                reverse("admin:usuarios_usuario_change", args=[usuario.pk]),
            ]:
                with self.subTest(perfil=perfil, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, self.dados).status_code, 403)

    def test_conta_criada_entra_no_primeiro_acesso_e_so_depois_nas_trilhas(self):
        self.client.post(self.url, self.dados)
        self.client.logout()
        destino = reverse("core:minhas_trilhas")
        r = self.client.post(
            reverse("login"), {"username": self.dados["username"], "password": self.dados["password1"], "next": destino}
        )
        self.assertIn(reverse("primeiro_acesso"), r.url)
        self.assertEqual(self.client.get(destino).status_code, 302)
        self.assertRedirects(
            self.client.post(
                reverse("primeiro_acesso"),
                {"aceite_termos": "on", "versao": settings.TERMOS_DE_USO_VERSAO, "next": destino},
            ),
            destino,
        )
