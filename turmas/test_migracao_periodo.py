"""A migração 0007 troca o ponto pela barra só no formato AAAA.S."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PadronizacaoDoPeriodoTest(TransactionTestCase):
    antes = [("turmas", "0006_instituicao_turma_instituicao")]
    depois = [("turmas", "0007_periodo_com_barra")]

    def test_converte_ponto_em_barra_e_preserva_outros_valores(self):
        docente = get_user_model().objects.create_user("prof.migracao", perfil="DOCENTE")
        executor = MigrationExecutor(connection)
        executor.migrate(self.antes)
        Turma = executor.loader.project_state(self.antes).apps.get_model("turmas", "Turma")
        for valor in ["2026.2", "2025.1", "2026/1", "semestre", "2026.3"]:
            Turma.objects.create(nome=valor, periodo=valor, docente_id=docente.pk)

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.depois)
        Turma = executor.loader.project_state(self.depois).apps.get_model("turmas", "Turma")
        self.assertEqual(
            dict(Turma.objects.values_list("nome", "periodo")),
            {"2026.2": "2026/2", "2025.1": "2025/1", "2026/1": "2026/1", "semestre": "semestre",
             "2026.3": "2026.3"},
        )
