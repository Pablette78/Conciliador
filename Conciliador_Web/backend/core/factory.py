import unicodedata

from .parsers.santander import SantanderParser
from .parsers.galicia import GaliciaParser
from .parsers.generic import (
    BBVAParser, BancorParser, NacionParser, CredicoopParser,
    HSBCParser, PatagoniaParser, SupervielleParser,
)
from .parsers.macro import MacroParser
from .parsers.provincia import ProvinciaParser
from .parsers.icbc import ICBCParser
from .parsers.ciudad import CiudadParser
from .parsers.comafi import ComafiParser
from .parsers.arca import ARCAParser
from .parsers.amex import AmexParser
from .parsers.visa import VisaParser
from .parsers.excel_bank import GenericExcelBankParser


def _normalizar(texto: str) -> str:
    """Pasa a mayúsculas y elimina tildes para comparación robusta."""
    nfkd = unicodedata.normalize('NFKD', texto)
    sin_tildes = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tildes.upper()


# Mapeo normalizado (sin tildes, MAYÚSCULAS) → clase parser
_PARSER_MAP = {
    "SANTANDER": SantanderParser,
    "GALICIA": GaliciaParser,
    "BBVA": BBVAParser,
    "FRANCES": BBVAParser,
    "BANCOR": BancorParser,
    "CORDOBA": BancorParser,
    "PROVINCIA": ProvinciaParser,
    "BAPRO": ProvinciaParser,
    "NACION": NacionParser,       # matchea "Nación", "NACION", "Nacion"
    "CREDICOOP": CredicoopParser,
    "HSBC": HSBCParser,
    "ICBC": ICBCParser,
    "MACRO": MacroParser,
    "PATAGONIA": PatagoniaParser,
    "SUPERVIELLE": SupervielleParser,
    "CIUDAD": CiudadParser,
    "COMAFI": ComafiParser,
    "ARCA": ARCAParser,
    "AFIP": ARCAParser,
    "AMEX": AmexParser,
    "AMERICAN EXPRESS": AmexParser,
    "VISA": VisaParser,
    # Extracto Excel genérico (cualquier banco no reconocido específicamente)
    "BANCO (EXCEL)": GenericExcelBankParser,
}


class FabricaParsers:
    @staticmethod
    def obtener_parser(nombre_banco: str):
        if not nombre_banco:
            return None

        b = _normalizar(nombre_banco.strip())

        for clave, parser_cls in _PARSER_MAP.items():
            if clave in b:
                return parser_cls()

        return None


def detectar_y_preparar(ruta_archivo: str):
    from detector_banco import detectar_banco
    banco = detectar_banco(ruta_archivo)
    if banco:
        return FabricaParsers.obtener_parser(banco)
    return None
