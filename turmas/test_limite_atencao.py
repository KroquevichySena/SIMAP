"""Configuração do limite pela turma, com validação e autorização no servidor."""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from painel.servicos import indicadores_da_turma
from usuarios.models import AceiteTermos
from .models import Matricula, Turma


class ConfiguracaoTurmaTest(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.professor = Usuario.objects.create_user(username="professor", perfil="DOCENTE")
        self.outro = Usuario.objects.create_user(username="outro", perfil="DOCENTE")
        self.aluno = Usuario.objects.create_user(username="aluno", perfil="DISCENTE")
        for pessoa in (self.professor, self.outro, self.aluno):
            AceiteTermos.objects.create(usuario=pessoa, versao=settings.TERMOS_DE_USO_VERSAO)
        self.turma = Turma.objects.create(nome="Algoritmos", periodo="2026/2", docente=self.professor)
        self.url = reverse("configurar_turma", args=[self.turma.pk])
        self.client.force_login(self.professor)

    def test_limite_tem_formulario_na_turma_e_link_no_painel(self):
        self.assertContains(self.client.get(self.url), 'name="limite_atencao"')
        self.assertContains(self.client.get(reverse("lista_turmas")), self.url)
        self.assertContains(self.client.get(reverse("matriculas_turma", args=[self.turma.pk])), self.url)
        painel = self.client.get(reverse("painel:docente"))
        self.assertContains(painel, self.url)
        self.assertNotContains(painel, 'name="limite_atencao"')

    def test_atualiza_so_o_limite_da_turma(self):
        resposta = self.client.post(self.url, {"limite_atencao": "72.5", "docente": self.outro.pk, "nome": "Forjado"})
        self.assertRedirects(resposta, self.url)
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.limite_atencao, Decimal("72.5"))
        self.assertEqual(self.turma.nome, "Algoritmos")
        self.assertEqual(self.turma.docente_id, self.professor.pk)
        self.assertContains(self.client.get(reverse("painel:docente")), "72,5%")

    def test_aceita_zero_e_cem_recusa_fora_do_intervalo_e_texto(self):
        for valor in ("0", "100"):
            with self.subTest(valor=valor):
                self.assertRedirects(self.client.post(self.url, {"limite_atencao": valor}), self.url)
                self.turma.refresh_from_db()
                self.assertEqual(self.turma.limite_atencao, Decimal(valor))
        for valor in ("-1", "101", "texto", "60.55", ""):
            with self.subTest(valor=valor):
                resposta = self.client.post(self.url, {"limite_atencao": valor})
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.context["form"].errors)
                self.turma.refresh_from_db()
                self.assertEqual(self.turma.limite_atencao, Decimal("100"))

    def test_outro_docente_e_discente_nao_conseguem_editar(self):
        for pessoa, codigo in ((self.outro, 404), (self.aluno, 403)):
            self.client.force_login(pessoa)
            for metodo in (self.client.get, self.client.post):
                with self.subTest(pessoa=pessoa.username, metodo=metodo.__name__):
                    self.assertEqual(metodo(self.url, {"limite_atencao": "99"}).status_code, codigo)
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.limite_atencao, Decimal("60"))

    def test_visitante_e_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.professor)
        self.assertEqual(cliente.post(self.url, {"limite_atencao": "80"}).status_code, 403)

    def test_cadastro_da_turma_aceita_limite_e_preserva_padrao_quando_omitido(self):
        for nome, valor in (("Nova", "75"), ("Sem alerta abaixo de zero", "0"), ("Padrao", None)):
            dados = {"nome": nome, "periodo": "2026/2", "ativa": "on"}
            if valor is not None:
                dados["limite_atencao"] = valor
            resposta = self.client.post(reverse("criar_turma"), dados)
            self.assertRedirects(resposta, reverse("lista_turmas"))
            self.assertEqual(Turma.objects.get(nome=nome).limite_atencao, Decimal(valor if valor is not None else "60"))

    def test_url_antiga_usa_mesma_validacao_e_destino_da_turma(self):
        resposta = self.client.post(reverse("painel:definir_limite", args=[self.turma.pk]), {"limite_atencao": "65"})
        self.assertRedirects(resposta, self.url)
        self.turma.refresh_from_db()
        self.assertEqual(self.turma.limite_atencao, Decimal("65"))

    def test_limite_alterado_muda_sinalizacao_inclusive_na_igualdade(self):
        from chamada.models import Chamada, Registro_de_Presenca
        from django.utils import timezone
        from datetime import timedelta
        Matricula.objects.create(turma=self.turma, discente=self.aluno)
        for indice in range(2):
            chamada = Chamada.objects.create(turma=self.turma, token_chamada=f"TOK{indice}", data_expiracao=timezone.now()+timedelta(hours=1), limite_uso=5)
            if indice == 0:
                Registro_de_Presenca.objects.create(chamada=chamada, discente=self.aluno)
        # Só a chamada concluída ou com presença entra na frequência. Para considerar
        # a segunda como falta, o prazo deve terminar depois da matrícula e antes de agora.
        Matricula.objects.filter(turma=self.turma).update(data_matricula=timezone.now()-timedelta(days=2))
        Chamada.objects.filter(turma=self.turma).update(data_expiracao=timezone.now()-timedelta(hours=1))
        self.assertTrue(indicadores_da_turma(self.turma)[0]["em_atencao"])
        self.client.post(self.url, {"limite_atencao": "50"})
        self.turma.refresh_from_db()
        self.assertFalse(indicadores_da_turma(self.turma)[0]["em_atencao"])
