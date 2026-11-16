"""Cenário fictício, repetição sem sobrescrever contas e limpeza limitada ao DEMO."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from turmas.models import Matricula, Turma

from .management.commands.popular_dados import COORDENACAO, DISCENTES, DOCENTES, SENHA_PADRAO, TURMA_DEMO
from .models import Atividade, TrilhaAprendizagem


@override_settings(DEBUG=True)
class PopularDadosTest(TestCase):
    def executar(self, **opcoes):
        saida = StringIO()
        call_command("popular_dados", stdout=saida, **opcoes)
        return saida.getvalue()

    def test_cria_tres_perfis_ficticios_sem_exibir_senha(self):
        saida = self.executar()
        Usuario = get_user_model()
        self.assertTrue(Usuario.objects.get(username=COORDENACAO[0]).is_coordenacao)
        docente = Usuario.objects.get(username=DOCENTES[0][0])
        self.assertTrue(docente.is_docente)
        self.assertFalse(docente.is_staff)
        self.assertFalse(docente.is_superuser)
        for usuario in Usuario.objects.all():
            self.assertTrue(usuario.username.startswith("demo."))
            self.assertTrue(usuario.email.endswith("@example.test"))
            self.assertTrue(usuario.troca_senha_obrigatoria)
            self.assertTrue(usuario.check_password(SENHA_PADRAO))
            if usuario.is_discente:
                self.assertTrue(usuario.rgm.startswith("DEMO-"))
        self.assertNotIn(SENHA_PADRAO, saida)
        self.assertFalse(Matricula.objects.filter(discente__username=DISCENTES[-1][0]).exists())

    def test_repetir_preserva_senha_modificada_e_nao_duplica_dados(self):
        self.executar()
        usuario = get_user_model().objects.get(username=DOCENTES[0][0])
        usuario.set_password("PessoalDiferente987!")
        usuario.troca_senha_obrigatoria = False
        usuario.save()
        contagens = (get_user_model().objects.count(), Turma.objects.count(), Atividade.objects.count())
        self.executar()
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("PessoalDiferente987!"))
        self.assertFalse(usuario.troca_senha_obrigatoria)
        self.assertEqual(
            contagens, (get_user_model().objects.count(), Turma.objects.count(), Atividade.objects.count())
        )

    def test_limpar_recria_apenas_turma_ficticia_e_preserva_outros_dados(self):
        outro = get_user_model().objects.create_user("outra.conta", perfil="DOCENTE")
        turma = Turma.objects.create(nome="Outra turma", periodo="2026/2", docente=outro)
        trilha = TrilhaAprendizagem.objects.create(turma=turma, titulo="Conteúdo preservado")
        atividade = Atividade.objects.create(trilha=trilha, titulo="Atividade preservada")
        self.executar()
        docente_pk = get_user_model().objects.get(username=DOCENTES[0][0]).pk
        self.executar(limpar=True)
        self.assertTrue(Atividade.objects.filter(pk=atividade.pk).exists())
        self.assertTrue(Turma.objects.filter(pk=turma.pk).exists())
        self.assertEqual(get_user_model().objects.get(username=DOCENTES[0][0]).pk, docente_pk)
        self.assertEqual(Turma.objects.filter(nome=TURMA_DEMO).count(), 1)

    def test_limpar_recusa_turma_demo_com_dados_de_outras_contas(self):
        self.executar()
        externo = get_user_model().objects.create_user("externo", perfil="DISCENTE")
        turma = Turma.objects.get(nome=TURMA_DEMO)
        matricula = Matricula.objects.create(turma=turma, discente=externo)
        with self.assertRaises(CommandError):
            self.executar(limpar=True)
        self.assertTrue(Matricula.objects.filter(pk=matricula.pk).exists())
        self.assertTrue(Turma.objects.filter(pk=turma.pk).exists())

    def test_colisao_com_conta_fora_do_cenario_cancela_sem_sobrescrever(self):
        usuario = get_user_model().objects.create_user(DOCENTES[0][0], perfil="DOCENTE", first_name="Preservar")
        with self.assertRaises(CommandError):
            self.executar()
        usuario.refresh_from_db()
        self.assertEqual(usuario.first_name, "Preservar")
        self.assertFalse(Turma.objects.exists())
        self.assertEqual(get_user_model().objects.count(), 1)

    @override_settings(DEBUG=False)
    def test_nao_executa_em_producao(self):
        with self.assertRaises(CommandError):
            self.executar()
        self.assertFalse(get_user_model().objects.exists())
