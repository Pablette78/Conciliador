from abc import ABC, abstractmethod
from typing import Dict, List
from ..models import Movimiento, DatosExtracto

class BaseParser(ABC):
    @abstractmethod
    def parse(self, ruta_archivo: str) -> DatosExtracto:
        """Debe ser implementado por cada banco"""
        pass

    def clasificar_concepto(self, concepto: str) -> str:
        """Lógica común de categorización basada en conceptos"""
        c = concepto.lower()
        if 'sircreb' in c: return 'RET_SIRCREB'
        if 'iibb tuc' in c or 'adelanto iibb' in c: return 'RET_IIBB_TUCUMAN'
        if 'ingresos brutos' in c or 'ing. brutos' in c: return 'PERC_IIBB'
        if 'percepcion ingresos brutos caba' in c: return 'PERC_IIBB_CABA'
        
        if 'ley 25413' in c or 'ley 25.413' in c:
            if 'cred' in c or 'cre.' in c: return 'LEY25413_CREDITO'
            if 'deb' in c or 'deb.' in c: return 'LEY25413_DEBITO'
            return 'LEY25413'
            
        if 'iva' in c and ('percepcion' in c or '21%' in c): return 'IVA'
        if 'comision' in c or 'com transf' in c or 'com.' in c: return 'COMISION'
        if 'pago de haberes' in c or 'honorarios' in c: return 'HABERES'
        if 'debito automatico' in c: return 'DEB_AUTOMATICO'
        if 'pago servicios' in c or 'afip' in c: return 'PAGO_SERVICIOS'
        if 'interes' in c: return 'INTERESES'
        if 'imp' in c and 'sello' in c: return 'IMP_SELLOS'
        if 'tarjeta' in c: return 'PAGO_TARJETA'
        return 'OTRO'

    def limpiar_monto(self, texto: str) -> float:
        """Utilidad para limpiar strings de montos"""
        if not texto: return 0.0
        # Eliminar $, espacios, y ajustar separadores decimales/miles
        # Asumiendo formato local común: miles con . y decimales con ,
        s = texto.replace('$', '').replace(' ', '')
        if ',' in s and '.' in s: # Formato 1.234,56
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s: # Formato 1234,56
            s = s.replace(',', '.')
        
        try:
            return abs(float(s))
        except ValueError:
            return 0.0
