import re
from datetime import datetime
from .generic import GenericBankParser
from ..models import Movimiento, DatosExtracto


class MacroParser(GenericBankParser):
    """Macro con soporte para formato ex-Itaú (2 fechas + importe con signo)."""
    NOMBRE_BANCO = "Banco Macro"

    RE_SALDO_ANT = re.compile(
        r'SALDO\s+ANTERIOR(?:\s+AL\s+\d{2}/\d{2}/\d{2,4})?[:\s]+([\d.,]+)', re.I
    )
    RE_MOV_ITAU = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+(-?[\d.,]+)\s+(-?[\d.,]+)\s*$'
    )

    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber

        # Detectar formato Itaú
        with pdfplumber.open(ruta_archivo) as pdf:
            lineas_totales = []
            for pagina in pdf.pages:
                texto = pagina.extract_text(x_tolerance=3, y_tolerance=3)
                if texto:
                    lineas_totales.extend(texto.split('\n'))

        es_itau = any('ITAU' in l.upper() for l in lineas_totales[:30])

        if not es_itau:
            # Formato Macro estándar: usar parser genérico
            return super().parse(ruta_archivo)

        # Formato ex-Itaú
        movimientos = []
        saldo_anterior = 0.0
        saldo_final = 0.0
        titular = ""
        en_movimientos = False

        for linea in lineas_totales:
            ls = linea.strip()
            if not ls:
                continue

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

            m = self.RE_MOV_ITAU.match(ls)
            if m:
                fecha_str, _, concepto, importe_str, _ = m.groups()
                fecha = self._parsear_fecha(fecha_str)
                if not fecha:
                    continue

                monto = self.limpiar_monto(importe_str)
                es_negativo = '-' in importe_str

                debito = monto if es_negativo else 0.0
                credito = monto if not es_negativo else 0.0

                if debito == 0 and credito == 0:
                    continue

                tipo = self.clasificar_concepto(concepto)
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
