import os
from .parsers.santander import SantanderParser
from .parsers.galicia import GaliciaParser
from .parsers.bbva import BBVAParser
from .parsers.bancor import BancorParser
from .parsers.provincia import ProvinciaParser
from .parsers.nacion import NacionParser
from .parsers.credicoop import CredicoopParser
from .parsers.hsbc import HSBCParser
from .parsers.icbc import ICBCParser
from .parsers.macro import MacroParser
from .parsers.patagonia import PatagoniaParser
from .parsers.supervielle import SupervielleParser
from .parsers.ciudad import CiudadParser
from .parsers.comafi import ComafiParser
from .parsers.arca import ARCAParser

class FabricaParsers:
    @staticmethod
    def obtener_parser(nombre_banco: str):
        if nombre_banco == "Banco Santander":
            return SantanderParser()
        elif nombre_banco == "Banco Galicia":
            return GaliciaParser()
        elif nombre_banco == "Banco BBVA":
            return BBVAParser()
        elif nombre_banco == "Banco Bancor":
            return BancorParser()
        elif nombre_banco == "Banco Provincia":
            return ProvinciaParser()
        elif nombre_banco == "Banco Nación":
            return NacionParser()
        elif nombre_banco == "Banco Credicoop":
            return CredicoopParser()
        elif nombre_banco == "Banco HSBC":
            return HSBCParser()
        elif nombre_banco == "Banco ICBC":
            return ICBCParser()
        elif nombre_banco == "Banco Macro":
            return MacroParser()
        elif nombre_banco == "Banco Patagonia":
            return PatagoniaParser()
        elif nombre_banco == "Banco Supervielle":
            return SupervielleParser()
        elif nombre_banco == "Banco Ciudad":
            return CiudadParser()
        elif nombre_banco == "Banco Comafi":
            return ComafiParser()
        elif "ARCA" in nombre_banco or "AFIP" in nombre_banco:
            return ARCAParser()
        
        # Mapeos alternativos para robustez
        b = nombre_banco.upper()
        if "GALICIA" in b: return GaliciaParser()
        if "SANTANDER" in b: return SantanderParser()
        if "BBVA" in b or "FRANCES" in b: return BBVAParser()
        if "BANCOR" in b or "CORDOBA" in b: return BancorParser()
        if "PROVINCIA" in b or "BAPRO" in b: return ProvinciaParser()
        if "NACION" in b: return NacionParser()
        if "CREDICOOP" in b: return CredicoopParser()
        if "HSBC" in b: return HSBCParser()
        if "ICBC" in b: return ICBCParser()
        if "MACRO" in b: return MacroParser()
        if "PATAGONIA" in b: return PatagoniaParser()
        if "SUPERVIELLE" in b: return SupervielleParser()
        if "CIUDAD" in b: return CiudadParser()
        if "COMAFI" in b: return ComafiParser()
        if "ARCA" in b or "AFIP" in b: return ARCAParser()
        
        return None

def detectar_y_preparar(ruta_archivo: str):
    # Por ahora mantenemos la lógica de detección actual pero retornamos el objeto Parser
    from detector_banco import detectar_banco
    banco = detectar_banco(ruta_archivo)
    if banco:
        return FabricaParsers.obtener_parser(banco)
    return None
