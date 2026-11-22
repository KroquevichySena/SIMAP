"""Perfil explícito, rotas separadas, barreira geral do Admin e migração de contas."""

import importlib
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from turmas.models import Turma

from .test_helpers import registrar_aceites_atuais


class PerfilCoordenacaoTest(TestCase):
    def setUp(self):
        self.Usuario = get_user_model()
        self.coord = self.Usuario.objects.create_superuser("coord", password="SenhaCoordenacao123!")
        self.prof = self.Usuario.objects.create_user("prof", perfil="DOCENTE", password="SenhaDocente123!")
        self.aluno = self.Usuario.objects.create_user("aluno", perfil="DISCENTE")
        registrar_aceites_atuais(self.Usuario.objects.all())
        self.turma = Turma.objects.create(nome="Algoritmos", periodo="2026/2", docente=self.prof)
        self.client.force_login(self.coord)

    def test_superusuario_novo_tem_perfil_explicito_e_nao_acumula_papeis(self):
        self.assertEqual(self.coord.perfil, "COORDENACAO")
        self.assertTrue(self.coord.is_coordenacao)
        self.assertFalse(self.coord.is_docente)
        self.assertFalse(self.coord.is_discente)
        for perfil in ("", "DOCENTE", "DISCENTE"):
            with self.subTest(perfil=perfil), self.assertRaises(ValueError):
                self.Usuario.objects.create_superuser(f"invalido-{perfil}", perfil=perfil)

    def test_coordenacao_acessa_gestao_auditoria_e_admin_sem_links_academicos(self):
        self.assertRedirects(self.client.get(reverse("core:dashboard")), reverse("usuarios_lista"))
        resposta = self.client.get(reverse("usuarios_lista"))
        self.assertContains(resposta, "Coordenação")
        self.assertNotContains(resposta, ">Painel</a>")
        self.assertNotContains(resposta, f'href="{reverse("lista_turmas")}"')
        self.assertNotContains(resposta, f'href="{reverse("chamada:abrir_chamada")}"')
        self.assertEqual(self.client.get(reverse("auditoria:registro_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_rotas_academicas_sao_negadas_a_coordenacao_tambem_por_post(self):
        rotas = [
            reverse("criar_turma"),
            reverse("criar_matricula"),
            reverse("configurar_turma", args=[self.turma.pk]),
            reverse("matriculas_turma", args=[self.turma.pk]),
            reverse("core:trilha_list"),
            reverse("core:atividade_list"),
            reverse("core:minhas_trilhas"),
            reverse("painel:docente"),
            reverse("painel:discente"),
        ]
        for rota in rotas:
            for metodo in (self.client.get, self.client.post):
                with self.subTest(rota=rota, metodo=metodo.__name__):
                    self.assertEqual(metodo(rota, {}).status_code, 403)

    def test_chamada_redireciona_coordenacao_sem_liberar_formulario(self):
        for nome in ("chamada:abrir_chamada", "chamada:confirmar_presenca"):
            for metodo in (self.client.get, self.client.post):
                self.assertRedirects(
                    metodo(reverse(nome), {}), reverse("core:dashboard"), fetch_redirect_response=False
                )

    def test_coordenacao_nao_modifica_chamadas_das_turmas_legadas(self):
        from datetime import timedelta

        from django.utils import timezone

        from chamada.models import Chamada, Registro_de_Presenca

        self.turma.docente = self.coord
        self.turma.save()
        chamada = Chamada.objects.create(
            turma=self.turma,
            token_chamada="TESTE1",
            data_expiracao=timezone.now() - timedelta(seconds=1),
        )
        presenca = Registro_de_Presenca.objects.create(
            chamada=chamada,
            discente=self.aluno,
            situacao=Registro_de_Presenca.EM_ANALISE,
        )
        for nome, pk, dados in (
            ("chamada:renovar", chamada.pk, {}),
            ("chamada:finalizar", chamada.pk, {}),
            ("chamada:decidir_presenca", presenca.pk, {"acao": "aceitar"}),
        ):
            self.assertEqual(self.client.post(reverse(nome, args=[pk]), dados).status_code, 403)
        chamada.refresh_from_db()
        presenca.refresh_from_db()
        self.assertIsNone(chamada.finalizada_em)
        self.assertEqual(chamada.token_chamada, "TESTE1")
        self.assertEqual(presenca.situacao, Registro_de_Presenca.EM_ANALISE)

    def test_flags_tecnicas_nao_transformam_docente_ou_discente_em_coordenacao(self):
        for pessoa in (self.prof, self.aluno):
            pessoa.is_staff = True
            pessoa.is_superuser = True
            pessoa.save()
            self.assertFalse(pessoa.is_coordenacao)
            self.client.force_login(pessoa)
            for rota in ("usuarios_lista", "usuario_criar", "auditoria:registro_list", "admin:index"):
                with self.subTest(perfil=pessoa.perfil, rota=rota):
                    self.assertEqual(self.client.get(reverse(rota)).status_code, 403)
            # A barreira é geral, inclusive para modelos com o ModelAdmin padrão.
            self.assertEqual(self.client.get(reverse("admin:turmas_turma_changelist")).status_code, 403)

    def test_escolher_perfil_nao_concede_superusuario_ou_acesso_ao_admin(self):
        gestora = self.Usuario.objects.create_user("gestora", perfil="COORDENACAO")
        registrar_aceites_atuais([gestora])
        self.assertTrue(gestora.is_coordenacao)
        self.assertFalse(gestora.is_staff)
        self.assertFalse(gestora.is_superuser)
        self.client.force_login(gestora)
        self.assertEqual(self.client.get(reverse("usuarios_lista")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_login_do_admin_recusa_docente_mesmo_com_flags(self):
        self.prof.is_staff = True
        self.prof.is_superuser = True
        self.prof.save()
        self.client.logout()
        resposta = self.client.post(
            reverse("admin:login"),
            {
                "username": self.prof.username,
                "password": "SenhaDocente123!",
                "next": reverse("admin:index"),
            },
        )
        self.assertContains(resposta, "exclusivo da coordenação")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_mostra_tres_perfis_e_cadastro_comum_apenas_dois(self):
        admin = self.client.get(reverse("admin:usuarios_usuario_add"))
        escolhas_admin = dict(admin.context["adminform"].form.fields["perfil"].choices)
        self.assertEqual(escolhas_admin["COORDENACAO"], "Coordenação")
        comum = self.client.get(reverse("usuario_criar"))
        self.assertEqual(set(dict(comum.context["form"].fields["perfil"].choices)), {"DOCENTE", "DISCENTE"})
        resposta = self.client.post(
            reverse("usuario_criar"),
            {
                "first_name": "Nova",
                "last_name": "Conta",
                "username": "gestora-forjada",
                "email": "teste@example.test",
                "perfil": "COORDENACAO",
                "password1": "InicialForte123!",
                "password2": "InicialForte123!",
                "is_superuser": "on",
                "is_staff": "on",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("perfil", resposta.context["form"].errors)
        self.assertFalse(self.Usuario.objects.filter(username="gestora-forjada").exists())

    def test_admin_reserva_responsavel_para_docente_e_matricula_para_discente(self):
        resposta = self.client.get(reverse("admin:turmas_turma_change", args=[self.turma.pk]))
        docentes = resposta.context["adminform"].form.fields["docente"].queryset
        self.assertIn(self.prof, docentes)
        self.assertNotIn(self.coord, docentes)
        self.assertNotIn(self.aluno, docentes)
        resposta = self.client.get(reverse("admin:turmas_matricula_add"))
        discentes = resposta.context["adminform"].form.fields["discente"].queryset
        self.assertIn(self.aluno, discentes)
        self.assertNotIn(self.coord, discentes)
        self.assertNotIn(self.prof, discentes)

    def test_admin_transfere_turma_legada_sem_apagar_dados(self):
        self.turma.docente = self.coord
        self.turma.save()
        url = reverse("admin:turmas_turma_change", args=[self.turma.pk])
        dados = {
            "nome": self.turma.nome,
            "periodo": self.turma.periodo,
            "docente": self.coord.pk,
            "ativa": "on",
            "limite_atencao": "60",
            "instituicao": "",
        }
        resposta = self.client.post(url, dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("docente", resposta.context["adminform"].form.errors)
        dados["docente"] = self.prof.pk
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.docente, self.prof)
        self.assertEqual(self.turma.nome, "Algoritmos")

    def test_migracao_converte_admins_antigos_sem_promover_discente_ou_mudar_vinculos(self):
        antigo = self.Usuario.objects.create_user(
            "antigo",
            perfil="DOCENTE",
            is_superuser=True,
            is_staff=True,
            password="SenhaLegada123!",
        )
        sem_perfil = self.Usuario.objects.create_user("sem-perfil", is_superuser=True, is_staff=True)
        discente = self.Usuario.objects.create_user("inconsistente", perfil="DISCENTE", is_superuser=True)
        self.turma.docente = antigo
        self.turma.save()
        migracao = importlib.import_module("usuarios.migrations.0004_alter_usuario_managers_alter_usuario_perfil")
        migracao.separar_coordenacao(apps, SimpleNamespace(connection=connection))
        for pessoa in (antigo, sem_perfil):
            pessoa.refresh_from_db()
            self.assertTrue(pessoa.is_coordenacao)
            self.assertFalse(pessoa.is_docente)
        self.assertTrue(antigo.check_password("SenhaLegada123!"))
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.docente_id, antigo.pk)
        discente.refresh_from_db()
        self.assertEqual(discente.perfil, "DISCENTE")
        self.prof.refresh_from_db()
        self.assertEqual(self.prof.perfil, "DOCENTE")

    def test_reversao_remove_valor_longo_antes_de_reduzir_coluna(self):
        migracao = importlib.import_module("usuarios.migrations.0004_alter_usuario_managers_alter_usuario_perfil")
        migracao.reverter_perfil(apps, SimpleNamespace(connection=connection))
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.perfil, "")
        self.assertTrue(self.coord.is_superuser)

    def test_downloads_academicos_exigem_perfil_mesmo_com_vinculo_legado(self):
        from core.models import Atividade, MaterialDeApoio, TrilhaAprendizagem
        from entregas.models import AnexoSubmissao, Submissao
        from turmas.models import Matricula

        self.turma.docente = self.coord
        self.turma.save()
        trilha = TrilhaAprendizagem.objects.create(turma=self.turma, titulo="Trilha", publicada=True)
        atividade = Atividade.objects.create(trilha=trilha, titulo="Atividade", enunciado="Teste", publicada=True)
        submissao = Submissao.objects.create(atividade=atividade, aluno=self.aluno, resposta_texto="Resposta")
        arquivo = {
            "arquivo": "falso.txt",
            "nome_original": "falso.txt",
            "extensao": ".txt",
            "tipo_conteudo": "text/plain",
            "tamanho": 1,
            "sha256": "a" * 64,
        }
        material = MaterialDeApoio.objects.create(trilha=trilha, **arquivo)
        anexo = AnexoSubmissao.objects.create(submissao=submissao, **arquivo)
        Matricula.objects.create(turma=self.turma, discente=self.aluno)
        for url, funcao in (
            (reverse("core:baixar_material", args=[material.pk]), "core.views.resposta_de_download"),
            (reverse("entregas:baixar_anexo", args=[anexo.pk]), "entregas.views.resposta_de_download"),
        ):
            with patch(funcao, return_value=HttpResponse("arquivo")) as download:
                self.assertEqual(self.client.get(url).status_code, 404)
                download.assert_not_called()
                self.client.force_login(self.aluno)
                self.assertEqual(self.client.get(url).status_code, 200)
                self.client.force_login(self.coord)
