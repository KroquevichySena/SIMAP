"""Regressao da confirmacao de presenca com relacionamento opcional no PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from turmas.models import Instituicao, Matricula, Turma
from usuarios.models import AceiteTermos

from .models import Chamada, Registro_de_Presenca
from .servicos import PresencaRecusada, registrar_presenca


@skipUnlessDBFeature("has_select_for_update_of")
class BloqueioPresencaPostgreSQLTest(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Regressao especifica de PostgreSQL.")
        usuarios = get_user_model()
        self.docente = usuarios.objects.create_user(username="docente.ficticio", perfil="DOCENTE")
        self.aluno = usuarios.objects.create_user(username="aluno.ficticio", perfil="DISCENTE")
        self.outro = usuarios.objects.create_user(username="outro.ficticio", perfil="DISCENTE")
        self.turma = Turma.objects.create(nome="Turma ficticia", periodo="2026/2", docente=self.docente)
        for aluno in (self.aluno, self.outro):
            Matricula.objects.create(turma=self.turma, discente=aluno)
            AceiteTermos.objects.create(usuario=aluno, versao=settings.TERMOS_DE_USO_VERSAO)
        self.chamada = Chamada.objects.create(
            turma=self.turma, token_chamada=Chamada.gerar_token(),
            limite_uso=2, data_expiracao=timezone.now() + timedelta(minutes=3),
        )

    def instituicao(self, com_coordenadas=True):
        valores = {"latitude": 0, "longitude": 0} if com_coordenadas else {}
        instituicao = Instituicao.objects.create(nome="Campus ficticio", **valores)
        self.turma.instituicao = instituicao
        self.turma.save(update_fields=["instituicao"])

    def confirmar(self, aluno=None, **extras):
        return registrar_presenca(
            self.chamada.pk, aluno or self.aluno,
            lido_em=extras.pop("lido_em", timezone.now()), origem="CODIGO", **extras,
        )

    def test_sem_instituicao_nao_gera_erro_de_bloqueio(self):
        presenca = self.confirmar()
        self.assertEqual(presenca.situacao, Registro_de_Presenca.CONFIRMADA)

    def test_localizacao_permitida_confirma(self):
        self.instituicao()
        presenca = self.confirmar(localizacao={"latitude": 0, "longitude": 0, "precisao": 10})
        self.assertEqual(presenca.situacao, Registro_de_Presenca.CONFIRMADA)
        self.assertEqual(presenca.distancia_m, 0)

    def test_sem_localizacao_com_instituicao_fica_em_analise(self):
        self.instituicao()
        presenca = self.confirmar()
        self.assertEqual(presenca.situacao, Registro_de_Presenca.EM_ANALISE)

    def test_instituicao_sem_coordenadas_nao_gera_erro(self):
        self.instituicao(com_coordenadas=False)
        self.assertEqual(self.confirmar().situacao, Registro_de_Presenca.CONFIRMADA)

    def test_post_da_tela_com_campos_vazios_nao_retorna_500(self):
        self.instituicao()
        self.client.force_login(self.aluno)
        sessao = self.client.session
        sessao["leitura_chamada"] = {
            "chamada": self.chamada.pk, "lido_em": timezone.now().isoformat(), "origem": "CODIGO",
        }
        sessao.save()
        resposta = self.client.post(
            reverse("chamada:confirmar_leitura"),
            {"latitude": "", "longitude": "", "precisao": ""},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            Registro_de_Presenca.objects.get(chamada=self.chamada, discente=self.aluno).situacao,
            Registro_de_Presenca.EM_ANALISE,
        )

    def test_duplicidade_continua_recusada(self):
        self.confirmar()
        with self.assertRaises(PresencaRecusada):
            self.confirmar()
        self.assertEqual(self.chamada.presencas.count(), 1)

    def test_matricula_inativa_continua_recusada(self):
        Matricula.objects.filter(turma=self.turma, discente=self.aluno).update(status="INATIVA")
        with self.assertRaises(PresencaRecusada):
            self.confirmar()
        self.assertEqual(self.chamada.presencas.count(), 0)

    def test_chamada_finalizada_continua_recusada(self):
        self.chamada.finalizada_em = timezone.now()
        self.chamada.save(update_fields=["finalizada_em"])
        with self.assertRaises(PresencaRecusada):
            self.confirmar()

    def test_prazo_da_leitura_continua_validado(self):
        with self.assertRaises(PresencaRecusada):
            self.confirmar(lido_em=timezone.now() - timedelta(minutes=4))

    def test_limite_continua_validado(self):
        self.chamada.limite_uso = 1
        self.chamada.save(update_fields=["limite_uso"])
        self.confirmar()
        with self.assertRaises(PresencaRecusada):
            self.confirmar(self.outro)

    def test_concorrencia_preserva_a_ultima_vaga(self):
        self.chamada.limite_uso = 1
        self.chamada.save(update_fields=["limite_uso"])
        barreira = Barrier(2)

        def tentar(aluno):
            close_old_connections()
            try:
                barreira.wait(timeout=10)
                self.confirmar(aluno)
                return "registrada"
            except PresencaRecusada:
                return "recusada"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(tentar, (self.aluno, self.outro)))
        self.assertCountEqual(resultados, ["registrada", "recusada"])
        self.assertEqual(self.chamada.presencas.count(), 1)
