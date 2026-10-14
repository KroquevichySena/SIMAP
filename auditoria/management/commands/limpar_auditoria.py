"""
Apaga os registros de auditoria mais antigos que o prazo de retenção.

A LGPD pede que dados pessoais não fiquem guardados para sempre, e a
auditoria guarda IP, navegador e o histórico de acesso de cada pessoa.
A ideia é rodar isto uma vez por dia (no Render, com um Cron Job):

    python manage.py limpar_auditoria
    python manage.py limpar_auditoria --dias 90
    python manage.py limpar_auditoria --simular
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auditoria.models import Acao, RegistroAuditoria
from auditoria.servicos import registrar


class Command(BaseCommand):
    help = "Remove registros de auditoria mais antigos que o prazo de retenção."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int,
            default=getattr(settings, "AUDITORIA_RETENCAO_DIAS", 180),
            help="Prazo de retenção em dias (padrão: AUDITORIA_RETENCAO_DIAS).",
        )
        parser.add_argument(
            "--simular", action="store_true",
            help="Apenas mostra quantos registros seriam removidos.",
        )

    def handle(self, *args, dias, simular, **options):
        if dias < 1:
            raise CommandError("O prazo de retenção deve ser de pelo menos 1 dia.")

        limite = timezone.now() - timedelta(days=dias)
        antigos = RegistroAuditoria.objects.filter(data_hora__lt=limite)
        total = antigos.count()

        if simular:
            self.stdout.write(f"{total} registro(s) anteriores a {limite:%d/%m/%Y} seriam removidos.")
            return

        # Apagar em lote pelo queryset não passa pelo delete() do modelo,
        # então o bloqueio de exclusão individual não atrapalha aqui. É de
        # propósito: essa é a única porta de saída permitida.
        antigos.delete()
        registrar(
            Acao.EXPURGO,
            descricao=f"{total} registro(s) anteriores a {limite:%d/%m/%Y} removidos (retenção de {dias} dias).",
            dados={"removidos": total, "retencao_dias": dias},
        )
        self.stdout.write(self.style.SUCCESS(f"{total} registro(s) removidos."))
