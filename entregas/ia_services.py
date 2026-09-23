import logging

import google.generativeai as genai
from django.conf import settings

from .models import AnaliseIA, STATUS_CONCLUIDO, STATUS_ERRO

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_TIMEOUT_SEGUNDOS = 10


def _montar_prompt(submissao):
    atividade = submissao.atividade
    return (
        "Você é um assistente que avalia respostas de alunos.\n\n"
        f"Enunciado da atividade:\n{atividade.enunciado}\n\n"
        f"Resposta do aluno:\n{submissao.resposta_texto}\n\n"
        "Escreva um parecer breve sobre a correção da resposta. "
        "Responda em texto simples, sem Markdown (sem **negrito**, sem `crases` ou listas)."
    )


def gerar_analise(submissao):
    """Gera (ou regenera) o parecer de IA para uma submissão."""
    analise, _ = AnaliseIA.objects.get_or_create(submissao=submissao)

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    try:
        resposta = model.generate_content(
            _montar_prompt(submissao),
            request_options={"timeout": GEMINI_TIMEOUT_SEGUNDOS},
        )
        analise.parecer_texto = resposta.text
        analise.status = STATUS_CONCLUIDO
    except Exception:
        logger.exception("Falha ao gerar análise de IA para submissão %s", submissao.pk)
        analise.status = STATUS_ERRO

    analise.save()
    return analise
