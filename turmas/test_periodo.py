"""O período da turma é escolhido numa lista de semestres, sempre no formato AAAA/S."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from usuarios.test_helpers import registrar_aceites_atuais

from .forms import TurmaForm
from .models import Turma
from .periodos import opcoes_de_periodo, periodo_atual


class OpcoesDePeriodoTest(SimpleTestCase):
    def test_vai_do_ano_anterior_ao_proximo(self):
        self.assertEqual(
            opcoes_de_periodo(date(2026, 11, 23)), ["2025/1", "2025/2", "2026/1", "2026/2", "2027/1", "2027/2"]
        )

    def test_semestre_atual_pelo_mes(self):
        self.assertEqual(periodo_atual(date(2026, 6, 30)), "2026/1")
        self.assertEqual(periodo_atual(date(2026, 7, 1)), "2026/2")


class CampoDePeriodoTest(TestCase):
    def setUp(self):
        self.docente = get_user_model().objects.create_user("prof.periodo", perfil="DOCENTE")
        registrar_aceites_atuais([self.docente])
        self.client.force_login(self.docente)

    def dados(self, periodo):
        return {"nome": "Algoritmos", "periodo": periodo, "ativa": "on", "limite_atencao": "60"}

    def test_tela_mostra_lista_com_o_semestre_atual_selecionado(self):
        resposta = self.client.get(reverse("criar_turma"))
        self.assertContains(resposta, '<select name="periodo"', html=False)
        self.assertContains(resposta, f'<option value="{periodo_atual()}" selected>', html=False)

    def test_aceita_semestre_da_lista(self):
        self.client.post(reverse("criar_turma"), self.dados(periodo_atual()))
        self.assertEqual(Turma.objects.get().periodo, periodo_atual())

    def test_recusa_texto_numero_ou_formato_fora_da_lista(self):
        ano = int(periodo_atual()[:4])
        for invalido in ("turma agora", "2026", str(ano) + ".2", f"{ano + 5}/1", f"{ano}/3", ""):
            with self.subTest(periodo=invalido):
                resposta = self.client.post(reverse("criar_turma"), self.dados(invalido))
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.context["form"].errors.get("periodo"))
        self.assertFalse(Turma.objects.exists())

    def test_turma_antiga_mantem_o_periodo_fora_da_lista_na_edicao(self):
        turma = Turma.objects.create(nome="Antiga", periodo="2019/1", docente=self.docente)
        form = TurmaForm(instance=turma)
        self.assertEqual(form.fields["periodo"].choices[0], ("2019/1", "2019/1"))
        self.assertEqual(form.fields["periodo"].initial, "2019/1")
        nova = TurmaForm()
        self.assertNotIn(("2019/1", "2019/1"), nova.fields["periodo"].choices)
