"""Regras da presença por QR Code, sem banco: recusa quando há certeza, análise quando há suspeita."""
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from django.utils import timezone

from . import servicos
from .models import Registro_de_Presenca

CAMPUS = SimpleNamespace(
    tem_localizacao=True, latitude=-23.517250, longitude=-46.182917, raio_metros=150, precisao_minima=100
)
NO_CAMPUS = {"latitude": -23.517300, "longitude": -46.182900, "precisao": 20}
LONGE = {"latitude": -23.530000, "longitude": -46.182917, "precisao": 20}


class DistanciaTest(SimpleTestCase):
    def test_mesmo_ponto_tem_distancia_zero(self):
        self.assertEqual(servicos.distancia_metros(-23.5, -46.1, -23.5, -46.1), 0)

    def test_um_centesimo_de_grau_de_latitude_da_cerca_de_1_1_km(self):
        self.assertAlmostEqual(servicos.distancia_metros(-23.51, -46.18, -23.52, -46.18), 1112, delta=2)


class MotivoDaLocalizacaoTest(SimpleTestCase):
    def test_instituicao_sem_coordenadas_nao_confere(self):
        self.assertEqual(servicos._motivo_da_localizacao(None, None), ("", None))
        sem_local = SimpleNamespace(tem_localizacao=False)
        self.assertEqual(servicos._motivo_da_localizacao(sem_local, None), ("", None))

    def test_aluno_que_negou_a_localizacao_vai_para_analise(self):
        self.assertEqual(servicos._motivo_da_localizacao(CAMPUS, None), ("Localização não autorizada", None))

    def test_gps_impreciso_vai_para_analise(self):
        motivo, _ = servicos._motivo_da_localizacao(CAMPUS, {**NO_CAMPUS, "precisao": 350.4})

        self.assertEqual(motivo, "Localização imprecisa (erro de 350 m)")

    def test_aluno_dentro_do_raio_passa(self):
        motivo, distancia = servicos._motivo_da_localizacao(CAMPUS, NO_CAMPUS)

        self.assertEqual(motivo, "")
        self.assertLess(distancia, CAMPUS.raio_metros)

    def test_aluno_fora_do_raio_vai_para_analise(self):
        motivo, distancia = servicos._motivo_da_localizacao(CAMPUS, LONGE)

        self.assertGreater(distancia, CAMPUS.raio_metros)
        self.assertEqual(motivo, f"Fora do raio ({distancia} m da instituição)")


@mock.patch.object(servicos.transaction, "atomic", mock.MagicMock())
@mock.patch.object(servicos.Registro_de_Presenca.objects, "create", side_effect=lambda **campos: campos)
@mock.patch.object(servicos.Matricula.objects, "filter")
@mock.patch.object(servicos.Chamada.objects, "select_for_update")
class RegistrarPresencaTest(SimpleTestCase):
    """Os mocks entram de baixo para cima: chamadas, matrículas e a criação da presença."""

    def _chamada(self, select_for_update, matriculas, *, finalizada=False, matriculado=True, ja_registrou=False,
                 validas=0, limite=40, mesmo_celular=None, instituicao=None):
        chamada = mock.MagicMock(finalizada_em=timezone.now() if finalizada else None, limite_uso=limite)
        chamada.turma.instituicao = instituicao
        chamada.presencas.filter.return_value.exists.return_value = ja_registrou
        presencas_validas = chamada.presencas.exclude.return_value
        presencas_validas.count.return_value = validas
        presencas_validas.filter.return_value.select_related.return_value.first.return_value = mesmo_celular
        select_for_update.return_value.select_related.return_value.get.return_value = chamada
        matriculas.return_value.exists.return_value = matriculado
        return chamada

    def _registrar(self, lido_ha=timedelta(seconds=10), **extra):
        return servicos.registrar_presenca(1, "aluno", timezone.now() - lido_ha, "QR", **extra)

    def test_presenca_sem_suspeita_e_confirmada(self, select_for_update, matriculas, _create):
        self._chamada(select_for_update, matriculas)

        presenca = self._registrar()

        self.assertEqual(presenca["situacao"], Registro_de_Presenca.CONFIRMADA)
        self.assertEqual(presenca["motivo"], "")

    def test_leitura_com_mais_de_tres_minutos_e_recusada_sem_consultar_a_chamada(
        self, select_for_update, matriculas, _create
    ):
        with self.assertRaisesMessage(servicos.PresencaRecusada, "O tempo para confirmar acabou"):
            self._registrar(lido_ha=timedelta(minutes=3, seconds=1))
        select_for_update.assert_not_called()

    def test_recusas(self, select_for_update, matriculas, create):
        casos = {
            "já foi finalizada": {"finalizada": True},
            "não tem matrícula ativa": {"matriculado": False},
            "já registrou presença": {"ja_registrou": True},
            "limite de presenças": {"validas": 40, "limite": 40},
        }
        for mensagem, situacao in casos.items():
            with self.subTest(mensagem=mensagem):
                self._chamada(select_for_update, matriculas, **situacao)
                with self.assertRaisesMessage(servicos.PresencaRecusada, mensagem):
                    self._registrar()
        create.assert_not_called()

    def test_mesmo_celular_de_outro_aluno_vai_para_analise(self, select_for_update, matriculas, _create):
        colega = SimpleNamespace(discente=SimpleNamespace(get_full_name=lambda: "Bia Lima", username="bia"))
        self._chamada(select_for_update, matriculas, mesmo_celular=colega)

        presenca = self._registrar(dispositivo="celular-1")

        self.assertEqual(presenca["situacao"], Registro_de_Presenca.EM_ANALISE)
        self.assertEqual(presenca["motivo"], "Mesmo celular de Bia Lima")

    def test_dois_motivos_ficam_juntos_para_o_professor(self, select_for_update, matriculas, _create):
        colega = SimpleNamespace(discente=SimpleNamespace(get_full_name=lambda: "", username="bia"))
        self._chamada(select_for_update, matriculas, mesmo_celular=colega, instituicao=CAMPUS)

        presenca = self._registrar(dispositivo="celular-1", localizacao=LONGE)

        self.assertEqual(presenca["situacao"], Registro_de_Presenca.EM_ANALISE)
        self.assertTrue(presenca["motivo"].startswith("Mesmo celular de bia; Fora do raio"))
        self.assertGreater(presenca["distancia_m"], CAMPUS.raio_metros)

    def test_dentro_do_raio_e_confirmada_com_a_distancia(self, select_for_update, matriculas, _create):
        self._chamada(select_for_update, matriculas, instituicao=CAMPUS)

        presenca = self._registrar(localizacao=NO_CAMPUS)

        self.assertEqual(presenca["situacao"], Registro_de_Presenca.CONFIRMADA)
        self.assertIsNotNone(presenca["distancia_m"])
