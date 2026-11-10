import unicodedata
from abc import ABC, abstractmethod
from typing import Dict, List
from ..models import Movimiento, DatosExtracto


def normalizar_texto(s: str) -> str:
    """Quita tildes, diacríticos y convierte a minúsculas para comparaciones uniformes."""
    if not s:
        return ""
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


class BaseParser(ABC):
    @abstractmethod
    def parse(self, ruta_archivo: str) -> DatosExtracto:
        """Debe ser implementado por cada banco"""
        pass

    def clasificar_concepto(self, concepto: str) -> str:
        """
        Lógica común de categorización basada en conceptos normalizados.
        Discrimina impuestos, percepciones, retenciones, comisiones y tipos operativos.
        """
        c = normalizar_texto(concepto)

        # ── 1. Retenciones y Percepciones de Ingresos Brutos ──────────────────
        if 'sircreb' in c:
            return 'RET_SIRCREB'
        if 'iibb tuc' in c or 'adelanto iibb' in c or ('ret' in c and 'tucuman' in c):
            return 'RET_IIBB_TUCUMAN'
        if ('percepcion' in c or 'perc' in c) and ('caba' in c or 'ib caba' in c or 'iibb caba' in c):
            return 'PERC_IIBB_CABA'
        if ('retencion' in c or 'ret' in c) and ('iibb' in c or 'ib' in c or 'ingresos brutos' in c or 'ing. brutos' in c):
            return 'RET_IIBB'
        if ('percepcion' in c or 'perc' in c) and ('iibb' in c or 'ib' in c or 'ingresos brutos' in c or 'ing. brutos' in c):
            return 'PERC_IIBB'
        if 'ingresos brutos' in c or 'ing. brutos' in c or 'iibb' in c:
            return 'RET_IIBB'

        # ── 2. Impuesto Ley 25.413 (Débitos y Créditos bancarios) y tasas ─────
        es_imp_deb_cred = (
            'ley 25413' in c or 'ley 25.413' in c or
            'impuesto a los debitos' in c or 'impuesto a los creditos' in c or
            'impuesto al debito' in c or 'impuesto al credito' in c or
            'imp a los debitos' in c or 'imp a los creditos' in c or
            'imp. a los debitos' in c or 'imp. a los creditos' in c or
            'imp. debitos' in c or 'imp. creditos' in c or
            'imp. debito' in c or 'imp. credito' in c or
            'imp.deb' in c or 'imp.cred' in c or
            'imp debito' in c or 'imp credito' in c or
            'imp deb y cred' in c or 'imp. deb/cred' in c or
            'debitos - tasa' in c or 'creditos-tasa' in c or 'creditos - tasa' in c or
            'tasa general debito' in c or 'tasa general credito' in c
        )
        if es_imp_deb_cred:
            if 'cred' in c:
                return 'LEY25413_CREDITO'
            if 'deb' in c:
                return 'LEY25413_DEBITO'
            return 'LEY25413'

        # ── 3. IVA (Percepciones vs Retenciones vs IVA General) ────────────────
        if ('percepcion' in c or 'perc' in c) and 'iva' in c:
            return 'PERC_IVA'
        if 'rg 2408' in c or 'rg2408' in c or 'rg 5329' in c or 'rg5329' in c:
            return 'PERC_IVA'
        if ('retencion' in c or 'ret' in c) and 'iva' in c:
            return 'RET_IVA'
        if 'iva' in c:
            return 'IVA'

        # ── 4. Comisiones y Mantenimiento Bancario ────────────────────────────
        if any(term in c for term in [
            'comision', 'com transf', 'com.', 'comision por', 'mantenimiento de',
            'mantenimiento cuenta', 'emision resumen', 'resumen de cu', 'cargo por',
            'costo de servicio', 'paquete de cuenta', 'gastos administracion',
            'renovacion', 'comision emision', 'comision transferencias'
        ]):
            return 'COMISION'

        # ── 5. Impuesto de Sellos ─────────────────────────────────────────────
        if ('imp' in c or 'impuesto' in c) and 'sello' in c:
            return 'IMP_SELLOS'

        # ── 6. Intereses Bancarios ────────────────────────────────────────────
        if 'interes' in c or 'int. compensatorio' in c or 'int. punitorio' in c:
            return 'INTERESES'

        # ── 7. Operativos: Haberes y Sueldos ──────────────────────────────────
        if any(term in c for term in ['sueldo', 'haberes', 'honorario', 'pago de haberes']):
            return 'SUELDOS'

        # ── 8. Operativos: Pago de Servicios e Impuestos AFIP / ARCA ───────────
        if any(term in c for term in [
            'pago de servicio', 'pago servicio', 'pago electronico de servicio',
            'pago directo', 'pago dir', 'afip', 'arca', 'vep', 'pago mis cuentas'
        ]):
            return 'PAGO_SERVICIOS'

        # ── 9. Operativos: Tarjetas y Débito Automático ────────────────────────
        if 'debito automatico' in c:
            return 'DEB_AUTOMATICO'
        if 'tarjeta' in c:
            return 'PAGO_TARJETA'

        # ── 10. Operativos: Fondos Comunes de Inversión / Inversiones ─────────
        if any(term in c for term in [
            'fci', 'fondo comun', 'suscripcion fci', 'rescate fci',
            'modificacion cp fci', 'plazo fijo'
        ]):
            return 'INVERSIONES'

        # ── 11. Operativos: Depósitos ─────────────────────────────────────────
        if any(term in c for term in ['deposito', 'dep.']):
            if 'cheque' in c:
                return 'DEPOSITO_CHEQUE'
            if 'efectivo' in c:
                return 'DEPOSITO_EFECTIVO'
            return 'DEPOSITOS'

        # ── 12. Operativos: Cheques pagados / emitidos ────────────────────────
        if any(term in c for term in ['pago de cheque', 'cheque', 'chq']):
            return 'CHEQUES'

        # ── 13. Operativos: Transferencias ────────────────────────────────────
        if any(term in c for term in ['transferencia', 'transf', 'transf.']):
            return 'TRANSFERENCIAS'

        return 'OTRO'

    def limpiar_monto(self, texto: str) -> float:
        """Limpia strings de montos. Soporta formato español (1.234,56)
        e inglés (1,234.56), con o sin signo negativo."""
        if not texto or not texto.strip(): return 0.0
        s = texto.strip().replace('$', '').replace(' ', '')
        s = s.strip('-')  # abs() al final se encarga del signo

        if ',' in s and '.' in s:
            if s.rindex(',') > s.rindex('.'):
                # Español: 1.234,56
                s = s.replace('.', '').replace(',', '.')
            else:
                # Inglés: 1,234.56
                s = s.replace(',', '')
        elif ',' in s:
            # Solo coma → decimal (1234,56)
            s = s.replace(',', '.')

        try:
            return abs(float(s))
        except ValueError:
            return 0.0
