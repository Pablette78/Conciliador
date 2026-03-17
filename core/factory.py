import os
from .parsers.santander import SantanderParser
from .parsers.galicia import GaliciaParser

class FabricaParsers:
    @staticmethod
    def obtener_parser(nombre_banco: str):
        if nombre_banco == "Banco Santander":
            return SantanderParser()
        elif nombre_banco == "Banco Galicia":
            return GaliciaParser()
        # Agregar mapeos para otros bancos
        return None

def detectar_y_preparar(ruta_archivo: str):
    # Por ahora mantenemos la lógica de detección actual pero retornamos el objeto Parser
    from detector_banco import detectar_banco
    banco = detectar_banco(ruta_archivo)
    if banco:
        return FabricaParsers.obtener_parser(banco)
    return None
