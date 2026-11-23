"""Verifica atenção e envia/reprocessa os avisos persistentes do RF33."""

import time

from django.core.management.base import BaseCommand, CommandError

from comunicacao.emails_academicos import processar_pendentes, verificar_atencao


class Command(BaseCommand):
    help = "Verifica alunos em atenção e envia os e-mails acadêmicos pendentes (RF33)."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=200, help="Máximo de avisos processados por execução.")
        parser.add_argument(
            "--falhar-em-erro", action="store_true",
            help="Retorna erro ao agendador se algum envio falhar; os avisos continuam pendentes.",
        )
        parser.add_argument(
            "--intervalo",
            type=int,
            default=0,
            help="Segundos entre verificações. Zero executa uma vez; use 60 para acompanhar continuamente.",
        )

    def handle(self, *args, limite, intervalo, falhar_em_erro, **options):
        if limite < 1:
            raise CommandError("--limite precisa ser pelo menos 1.")
        if intervalo < 0:
            raise CommandError("--intervalo não pode ser negativo.")
        try:
            while True:
                novos = verificar_atencao()
                resultados = processar_pendentes(limite)
                self.stdout.write(
                    f"Novos alertas de atenção: {novos}. Resultados dos envios: {resultados}. "
                    "O destino real depende do EMAIL_BACKEND configurado."
                )
                if falhar_em_erro and resultados.get("falha", 0):
                    raise CommandError("Há falhas de envio. Os avisos permanecem pendentes para nova tentativa.")
                if intervalo == 0:
                    return
                time.sleep(intervalo)
        except KeyboardInterrupt:
            self.stdout.write("Acompanhamento interrompido.")
