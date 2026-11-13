"""
Testes da chamada por QR code: ciclo do QR, recusas, sinais e telas.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from painel.servicos import historico_do_aluno
from turmas.models import Instituicao, Matricula, Turma
from usuarios.test_helpers import registrar_aceites_atuais

from .models import Chamada, Registro_de_Presenca
from .servicos import PresencaRecusada, distancia_metros, registrar_presenca

Usuario = get_user_model()
SENHA = "SenhaDeTeste123"
LAT, LNG = Decimal("-23.550500"), Decimal("-46.633300")
NA_SALA = {"latitude": -23.5505, "longitude": -46.6333, "precisao": 20}
LONGE = {"latitude": -23.5550, "longitude": -46.6333, "precisao": 20}


class BaseChamadaQR(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(username="prof.ana", password=SENHA, perfil="DOCENTE")
        cls.carla = Usuario.objects.create_user(
            username="aluno.carla", password=SENHA, perfil="DISCENTE", first_name="Carla", last_name="Mendes"
        )
        cls.diego = Usuario.objects.create_user(username="aluno.diego", password=SENHA, perfil="DISCENTE")
        cls.turma = Turma.objects.create(nome="Algoritmos I", periodo="2026.2", docente=cls.docente)
        Matricula.objects.create(turma=cls.turma, discente=cls.carla)
        Matricula.objects.create(turma=cls.turma, discente=cls.diego)
        registrar_aceites_atuais(Usuario.objects.all())

    def abrir(self, limite=30, segundos=30):
        chamada = Chamada(turma=self.turma, limite_uso=limite, ciclo_segundos=segundos)
        chamada.iniciar_ciclo()
        chamada.save()
        return chamada

    def registrar(self, chamada, aluno, **extras):
        extras.setdefault("lido_em", timezone.now())
        extras.setdefault("origem", "QR")
        return registrar_presenca(chamada.pk, aluno, **extras)


class RegistrarPresencaTest(BaseChamadaQR):

    def test_confirma_quando_todas_as_regras_passam(self):
        presenca = self.registrar(self.abrir(), self.carla, dispositivo="aparelho-1")

        self.assertEqual(presenca.situacao, Registro_de_Presenca.CONFIRMADA)
        self.assertEqual(presenca.motivo, "")

    def test_recusa_quando_passou_o_tempo_para_confirmar(self):
        with self.assertRaisesMessage(PresencaRecusada, "tempo para confirmar acabou"):
            self.registrar(self.abrir(), self.carla, lido_em=timezone.now() - timedelta(minutes=4))

    def test_aceita_quem_leu_a_tempo_mesmo_com_o_qr_ja_fechado(self):
        chamada = self.abrir()
        Chamada.objects.filter(pk=chamada.pk).update(data_expiracao=timezone.now() - timedelta(seconds=5))

        presenca = self.registrar(chamada, self.carla, lido_em=timezone.now() - timedelta(minutes=1))

        self.assertEqual(presenca.situacao, Registro_de_Presenca.CONFIRMADA)

    def test_recusa_quando_a_chamada_foi_finalizada(self):
        chamada = self.abrir()
        chamada.finalizar()

        with self.assertRaisesMessage(PresencaRecusada, "finalizada"):
            self.registrar(chamada, self.carla)

    def test_recusa_aluno_com_matricula_inativa(self):
        Matricula.objects.filter(discente=self.carla).update(status="INATIVA")

        with self.assertRaisesMessage(PresencaRecusada, "matrícula ativa"):
            self.registrar(self.abrir(), self.carla)

    def test_recusa_presenca_repetida(self):
        chamada = self.abrir()
        self.registrar(chamada, self.carla)

        with self.assertRaisesMessage(PresencaRecusada, "já registrou"):
            self.registrar(chamada, self.carla)

    def test_recusa_quando_o_limite_foi_atingido(self):
        chamada = self.abrir(limite=1)
        self.registrar(chamada, self.carla)

        with self.assertRaisesMessage(PresencaRecusada, "limite"):
            self.registrar(chamada, self.diego)

    def test_presenca_recusada_pelo_professor_nao_ocupa_o_limite(self):
        chamada = self.abrir(limite=1)
        Registro_de_Presenca.objects.create(
            chamada=chamada, discente=self.carla, situacao=Registro_de_Presenca.RECUSADA
        )

        presenca = self.registrar(chamada, self.diego)

        self.assertEqual(presenca.situacao, Registro_de_Presenca.CONFIRMADA)

    def test_sinaliza_quando_o_celular_ja_confirmou_outro_aluno(self):
        chamada = self.abrir()
        self.registrar(chamada, self.carla, dispositivo="aparelho-1")

        presenca = self.registrar(chamada, self.diego, dispositivo="aparelho-1")

        self.assertEqual(presenca.situacao, Registro_de_Presenca.EM_ANALISE)
        self.assertEqual(presenca.motivo, "Mesmo celular de Carla Mendes")


class LocalizacaoTest(BaseChamadaQR):

    def setUp(self):
        instituicao = Instituicao.objects.create(nome="Campus Central", latitude=LAT, longitude=LNG)
        Turma.objects.filter(pk=self.turma.pk).update(instituicao=instituicao)

    def test_confirma_dentro_do_raio_e_guarda_so_a_distancia(self):
        presenca = self.registrar(self.abrir(), self.carla, localizacao=NA_SALA)

        self.assertEqual(presenca.situacao, Registro_de_Presenca.CONFIRMADA)
        self.assertEqual(presenca.distancia_m, 0)

    def test_sinaliza_fora_do_raio(self):
        presenca = self.registrar(self.abrir(), self.carla, localizacao=LONGE)

        self.assertEqual(presenca.situacao, Registro_de_Presenca.EM_ANALISE)
        self.assertIn("Fora do raio (500 m", presenca.motivo)

    def test_sinaliza_localizacao_imprecisa(self):
        presenca = self.registrar(self.abrir(), self.carla, localizacao={**NA_SALA, "precisao": 300})

        self.assertEqual(presenca.situacao, Registro_de_Presenca.EM_ANALISE)
        self.assertIn("imprecisa", presenca.motivo)

    def test_sinaliza_quando_o_aluno_nega_a_localizacao(self):
        presenca = self.registrar(self.abrir(), self.carla, localizacao=None)

        self.assertEqual(presenca.motivo, "Localização não autorizada")

    def test_distancia_entre_pontos_conhecidos(self):
        self.assertEqual(distancia_metros(LAT, LNG, LAT, LNG), 0)
        self.assertEqual(distancia_metros(-23.5505, -46.6333, -23.5550, -46.6333), 500)


class FluxoDoProfessorTest(BaseChamadaQR):

    def setUp(self):
        self.client.login(username="prof.ana", password=SENHA)

    def test_abrir_sem_limite_usa_os_alunos_com_matricula_ativa(self):
        resposta = self.client.post(
            reverse("chamada:abrir_chamada"), {"turma": self.turma.pk, "ciclo_segundos": 30}
        )

        chamada = Chamada.objects.get()
        self.assertRedirects(resposta, reverse("chamada:ao_vivo", args=[chamada.pk]))
        self.assertEqual(chamada.limite_uso, 2)
        self.assertEqual(len(chamada.token_chamada), 6)
        self.assertTrue(chamada.qr_aberto)

    def test_renovar_gera_codigo_novo_so_depois_que_o_qr_fechou(self):
        chamada = self.abrir()
        token_antigo = chamada.token_chamada

        self.client.post(reverse("chamada:renovar", args=[chamada.pk]))
        chamada.refresh_from_db()
        self.assertEqual(chamada.token_chamada, token_antigo)

        Chamada.objects.filter(pk=chamada.pk).update(data_expiracao=timezone.now() - timedelta(seconds=1))
        self.client.post(reverse("chamada:renovar", args=[chamada.pk]))
        chamada.refresh_from_db()
        self.assertNotEqual(chamada.token_chamada, token_antigo)
        self.assertEqual(chamada.renovacoes, 1)
        self.assertTrue(chamada.qr_aberto)

    def test_finalizar_fecha_o_qr(self):
        chamada = self.abrir()

        self.client.post(reverse("chamada:finalizar", args=[chamada.pk]))

        chamada.refresh_from_db()
        self.assertIsNotNone(chamada.finalizada_em)
        self.assertFalse(chamada.qr_aberto)

    def test_estado_informa_codigo_tempo_e_contador(self):
        chamada = self.abrir()
        self.registrar(chamada, self.carla)

        dados = self.client.get(reverse("chamada:estado", args=[chamada.pk])).json()

        self.assertEqual(dados["token"], chamada.token_chamada)
        self.assertTrue(dados["link"].endswith(f"/chamada/p/{chamada.token_chamada}/"))
        self.assertEqual(dados["presentes"], 1)
        self.assertTrue(dados["aberto"])

    def test_outro_professor_nao_ve_a_chamada(self):
        bia = Usuario.objects.create_user(username="prof.bia", password=SENHA, perfil="DOCENTE")
        registrar_aceites_atuais([bia])
        chamada = self.abrir()
        self.client.login(username="prof.bia", password=SENHA)

        resposta = self.client.get(reverse("chamada:estado", args=[chamada.pk]))

        self.assertEqual(resposta.status_code, 404)

    def test_aceitar_presenca_em_analise(self):
        chamada = self.abrir()
        presenca = Registro_de_Presenca.objects.create(
            chamada=chamada, discente=self.carla, situacao=Registro_de_Presenca.EM_ANALISE
        )

        self.client.post(reverse("chamada:decidir_presenca", args=[presenca.pk]), {"acao": "aceitar"})

        presenca.refresh_from_db()
        self.assertEqual(presenca.situacao, Registro_de_Presenca.CONFIRMADA)

    def test_painel_so_conta_presenca_confirmada(self):
        chamada = self.abrir()
        Registro_de_Presenca.objects.create(
            chamada=chamada, discente=self.carla, situacao=Registro_de_Presenca.EM_ANALISE
        )
        chamada.finalizar()

        historico = historico_do_aluno(self.turma, self.carla)

        self.assertFalse(historico["chamadas"][0]["presente"])


class FluxoDoAlunoTest(BaseChamadaQR):

    def test_leitura_do_qr_sobrevive_ao_login(self):
        chamada = self.abrir()

        resposta = self.client.get(reverse("chamada:ler_qr", args=[chamada.token_chamada]))
        self.assertRedirects(resposta, reverse("chamada:confirmar_leitura"), fetch_redirect_response=False)

        self.client.login(username="aluno.carla", password=SENHA)
        resposta = self.client.post(reverse("chamada:confirmar_leitura"))

        self.assertContains(resposta, "Presença registrada")
        presenca = Registro_de_Presenca.objects.get(discente=self.carla)
        self.assertEqual(presenca.origem, "QR")
        self.assertTrue(presenca.dispositivo)
        self.assertIn("simap_aparelho", resposta.cookies)

    def test_qr_expirado_nao_guarda_a_leitura(self):
        chamada = self.abrir()
        Chamada.objects.filter(pk=chamada.pk).update(data_expiracao=timezone.now() - timedelta(seconds=1))

        resposta = self.client.get(reverse("chamada:ler_qr", args=[chamada.token_chamada]))

        self.assertContains(resposta, "QR code expirado")
        self.assertNotIn("leitura_chamada", self.client.session)

    def test_codigo_digitado_segue_para_a_confirmacao(self):
        chamada = self.abrir()
        self.client.login(username="aluno.carla", password=SENHA)

        resposta = self.client.post(
            reverse("chamada:confirmar_presenca"),
            {"turma": self.turma.pk, "token_chamada": chamada.token_chamada.lower()},
        )

        self.assertRedirects(resposta, reverse("chamada:confirmar_leitura"))
        self.assertEqual(self.client.session["leitura_chamada"]["origem"], "CODIGO")

    def test_confirmar_sem_leitura_volta_para_digitar_o_codigo(self):
        self.client.login(username="aluno.carla", password=SENHA)

        resposta = self.client.get(reverse("chamada:confirmar_leitura"))

        self.assertRedirects(resposta, reverse("chamada:confirmar_presenca"))

    def test_mostra_o_motivo_da_recusa_ao_aluno(self):
        chamada = self.abrir(limite=1)
        self.registrar(chamada, self.diego)
        self.client.login(username="aluno.carla", password=SENHA)
        self.client.get(reverse("chamada:ler_qr", args=[chamada.token_chamada]))

        resposta = self.client.post(reverse("chamada:confirmar_leitura"))

        self.assertContains(resposta, "limite de presenças desta chamada foi atingido")
        self.assertFalse(Registro_de_Presenca.objects.filter(discente=self.carla).exists())
