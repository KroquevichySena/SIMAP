"""Leitura das coordenadas coladas do Google Maps (regra pura, sem banco)."""
from decimal import Decimal

from django.test import SimpleTestCase

from .coordenadas import CoordenadaInvalida, ler_coordenadas


class LerCoordenadasTest(SimpleTestCase):
    def test_graus_minutos_segundos_do_maps(self):
        self.assertEqual(
            ler_coordenadas("23°31'02.1\"S 46°10'58.5\"W"),
            (Decimal("-23.517250"), Decimal("-46.182917")),
        )

    def test_decimal_do_maps(self):
        self.assertEqual(
            ler_coordenadas("-23.517250, -46.182917"),
            (Decimal("-23.517250"), Decimal("-46.182917")),
        )

    def test_aceita_virgula_nos_segundos_e_letras_em_portugues(self):
        self.assertEqual(
            ler_coordenadas("23°31'02,1\"S 46°10'58,5\"O"),
            (Decimal("-23.517250"), Decimal("-46.182917")),
        )

    def test_norte_e_leste_ficam_positivos(self):
        latitude, longitude = ler_coordenadas("48°51'30\"N 2°17'40\"E")
        self.assertGreater(latitude, 0)
        self.assertGreater(longitude, 0)

    def test_ordem_trocada_e_recusada(self):
        with self.assertRaisesMessage(CoordenadaInvalida, "latitude (N ou S) vem primeiro"):
            ler_coordenadas("46°10'58.5\"W 23°31'02.1\"S")

    def test_so_uma_coordenada_e_recusada(self):
        with self.assertRaises(CoordenadaInvalida):
            ler_coordenadas("23°31'02.1\"S")

    def test_latitude_fora_do_limite_e_recusada(self):
        with self.assertRaisesMessage(CoordenadaInvalida, "latitude deve ficar entre -90 e 90"):
            ler_coordenadas("-123.5, -46.1")

    def test_longitude_fora_do_limite_e_recusada(self):
        with self.assertRaisesMessage(CoordenadaInvalida, "longitude deve ficar entre -180 e 180"):
            ler_coordenadas("-23.5, -246.1")

    def test_minutos_invalidos_sao_recusados(self):
        with self.assertRaisesMessage(CoordenadaInvalida, "Minutos e segundos"):
            ler_coordenadas("23°75'02.1\"S 46°10'58.5\"W")

    def test_texto_qualquer_e_recusado(self):
        with self.assertRaisesMessage(CoordenadaInvalida, "Formato não reconhecido"):
            ler_coordenadas("perto da UMC")
