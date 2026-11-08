"""
Avisa os alunos de atividades com prazo chegando que eles ainda não entregaram.

Uso:
    python manage.py notificar_prazos            # prazos nas próximas 24 horas
    python manage.py notificar_prazos --horas 48

A ideia é rodar isso uma vez por hora (cron do servidor ou o agendador do
Render). Rodar várias vezes não repete o aviso: cada aluno recebe um único
lembrete por atividade.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from comunicacao.models import Notificacao
from comunicacao.permissoes import alunos_da_turma
from core.avisos import url_da_atividade
from core.models import Atividade


class Command(BaseCommand):
    help = "Notifica os alunos sobre atividades com prazo próximo que ainda não foram entregues."

    def add_arguments(self, parser):
        parser.add_argument(
            "--horas", type=int, default=24,
            help="Janela, em horas a partir de agora, para considerar o prazo próximo (padrão: 24).",
        )

    def handle(self, *args, horas, **options):
        if horas < 1:
            raise CommandError("--horas precisa ser pelo menos 1.")
        agora = timezone.now()
        atividades = (
            Atividade.objects.filter(
                publicada=True,
                trilha__publicada=True,
                trilha__turma__ativa=True,
                prazo__gt=agora,
                prazo__lte=agora + timedelta(hours=horas),
            )
            .select_related("trilha__turma")
            .order_by("prazo")
        )

        total = 0
        for atividade in atividades:
            url = url_da_atividade(atividade)
            ja_entregaram = set(atividade.submissoes.values_list("aluno_id", flat=True))
            ja_avisados = set(
                Notificacao.objects.filter(tipo=Notificacao.Tipo.PRAZO, url=url)
                .values_list("destinatario_id", flat=True)
            )
            prazo = timezone.localtime(atividade.prazo)
            mensagem = (
                f"O prazo de \"{atividade.titulo[:80]}\" termina em "
                f"{prazo:%d/%m às %H:%M} e você ainda não entregou."
            )
            novas = [
                Notificacao(destinatario=aluno, tipo=Notificacao.Tipo.PRAZO, mensagem=mensagem[:255], url=url)
                for aluno in alunos_da_turma(atividade.trilha.turma)
                if aluno.pk not in ja_entregaram and aluno.pk not in ja_avisados
            ]
            Notificacao.objects.bulk_create(novas)
            total += len(novas)

        self.stdout.write(self.style.SUCCESS(f"{total} lembrete(s) de prazo enviado(s)."))
