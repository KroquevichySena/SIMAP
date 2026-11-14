"""Login e aceite separado, com bloqueio dos demais endpoints até o consentimento."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from auditoria.models import Acao, RegistroAuditoria

from .acesso import url_primeiro_acesso
from .models import AceiteTermos


class PrimeiroAcessoTest(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="aluno.token", password="SenhaTeste123", perfil="DISCENTE"
        )
        self.destino = reverse("chamada:confirmar_presenca")
        self.primeiro = reverse("primeiro_acesso")

    def entrar(self):
        return self.client.post(reverse("login"), {
            "username": self.usuario.username, "password": "SenhaTeste123", "next": self.destino,
        })

    def aceitar(self, **extra):
        return self.client.post(self.primeiro, {
            "aceite_termos": "on", "versao": settings.TERMOS_DE_USO_VERSAO,
            "next": self.destino, **extra,
        })

    def test_login_sem_checkbox_autentica_e_encaminha_para_aceite(self):
        self.assertNotContains(self.client.get(reverse("login")), 'name="aceite_termos"')
        self.assertRedirects(self.entrar(), url_primeiro_acesso(self.destino))
        self.assertIn("_auth_user_id", self.client.session)
        self.assertFalse(AceiteTermos.objects.filter(usuario=self.usuario).exists())

    def test_checkbox_enviado_no_login_nao_registra_aceite(self):
        self.client.post(reverse("login"), {
            "username": self.usuario.username, "password": "SenhaTeste123", "aceite_termos": "on",
        })
        self.assertFalse(AceiteTermos.objects.filter(usuario=self.usuario).exists())

    def test_aceite_vazio_nao_libera_o_sistema(self):
        self.entrar()
        r = self.aceitar(aceite_termos="")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"]["aceite_termos"].errors)
        self.assertFalse(AceiteTermos.objects.filter(usuario=self.usuario).exists())
        self.assertRedirects(self.client.get(self.destino), url_primeiro_acesso(self.destino))

    def test_aceite_registra_usuario_ip_versao_e_auditoria(self):
        self.entrar()
        self.assertRedirects(self.aceitar(), self.destino)
        aceite = AceiteTermos.objects.get(usuario=self.usuario)
        self.assertEqual(aceite.versao, settings.TERMOS_DE_USO_VERSAO)
        self.assertEqual(aceite.ip_address, "127.0.0.1")
        registro = RegistroAuditoria.objects.get(
            acao=Acao.CRIACAO, entidade="usuarios.AceiteTermos", objeto_id=str(aceite.pk)
        )
        self.assertEqual(registro.usuario, self.usuario)
        self.aceitar()
        self.assertEqual(AceiteTermos.objects.filter(usuario=self.usuario).count(), 1)

    def test_quem_ja_aceitou_entra_diretamente(self):
        AceiteTermos.objects.create(usuario=self.usuario, versao=settings.TERMOS_DE_USO_VERSAO)
        self.assertRedirects(self.entrar(), self.destino)

    def test_nova_versao_exige_aceite_inclusive_em_sessao_existente(self):
        self.entrar()
        self.aceitar()
        with override_settings(TERMOS_DE_USO_VERSAO="nova"):
            self.assertRedirects(self.client.get(self.destino), url_primeiro_acesso(self.destino))
            r = self.aceitar(versao="antiga")
            self.assertEqual(r.status_code, 200)
            self.assertFalse(AceiteTermos.objects.filter(usuario=self.usuario, versao="nova").exists())
            self.assertRedirects(self.aceitar(), self.destino)

    def test_bloqueia_get_e_post_diretos_sem_reexecutar_operacao(self):
        self.client.force_login(self.usuario)
        self.assertRedirects(self.client.get(self.destino), url_primeiro_acesso(self.destino))
        r = self.client.post(self.destino, {"token_chamada": "ABC123"})
        self.assertRedirects(r, url_primeiro_acesso(reverse("core:dashboard")))

    def test_termos_e_logout_continuam_disponiveis_sem_aceite(self):
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(reverse("termos_de_uso")), "Termos de Uso")
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))

    def test_destinos_externos_e_loops_sao_recusados(self):
        self.client.force_login(self.usuario)
        for destino in ["https://externo.example/", "//externo.example/", "/\\externo.example/", self.primeiro]:
            with self.subTest(destino=destino):
                r = self.aceitar(next=destino)
                self.assertEqual(r.url, reverse("core:dashboard"))

    def test_visitante_precisa_autenticar_e_post_exige_csrf(self):
        self.assertEqual(self.client.get(self.primeiro).status_code, 302)
        self.assertEqual(self.client.post(self.primeiro, {"aceite_termos": "on"}).status_code, 302)
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.usuario)
        self.assertEqual(
            c.post(self.primeiro, {"aceite_termos": "on", "versao": settings.TERMOS_DE_USO_VERSAO}).status_code, 403
        )

    def test_primeiro_acesso_pendencia_tambem_bloqueia_admin_e_downloads(self):
        coord = get_user_model().objects.create_superuser(username="coord")
        self.client.force_login(coord)
        for url in [reverse("admin:index"), reverse("auditoria:registro_list"), "/entregas/anexos/999/"]:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), url_primeiro_acesso(url))
