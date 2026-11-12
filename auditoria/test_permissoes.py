"""Discente não pode consultar a auditoria, mesmo com privilégios inconsistentes."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Acao, RegistroAuditoria


class PermissoesAuditoriaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.discentes = [
            Usuario.objects.create_user(
                username=f"discente-{indice}", perfil="DISCENTE",
                is_staff=staff, is_superuser=superusuario,
            )
            for indice, (staff, superusuario) in enumerate([
                (False, False), (True, False), (True, True), (False, True),
            ])
        ]
        cls.coordenadores = [
            Usuario.objects.create_superuser(username=f"coord-{indice}", perfil=perfil)
            for indice, perfil in enumerate(["", "DOCENTE"])
        ]
        cls.docente = Usuario.objects.create_user(username="docente", perfil="DOCENTE")
        cls.registro = RegistroAuditoria.objects.create(
            acao=Acao.ACESSO, descricao="DADO-RESTRITO-DA-AUDITORIA"
        )

    def test_discente_nao_abre_pagina_nem_exporta_csv(self):
        for usuario in self.discentes:
            self.client.force_login(usuario)
            for filtros in ({}, {"formato": "csv"}):
                with self.subTest(usuario=usuario.username, filtros=filtros):
                    resposta = self.client.get(reverse("auditoria:registro_list"), filtros)
                    self.assertEqual(resposta.status_code, 403)
                    self.assertNotContains(resposta, "DADO-RESTRITO-DA-AUDITORIA", status_code=403)

    def test_discente_nao_ve_link_no_menu(self):
        for usuario in self.discentes:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                resposta = self.client.get(reverse("termos_de_uso"))
                self.assertNotContains(resposta, f'href="{reverse("auditoria:registro_list")}"')

    def test_discente_superusuario_nao_acessa_registros_pelo_admin(self):
        usuario = next(u for u in self.discentes if u.is_staff and u.is_superuser)
        self.client.force_login(usuario)
        for url in [
            reverse("admin:auditoria_registroauditoria_changelist"),
            reverse("admin:auditoria_registroauditoria_change", args=[self.registro.pk]),
        ]:
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 403)
                self.assertNotContains(resposta, "DADO-RESTRITO-DA-AUDITORIA", status_code=403)

    def test_coordenacao_continua_com_acesso_a_tela_csv_menu_e_admin(self):
        for usuario in self.coordenadores:
            with self.subTest(perfil=usuario.perfil):
                self.client.force_login(usuario)
                url = reverse("auditoria:registro_list")
                self.assertEqual(self.client.get(url).status_code, 200)
                csv = self.client.get(url, {"formato": "csv"})
                self.assertEqual(csv.status_code, 200)
                self.assertIn(b"DADO-RESTRITO-DA-AUDITORIA", b"".join(csv.streaming_content))
                self.assertContains(self.client.get(reverse("termos_de_uso")), f'href="{url}"')
                self.assertEqual(self.client.get(reverse("admin:auditoria_registroauditoria_changelist")).status_code, 200)

    def test_docente_comum_nao_consulta(self):
        self.client.force_login(self.docente)
        self.assertEqual(self.client.get(reverse("auditoria:registro_list")).status_code, 403)

    def test_usuario_inativo_nao_tem_permissao(self):
        usuario = get_user_model()(perfil="DOCENTE", is_superuser=True, is_active=False)
        self.assertFalse(usuario.pode_consultar_auditoria)
