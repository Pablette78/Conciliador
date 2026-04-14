"""
Parser genérico para extractos bancarios con formato tabular estándar.

Cubre bancos que siguen el patrón: SALDO ANTERIOR → movimientos (fecha, concepto,
débito, crédito, saldo) → SALDO FINAL. Variaciones menores se manejan con
parámetros de configuración y hooks de post-procesamiento.

Bancos soportados directamente:
  Bancor, Credicoop, Supervielle, Patagonia, BBVA, Nación, HSBC
"""
import re
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto


class GenericBankParser(BaseParser):
    """Parser configurable para extractos bancarios tabulares."""

    # --- Configuración por defecto (se overridea en subclases o __init__) ---
    NOMBRE_BANCO = "Banco Genérico"

    RE_SALDO_ANT = re.compile(
        r'(?:OPENING\s+BALANCE|SALDO\s+ANTERIOR)(?:\s+AL\s+\d{2}/\d{2}/\d{2,4})?[:\s]+([\d.,]+)', re.I
    )
    RE_SALDO_FIN = re.compile(
        r'(?:CLOSING\s+BALANCE|SALDO\s+(?:FINAL|AL\s+\d{2}/\d{2}(?:/\d{2,4})?))[:\s]+([\d.,]+)', re.I
    )
    RE_TITULAR = re.compile(
        r'(?:TITULAR|ACCOUNT\s+NAME|RAZ[OÓ]N\s+SOCIAL)[:\s]+(.+)', re.I
    )
    # Movimiento con 2 fechas (ej: BBVA: fecha operación + fecha valor)
    RE_MOV_2FECHAS = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+([\d.,]+|-)\s+([\d.,]+|-)?\s*([\d.,]+)?\s*$'
    )
    # Movimiento con 1 fecha
    RE_MOV_1FECHA = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+([\d.,]+|-)\s+([\d.,]+|-)?\s*([\d.,]+)?\s*$'
    )
    RE_TOTAL = re.compile(r'^TOTAL\s+', re.I)

    X_TOLERANCE = 3
    Y_TOLERANCE = 3

    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber

        movimientos = []
        saldo_anterior = 0.0
        saldo_final = 0.0
        titular = ""

        with pdfplumber.open(ruta_archivo) as pdf:
            lineas_totales = []
            for pagina in pdf.pages:
                texto = pagina.extract_text(
                    x_tolerance=self.X_TOLERANCE,
                    y_tolerance=self.Y_TOLERANCE
                )
                if texto:
                    lineas_totales.extend(texto.split('\n'))

        en_movimientos = False
        for linea in lineas_totales:
            ls = linea.strip()
            if not ls or self.RE_TOTAL.match(ls):
                continue

            # --- Metadatos ---
            m_tit = self.RE_TITULAR.search(ls)
            if m_tit and not titular:
                titular = m_tit.group(1).strip()
                continue

            m_ant = self.RE_SALDO_ANT.search(ls)
            if m_ant:
                saldo_anterior = self.limpiar_monto(m_ant.group(1))
                en_movimientos = True
                continue

            m_fin = self.RE_SALDO_FIN.search(ls)
            if m_fin:
                saldo_final = self.limpiar_monto(m_fin.group(1))
                continue

            if not en_movimientos:
                continue

            # --- Movimientos ---
            fecha_str, concepto, col_deb, col_cred = None, None, None, None

            m2 = self.RE_MOV_2FECHAS.match(ls)
            if m2:
                fecha_str = m2.group(1)
                concepto = m2.group(3)
                col_deb = m2.group(4)
                col_cred = m2.group(5)
            else:
                m1 = self.RE_MOV_1FECHA.match(ls)
                if m1:
                    fecha_str = m1.group(1)
                    concepto = m1.group(2)
                    col_deb = m1.group(3)
                    col_cred = m1.group(4)

            if fecha_str is None:
                continue

            fecha = self._parsear_fecha(fecha_str)
            if fecha is None:
                continue

            debito = self._limpiar_columna(col_deb)
            credito = self._limpiar_columna(col_cred)

            if debito == 0 and credito == 0:
                continue

            tipo = self.clasificar_concepto(concepto)
            tipo = self._post_clasificar(concepto, tipo, debito, credito)

            movimientos.append(Movimiento(
                fecha=fecha,
                concepto=concepto.strip(),
                debito=debito,
                credito=credito,
                tipo=tipo,
                descripcion=concepto.strip()
            ))

        return DatosExtracto(
            banco=self.NOMBRE_BANCO,
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )

    # --- Helpers ---

    def _parsear_fecha(self, fecha_str: str):
        try:
            fmt = '%d/%m/%Y' if len(fecha_str.split('/')[-1]) == 4 else '%d/%m/%y'
            return datetime.strptime(fecha_str, fmt)
        except ValueError:
            return None

    def _limpiar_columna(self, valor) -> float:
        if not valor or valor == '-':
            return 0.0
        return self.limpiar_monto(valor)

    def _post_clasificar(self, concepto: str, tipo: str, debito: float, credito: float) -> str:
        """Hook para reclasificación específica del banco. Override en subclases."""
        return tipo


# ---------------------------------------------------------------------------
# Subclases concretas — solo definen lo que difiere del genérico
# ---------------------------------------------------------------------------

class BancorParser(GenericBankParser):
    NOMBRE_BANCO = "Banco Bancor"

    def _post_clasificar(self, concepto, tipo, debito, credito):
        if tipo in ('OTRO', 'LEY25413'):
            c = concepto.lower()
            if '25413' in c or 'imp.db' in c:
                return 'LEY25413_DEBITO' if debito > 0 else 'LEY25413_CREDITO'
        return tipo


class CredicoopParser(GenericBankParser):
    NOMBRE_BANCO = "Banco Credicoop"


class SupervielleParser(GenericBankParser):
    NOMBRE_BANCO = "Banco Supervielle"


class PatagoniaParser(GenericBankParser):
    NOMBRE_BANCO = "Banco Patagonia"


class BBVAParser(GenericBankParser):
    NOMBRE_BANCO = "Banco BBVA"

    def _post_clasificar(self, concepto, tipo, debito, credito):
        if tipo == 'OTRO':
            c = concepto.lower()
            if 'imp.db.cr.ley25413' in c or 'imp db cred ley 25413' in c:
                return 'LEY25413_DEBITO' if debito > 0 else 'LEY25413_CREDITO'
            if 'ret sircreb' in c:
                return 'RET_SIRCREB'
        return tipo


class NacionParser(GenericBankParser):
    NOMBRE_BANCO = "Banco Nación"


class HSBCParser(GenericBankParser):
    NOMBRE_BANCO = "Banco HSBC"
