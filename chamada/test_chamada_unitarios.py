
from datetime import datetime, timedelta
from datetime import timezone as fuso
from unittest.mock import MagicMock, PropertyMock, patch

from django import forms
from django.test import SimpleTestCase

from chamada.forms import ConfirmarPresencaForm, Usuario
from chamada.models import Chamada

AGORA = datetime(2026, 10, 6, 10, 0, tzinfo=fuso.utc)
RELOGIO = "chamada.models.timezone.now"
MATRICULAS = "chamada.forms.Matricula.objects"
CHAMADAS = "chamada.forms.Chamada.objects"
PRESENCAS = "chamada.forms.Registro_de_Presenca.objects"
USUARIOS = "chamada.forms.Usuario.objects"


def chamada_expirando_em(minutos, limite=3):
    return Chamada(
        data_expiracao=AGORA + timedelta(minutes=minutos), limite_uso=limite
    )


def com_presencas(quantidade):
    """Substitui o gerenciador `presencas` por um mock que conta `quantidade`."""
    gerenciador = MagicMock()
    gerenciador.count.return_value = quantidade
    return patch.object(
        Chamada, "presencas", new_callable=PropertyMock, return_value=gerenciador
    )


@patch(RELOGIO, return_value=AGORA)
class ChamadaTest(SimpleTestCase):

    # ---------- caminho feliz ----------
    def test_deve_ser_valida_quando_nao_expirou_e_ainda_ha_vagas(self, _relogio):
        chamada = chamada_expirando_em(10, limite=3)

        with com_presencas(2):
            self.assertFalse(chamada.esta_expirada)
            self.assertFalse(chamada.vagas_esgotadas)
            self.assertTrue(chamada.esta_valida)

    # ---------- violação ----------
    def test_deve_estar_expirada_quando_o_prazo_ja_passou(self, _relogio):
        chamada = chamada_expirando_em(-1)

        with com_presencas(0):
            self.assertTrue(chamada.esta_expirada)
            self.assertFalse(chamada.esta_valida)

    # ---------- casos-limite ----------
    def test_nao_deve_estar_expirada_no_exato_instante_do_prazo(self, _relogio):
        chamada = chamada_expirando_em(0)

        self.assertFalse(chamada.esta_expirada)

    def test_deve_esgotar_as_vagas_quando_as_presencas_igualam_o_limite(self, _relogio):
        chamada = chamada_expirando_em(10, limite=3)

        with com_presencas(3):
            self.assertTrue(chamada.vagas_esgotadas)
            self.assertFalse(chamada.esta_valida)

    # ---------- parametrizado (subTest) ----------
    def test_deve_validar_a_combinacao_de_prazo_e_vagas(self, _relogio):
        casos = [
            # (minutos até expirar, presenças já registradas, esperado)
            (10, 0, True),
            (10, 2, True),
            (10, 3, False),
            (0, 3, False),
            (-1, 0, False),
            (-1, 3, False),
        ]
        for minutos, presencas, esperado in casos:
            with self.subTest(minutos=minutos, presencas=presencas):
                chamada = chamada_expirando_em(minutos, limite=3)
                with com_presencas(presencas):
                    self.assertEqual(chamada.esta_valida, esperado)


def montar_form(turma="turma", token="AULA01", discente="discente"):
    """Cria o formulário sem validar campos (evita consultar o banco)."""
    form = ConfirmarPresencaForm()
    form.cleaned_data = {"username": "ana", "turma": turma, "token_chamada": token}
    form.discente = discente
    return form


class ConfirmarPresencaFormTest(SimpleTestCase):

    # ---------- caminho feliz ----------
    @patch(PRESENCAS)
    @patch(CHAMADAS)
    @patch(MATRICULAS)
    def test_deve_aceitar_e_guardar_a_chamada_quando_todas_as_regras_passam(
        self, matriculas, chamadas, presencas
    ):
        chamada = MagicMock(esta_valida=True)
        matriculas.filter.return_value.exists.return_value = True
        chamadas.get.return_value = chamada
        presencas.filter.return_value.exists.return_value = False
        form = montar_form()

        dados = form.clean()

        self.assertIs(form.chamada, chamada)
        self.assertEqual(dados["token_chamada"], "AULA01")
        matriculas.filter.assert_called_once_with(turma="turma", discente="discente")
        presencas.filter.assert_called_once_with(chamada=chamada, discente="discente")

    # ---------- violações / exceções ----------
    @patch(CHAMADAS)
    @patch(MATRICULAS)
    def test_deve_rejeitar_quando_o_aluno_nao_esta_matriculado_na_turma(
        self, matriculas, chamadas
    ):
        matriculas.filter.return_value.exists.return_value = False

        with self.assertRaisesMessage(
            forms.ValidationError, "Você não está matriculado nesta turma."
        ):
            montar_form().clean()

        chamadas.get.assert_not_called()

    @patch(CHAMADAS)
    @patch(MATRICULAS)
    def test_deve_rejeitar_quando_o_token_nao_existe_para_a_turma(
        self, matriculas, chamadas
    ):
        matriculas.filter.return_value.exists.return_value = True
        chamadas.get.side_effect = Chamada.DoesNotExist

        with self.assertRaisesMessage(
            forms.ValidationError, "Token inválido para a turma selecionada."
        ):
            montar_form().clean()

    @patch(PRESENCAS)
    @patch(CHAMADAS)
    @patch(MATRICULAS)
    def test_deve_rejeitar_quando_a_chamada_expirou(self, matriculas, chamadas, presencas):
        matriculas.filter.return_value.exists.return_value = True
        chamadas.get.return_value = MagicMock(esta_valida=False, esta_expirada=True)

        with self.assertRaisesMessage(forms.ValidationError, "Essa chamada já expirou."):
            montar_form().clean()

        presencas.filter.assert_not_called()

    @patch(PRESENCAS)
    @patch(CHAMADAS)
    @patch(MATRICULAS)
    def test_deve_rejeitar_quando_a_presenca_ja_foi_confirmada(
        self, matriculas, chamadas, presencas
    ):
        matriculas.filter.return_value.exists.return_value = True
        chamadas.get.return_value = MagicMock(esta_valida=True)
        presencas.filter.return_value.exists.return_value = True

        with self.assertRaisesMessage(
            forms.ValidationError, "Você já confirmou presença nesta chamada."
        ):
            montar_form().clean()

    @patch(USUARIOS)
    def test_deve_rejeitar_usuario_que_nao_e_discente_ativo(self, usuarios):
        usuarios.get.side_effect = Usuario.DoesNotExist
        form = ConfirmarPresencaForm()
        form.cleaned_data = {"username": "fantasma"}

        with self.assertRaisesMessage(
            forms.ValidationError, "não é um discente ativo"
        ):
            form.clean_username()

    # ---------- casos-limite ----------
    @patch(MATRICULAS)
    def test_nao_deve_consultar_o_banco_quando_falta_algum_dado_do_formulario(
        self, matriculas
    ):
        form = montar_form(turma=None)

        dados = form.clean()

        self.assertIs(dados, form.cleaned_data)
        matriculas.filter.assert_not_called()

    @patch(PRESENCAS)
    @patch(CHAMADAS)
    @patch(MATRICULAS)
    def test_deve_informar_o_limite_de_uso_quando_as_vagas_acabaram(
        self, matriculas, chamadas, presencas
    ):
        matriculas.filter.return_value.exists.return_value = True
        chamadas.get.return_value = MagicMock(esta_valida=False, esta_expirada=False)

        with self.assertRaisesMessage(forms.ValidationError, "atingiu o limite de uso"):
            montar_form().clean()

    # ---------- parametrizado (subTest) ----------
    def test_deve_normalizar_o_token_para_maiusculas(self):
        casos = [("aula01", "AULA01"), ("AbC123", "ABC123"), ("", "")]
        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                form = ConfirmarPresencaForm()
                form.cleaned_data = {"token_chamada": entrada}

                self.assertEqual(form.clean_token_chamada(), esperado)

    # ---------- interação com dependência mockada ----------
    @patch(PRESENCAS)
    def test_deve_criar_o_registro_com_a_chamada_e_o_discente_validados(self, presencas):
        form = montar_form()
        form.chamada = "chamada-validada"

        form.save()

        presencas.create.assert_called_once_with(
            chamada="chamada-validada", discente="discente"
        )
