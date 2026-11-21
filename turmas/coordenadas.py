"""
Lê as coordenadas do jeito que o Google Maps mostra, sempre latitude primeiro:

    23°31'02.1"S 46°10'58.5"W      (graus, minutos e segundos)
    -23.517250, -46.182917          (decimal, ao clicar com o botão direito no mapa)
"""
import re
from decimal import ROUND_HALF_UP, Decimal

CASAS = Decimal("0.000001")  # mesmas 6 casas dos campos do modelo

_GMS = re.compile(
    r"""(\d{1,3})\s*[°º]\s*(\d{1,2})\s*['′’]\s*(\d{1,2}(?:[.,]\d+)?)\s*(?:["″”]|'')?\s*([NSLOEW])""",
    re.IGNORECASE,
)
_DECIMAL = re.compile(r"^\s*([-+]?\d{1,3}(?:\.\d+)?)\s*[,;\s]\s*([-+]?\d{1,3}(?:\.\d+)?)\s*$")


class CoordenadaInvalida(ValueError):
    pass


def _de_gms(graus, minutos, segundos, direcao):
    valor = Decimal(graus) + Decimal(minutos) / 60 + Decimal(segundos.replace(",", ".")) / 3600
    if int(minutos) >= 60 or Decimal(segundos.replace(",", ".")) >= 60:
        raise CoordenadaInvalida("Minutos e segundos vão de 0 a 59.")
    return -valor if direcao.upper() in "SOW" else valor


def ler_coordenadas(texto):
    """Devolve (latitude, longitude) como Decimal, ou lança CoordenadaInvalida."""
    texto = (texto or "").strip()
    partes = _GMS.findall(texto)
    if partes:
        if len(partes) != 2:
            raise CoordenadaInvalida("Informe a latitude e a longitude, como aparecem no Google Maps.")
        (*lat, dir_lat), (*lon, dir_lon) = partes
        if dir_lat.upper() not in "NS" or dir_lon.upper() not in "LOEW":
            raise CoordenadaInvalida("A latitude (N ou S) vem primeiro e a longitude (L/E ou O/W) depois.")
        latitude, longitude = _de_gms(*lat, dir_lat), _de_gms(*lon, dir_lon)
    else:
        decimal = _DECIMAL.match(texto)
        if not decimal:
            raise CoordenadaInvalida(
                "Formato não reconhecido. Cole como no Google Maps, por exemplo "
                "23°31'02.1\"S 46°10'58.5\"W ou -23.517250, -46.182917."
            )
        latitude, longitude = Decimal(decimal.group(1)), Decimal(decimal.group(2))

    if not -90 <= latitude <= 90:
        raise CoordenadaInvalida("A latitude deve ficar entre -90 e 90. Confira se ela veio primeiro.")
    if not -180 <= longitude <= 180:
        raise CoordenadaInvalida("A longitude deve ficar entre -180 e 180.")
    return (
        latitude.quantize(CASAS, rounding=ROUND_HALF_UP),
        longitude.quantize(CASAS, rounding=ROUND_HALF_UP),
    )
