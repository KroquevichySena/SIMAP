"""Troca obrigatória antes do aceite, das páginas e das operações do SIMAP."""
import importlib
from types import SimpleNamespace

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from auditoria.models import Acao, RegistroAuditoria
from turmas.models import Turma
from .acesso import url_primeiro_acesso, url_troca_senha
from .forms import SenhaTemporariaAdminForm
from .models import AceiteTermos


class SenhaTemporariaTest(TestCase):
    def setUp(self):
        self.senha_temporaria = "TemporariaInicial123!"
        self.senha_pessoal = "PessoalDiferente456!"
        self.usuario = get_user_model().objects.create_user(
            username="aluna.demo", perfil="DISCENTE", password=self.senha_temporaria,
            troca_senha_obrigatoria=True, email="aluna@example.test",
        )
        self.url = reverse("trocar_senha_temporaria")
        self.destino = reverse("core:minhas_trilhas")

    def entrar(self):
        return self.client.post(reverse("login"), {
            "username": self.usuario.username, "password": self.senha_temporaria, "next": self.destino,
        })

    def trocar(self, **alteracoes):
        return self.client.post(self.url, {
            "old_password": self.senha_temporaria, "new_password1": self.senha_pessoal,
            "new_password2": self.senha_pessoal, "next": self.destino, **alteracoes,
        })

    def test_login_encaminha_para_troca_antes_dos_termos(self):
        self.assertRedirects(self.entrar(), url_troca_senha(self.destino))
        self.assertFalse(AceiteTermos.objects.filter(usuario=self.usuario).exists())
        self.assertNotContains(self.client.get(self.url), 'class="simap-sidebar"')

    def test_urls_diretas_post_e_aceite_sao_bloqueados_ate_trocar(self):
        self.client.force_login(self.usuario)
        for url in (self.destino, reverse("primeiro_acesso"), reverse("admin:index"), "/entregas/anexos/999/"):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), url_troca_senha(url if url != reverse("primeiro_acesso") else reverse("core:dashboard")))
        resposta = self.client.post(reverse("primeiro_acesso"), {"aceite_termos": "on", "versao": settings.TERMOS_DE_USO_VERSAO})
        self.assertEqual(resposta.url, url_troca_senha(reverse("core:dashboard")))
        self.assertFalse(AceiteTermos.objects.exists())
        self.assertEqual(self.client.post(self.destino, {}).status_code, 302)

    def test_aceite_anterior_nao_dispensa_a_troca(self):
        AceiteTermos.objects.create(usuario=self.usuario, versao=settings.TERMOS_DE_USO_VERSAO)
        self.assertIn(self.url, self.entrar().url)
        self.assertRedirects(self.trocar(), self.destino)

    def test_senha_fraca_diferente_da_confirmacao_errada_ou_igual_nao_libera(self):
        self.client.force_login(self.usuario)
        for alteracao in (
            {"new_password1": "123", "new_password2": "123"},
            {"new_password2": "OutraConfirmacao123!"},
            {"old_password": "NaoEASenha123!"},
            {"new_password1": self.senha_temporaria, "new_password2": self.senha_temporaria},
        ):
            with self.subTest(alteracao=alteracao):
                resposta = self.trocar(**alteracao)
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.context["form"].errors)
                self.usuario.refresh_from_db()
                self.assertTrue(self.usuario.troca_senha_obrigatoria)
                self.assertTrue(self.usuario.check_password(self.senha_temporaria))

    def test_troca_preserva_sessao_invalida_senha_antiga_e_encaminha_ao_aceite(self):
        self.entrar()
        self.assertRedirects(self.trocar(), url_primeiro_acesso(self.destino))
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.troca_senha_obrigatoria)
        self.assertTrue(self.usuario.check_password(self.senha_pessoal))
        self.assertFalse(self.usuario.check_password(self.senha_temporaria))
        self.assertIn("_auth_user_id", self.client.session)
        self.assertFalse(AceiteTermos.objects.filter(usuario=self.usuario).exists())
        self.assertRedirects(self.client.post(reverse("primeiro_acesso"), {
            "aceite_termos": "on", "versao": settings.TERMOS_DE_USO_VERSAO, "next": self.destino,
        }), self.destino)
        self.client.logout()
        self.assertFalse(self.client.login(username=self.usuario.username, password=self.senha_temporaria))
        resposta = self.client.post(reverse("login"), {"username": self.usuario.username, "password": self.senha_pessoal, "next": self.destino})
        self.assertRedirects(resposta, self.destino)
        registro = RegistroAuditoria.objects.filter(acao=Acao.ALTERACAO, entidade="usuarios.Usuario", objeto_id=str(self.usuario.pk)).latest("id")
        self.assertNotIn(self.senha_pessoal, str(registro.dados))
        self.assertNotIn(self.senha_temporaria, str(registro.dados))

    def test_next_externo_loop_e_conta_forjada_nao_sao_aceitos(self):
        self.client.force_login(self.usuario)
        outro = get_user_model().objects.create_user(username="outro", password="OutraSenha123!")
        resposta = self.trocar(next="https://example.com/", usuario=outro.pk, troca_senha_obrigatoria="")
        self.assertEqual(resposta.url, url_primeiro_acesso(reverse("core:dashboard")))
        outro.refresh_from_db()
        self.assertTrue(outro.check_password("OutraSenha123!"))
        self.assertFalse(AceiteTermos.objects.filter(usuario=outro).exists())

    def test_pagina_exige_login_e_csrf(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        self.assertEqual(cliente.post(self.url, {}).status_code, 403)

    def test_recuperacao_de_senha_tambem_conclui_troca_obrigatoria(self):
        uid = urlsafe_base64_encode(force_bytes(self.usuario.pk))
        token = default_token_generator.make_token(self.usuario)
        resposta = self.client.get(reverse("password_reset_confirm", args=[uid, token]))
        resposta = self.client.post(resposta.url, {"new_password1": self.senha_pessoal, "new_password2": self.senha_pessoal})
        self.assertRedirects(resposta, reverse("password_reset_complete"))
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.troca_senha_obrigatoria)
        self.assertFalse(self.usuario.check_password(self.senha_temporaria))
        self.assertFalse(default_token_generator.check_token(self.usuario, token))

    def test_redefinicao_nao_pode_manter_a_senha_temporaria(self):
        uid = urlsafe_base64_encode(force_bytes(self.usuario.pk))
        token = default_token_generator.make_token(self.usuario)
        resposta = self.client.get(reverse("password_reset_confirm", args=[uid, token]))
        resposta = self.client.post(resposta.url, {"new_password1": self.senha_temporaria, "new_password2": self.senha_temporaria})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.troca_senha_obrigatoria)

    def test_termos_publicos_e_logout_disponiveis_durante_a_troca(self):
        AceiteTermos.objects.create(usuario=self.usuario, versao=settings.TERMOS_DE_USO_VERSAO)
        self.client.force_login(self.usuario)
        self.assertNotContains(self.client.get(reverse("termos_de_uso")), 'class="simap-sidebar"')
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))

    def test_redefinicao_pela_coordenacao_no_admin_exige_nova_troca(self):
        self.usuario.troca_senha_obrigatoria = False
        self.usuario.save()
        formulario = SenhaTemporariaAdminForm(self.usuario, {"password1": self.senha_pessoal, "password2": self.senha_pessoal})
        self.assertTrue(formulario.is_valid(), formulario.errors)
        formulario.save()
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.troca_senha_obrigatoria)

    def test_atualizacao_marca_contas_antigas_e_preserva_coordenacao(self):
        Usuario = get_user_model()
        docente = Usuario.objects.create_user(username="docente", perfil="DOCENTE")
        coord = Usuario.objects.create_superuser(username="coord", perfil="DOCENTE")
        migracao = importlib.import_module("usuarios.migrations.0003_usuario_troca_senha_obrigatoria")
        migracao.exigir_troca_das_contas_existentes(apps, SimpleNamespace(connection=connection))
        docente.refresh_from_db()
        coord.refresh_from_db()
        self.assertTrue(docente.troca_senha_obrigatoria)
        self.assertFalse(coord.troca_senha_obrigatoria)
