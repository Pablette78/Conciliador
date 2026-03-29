import re
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto

class MacroParser(BaseParser):
    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber
        
        movimientos = []
        saldo_anterior = 0.0
        saldo_final = 0.0
        titular = ""

        # Regex para Macro
        RE_SALDO_ANT = re.compile(r'SALDO\s+ANTERIOR(?:\s+AL\s+\d{2}/\d{2}/\d{2,4})?[:\s]+([\d.,]+)', re.I)
        RE_SALDO_FIN = re.compile(r'SALDO\s+(?:FINAL|AL\s+\d{2}/\d{2}(?:/\d{2,4})?)[:\s]+([\d.,]+)', re.I)
        RE_TITULAR = re.compile(r'(?:TITULAR|RAZ[OÓ]N\s+SOCIAL)[:\s]+(.+)', re.I)

        # Formato Macro clásico
        RE_MOV_MACRO = re.compile(r'^(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+([\d.,]+)?\s+([\d.,]+)?\s+([\d.,]+)?\s*$')
        
        # Formato ex-Itaú
        RE_MOV_ITAU = re.compile(r'^(\d{2}/\d{2}/\d{2,4})\s+(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+(-?[\d.,]+)\s+(-?[\d.,]+)\s*$')

        with pdfplumber.open(ruta_archivo) as pdf:
            lineas_totales = []
            for pagina in pdf.pages:
                texto = pagina.extract_text(x_tolerance=3, y_tolerance=3)
                if texto:
                    lineas_totales.extend(texto.split('\n'))

        # Detección de formato
        formato = 'macro'
        for linea in lineas_totales[:30]:
            if 'ITAU' in linea.upper():
                formato = 'itau'
                break

        en_movimientos = False
        for linea in lineas_totales:
            ls = linea.strip()
            if not ls: continue

            m_tit = RE_TITULAR.search(ls)
            if m_tit and not titular:
                titular = m_tit.group(1).strip()
                continue
            
            m_ant = RE_SALDO_ANT.search(ls)
            if m_ant:
                saldo_anterior = self.limpiar_monto(m_ant.group(1))
                en_movimientos = True
                continue
            
            m_fin = RE_SALDO_FIN.search(ls)
            if m_fin:
                saldo_final = self.limpiar_monto(m_fin.group(1))
                continue

            if not en_movimientos: continue

            if formato == 'itau':
                m = RE_MOV_ITAU.match(ls)
                if m:
                    fecha_str, _, concepto, importe_str, _ = m.groups()
                    monto = self.limpiar_monto(importe_str)
                    es_negativo = '-' in importe_str
                    debito = monto if es_negativo else 0.0
                    credito = monto if not es_negativo else 0.0
                    self._procesar_y_agregar(movimientos, fecha_str, concepto, debito, credito)
                    continue

            m = RE_MOV_MACRO.match(ls)
            if m:
                fecha_str, concepto, col_deb, col_cred, _ = m.groups()
                debito = self.limpiar_monto(col_deb)
                credito = self.limpiar_monto(col_cred)
                self._procesar_y_agregar(movimientos, fecha_str, concepto, debito, credito)

        return DatosExtracto(
            banco="Banco Macro",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )

    def _procesar_y_agregar(self, movimientos, fecha_str, concepto, debito, credito):
        if debito == 0 and credito == 0: return
        
        try:
            fmt = '%d/%m/%Y' if len(fecha_str.split('/')[-1]) == 4 else '%d/%m/%y'
            fecha = datetime.strptime(fecha_str, fmt)
        except ValueError:
            return

        tipo = self.clasificar_concepto(concepto)
        movimientos.append(Movimiento(
            fecha=fecha,
            concepto=concepto.strip(),
            debito=debito,
            credito=credito,
            tipo=tipo,
            descripcion=concepto.strip()
        ))
