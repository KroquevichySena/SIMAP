"""Cadastra a versão 1.3 dos termos, que até aqui ficava escrita no template."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.db import migrations

PASTA = Path(__file__).resolve().parent.parent / "termos_iniciais"
PUBLICADA_EM = datetime(2026, 11, 15, tzinfo=ZoneInfo("America/Sao_Paulo"))


def cadastrar_1_3(apps, schema_editor):
    VersaoTermos = apps.get_model("usuarios", "VersaoTermos")
    if VersaoTermos.objects.exists():
        return
    versao = VersaoTermos.objects.create(
        numero="1.3",
        resumo=(PASTA / "1.3_resumo.txt").read_text(encoding="utf-8"),
        texto=(PASTA / "1.3_texto.txt").read_text(encoding="utf-8"),
    )
    VersaoTermos.objects.filter(pk=versao.pk).update(publicada_em=PUBLICADA_EM)


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0005_versaotermos")]

    operations = [migrations.RunPython(cadastrar_1_3, migrations.RunPython.noop)]
