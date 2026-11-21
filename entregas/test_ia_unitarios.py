"""Parecer consultivo da IA sobre a entrega, sem banco e sem chamar o Gemini."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from . import ia_services
from .models import STATUS_CONCLUIDO, STATUS_ERRO

SUBMISSAO = SimpleNamespace(
    pk=5,
    atividade=SimpleNamespace(enunciado="Explique o que é uma variável."),
    resposta_texto="É um espaço na memória com um nome.",
    aluno=SimpleNamespace(first_name="Bia", email="bia@example.test", rgm="12345"),
)


@mock.patch.object(ia_services, "genai")
@mock.patch.object(ia_services.AnaliseIA.objects, "get_or_create")
class GerarAnaliseTest(SimpleTestCase):
    def test_parecer_e_guardado_quando_a_ia_responde(self, get_or_create, genai):
        analise = mock.MagicMock()
        get_or_create.return_value = (analise, True)
        genai.GenerativeModel.return_value.generate_content.return_value = SimpleNamespace(text="Resposta correta.")

        ia_services.gerar_analise(SUBMISSAO)

        self.assertEqual(analise.parecer_texto, "Resposta correta.")
        self.assertEqual(analise.status, STATUS_CONCLUIDO)
        analise.save.assert_called_once()

    def test_falha_da_ia_fica_registrada_como_erro(self, get_or_create, genai):
        analise = mock.MagicMock()
        get_or_create.return_value = (analise, False)
        genai.GenerativeModel.return_value.generate_content.side_effect = TimeoutError

        with self.assertLogs("entregas.ia_services", level="ERROR"):
            ia_services.gerar_analise(SUBMISSAO)

        self.assertEqual(analise.status, STATUS_ERRO)
        analise.save.assert_called_once()

    def test_pedido_tem_tempo_limite(self, get_or_create, genai):
        get_or_create.return_value = (mock.MagicMock(), True)

        ia_services.gerar_analise(SUBMISSAO)

        opcoes = genai.GenerativeModel.return_value.generate_content.call_args.kwargs["request_options"]
        self.assertEqual(opcoes, {"timeout": ia_services.GEMINI_TIMEOUT_SEGUNDOS})


class PromptTest(SimpleTestCase):
    def test_leva_enunciado_e_resposta_mas_nao_os_dados_do_aluno(self):
        prompt = ia_services._montar_prompt(SUBMISSAO)

        self.assertIn("Explique o que é uma variável.", prompt)
        self.assertIn("É um espaço na memória com um nome.", prompt)
        for dado_pessoal in ("Bia", "bia@example.test", "12345"):
            self.assertNotIn(dado_pessoal, prompt)
