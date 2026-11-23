"""Executa o lote do RF33 sem publicar credenciais ou tracebacks nos logs do job."""

import logging
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit


def executar():
    obrigatorias = (
        "SECRET_KEY", "DATABASE_URL", "MAILGUN_API_KEY", "MAILGUN_DOMAIN", "DEFAULT_FROM_EMAIL",
    )
    ausentes = [nome for nome in obrigatorias if not os.environ.get(nome, "").strip()]
    if ausentes:
        print("Configuracao ausente: " + ", ".join(ausentes) + ". Confira os Secrets RF33 do repositorio.")
        return 1
    try:
        endereco = urlsplit(os.environ["DATABASE_URL"])
        valido = endereco.scheme in {"postgres", "postgresql"} and bool(endereco.hostname)
    except ValueError:
        valido = False
    if not valido:
        print("DATABASE_URL precisa apontar para o PostgreSQL de producao.")
        return 1
    if os.environ.get("EMAIL_BACKEND") != "usuarios.email_backend.MailgunEmailBackend":
        print("Configure o backend do Mailgun; backend console nao valida entrega de e-mail.")
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    os.environ["DJANGO_SETTINGS_MODULE"] = "SIMAP.settings"
    saida = StringIO()
    falhou = False
    categoria = ""
    # O repositorio e publico: nao publicar mensagens de excecoes de provedores,
    # consultas SQL ou detalhes de destinatarios. O resumo contem so contagens.
    nivel_anterior = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(saida), redirect_stderr(StringIO()):
            import django
            from django.core.management import call_command

            django.setup()
            call_command("notificar_acompanhamento", falhar_em_erro=True, stdout=saida)
    except Exception as erro:
        falhou = True
        categoria = type(erro).__name__
    finally:
        logging.disable(nivel_anterior)

    for linha in saida.getvalue().splitlines():
        if linha.startswith("Novos alertas de atenção:"):
            print(linha)
    if falhou:
        print(f"RF33 falhou ({categoria}). Confira conexao, configuracao Mailgun e destinatarios autorizados.")
        print("Nao ha garantia de rollback de envios ja realizados. Consulte os status antes de repetir.")
        return 1
    print("Verificacao concluida. Enviado significa aceito pelo Mailgun, nao leitura pelo destinatario.")
    return 0


if __name__ == "__main__":
    raise SystemExit(executar())
