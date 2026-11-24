"""Padroniza o período das turmas no formato da lista de seleção: 2026.2 vira 2026/2."""
import re

from django.db import migrations

FORMATO_ANTIGO = re.compile(r"^(\d{4})\.([12])$")


def padronizar(apps, schema_editor):
    Turma = apps.get_model("turmas", "Turma")
    for turma in Turma.objects.filter(periodo__regex=r"^\d{4}\.[12]$").only("pk", "periodo"):
        Turma.objects.filter(pk=turma.pk).update(periodo=FORMATO_ANTIGO.sub(r"\1/\2", turma.periodo))


class Migration(migrations.Migration):
    dependencies = [("turmas", "0006_instituicao_turma_instituicao")]

    operations = [migrations.RunPython(padronizar, migrations.RunPython.noop)]
