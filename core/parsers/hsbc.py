import re
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto

class HSBCParser(BaseParser):
    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber
        
        movimientos = []
        saldo_anterior = 0.0
        saldo_final = 0.0
        titular = ""

        # Regex para HSBC
        RE_SALDO_ANT = re.compile(
            r'(?:OPENING\s+BALANCE|SALDO\s+ANTERIOR)(?:\s+AL\s+\d{2}/\d{2}/\d{2,4})?[:\s]+([\d.,]+)', re.I
        )
        RE_SALDO_FIN = re.compile(
            r'(?:CLOSING\s+BALANCE|SALDO\s+FINAL|SALDO\s+AL\s+\d{2}/\d{2})[:\s]+([\d.,]+)', re.I
        )
        RE_TITULAR = re.compile(
            r'(?:TITULAR|ACCOUNT\s+NAME|RAZ[OÓ]N\s+SOCIAL)[:\s]+(.+)', re.I
        )
        RE_MOV = re.compile(
            r'^(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+([\d.,]+)?\s+([\d.,]+)?\s+([\d.,]+)?\s*$'
        )

        with pdfplumber.open(ruta_archivo) as pdf:
            lineas_totales = []
            for pagina in pdf.pages:
                texto = pagina.extract_text(x_tolerance=3, y_tolerance=3)
                if texto:
                    lineas_totales.extend(texto.split('\n'))

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
                saldo_anterior = self._limpiar_monto_hsbc(m_ant.group(1))
                en_movimientos = True
                continue
            
            m_fin = RE_SALDO_FIN.search(ls)
            if m_fin:
                saldo_final = self._limpiar_monto_hsbc(m_fin.group(1))
                continue

            if not en_movimientos: continue

            m = RE_MOV.match(ls)
            if m:
                fecha_str, concepto, c1, c2, _c3 = m.groups()
                
                try:
                    fmt = '%d/%m/%Y' if len(fecha_str.split('/')[-1]) == 4 else '%d/%m/%y'
                    fecha = datetime.strptime(fecha_str, fmt)
                except ValueError:
                    continue

                debito = self._limpiar_monto_hsbc(c1)
                credito = self._limpiar_monto_hsbc(c2)
                
                if debito == 0 and credito == 0: continue

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
            banco="Banco HSBC",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )

    def _limpiar_monto_hsbc(self, texto: str) -> float:
        """Limpieza especial para HSBC que puede usar formato inglés (1,234.56)"""
        if not texto or not texto.strip(): return 0.0
        t = texto.strip().replace(' ', '').replace('$', '')
        negativo = t.startswith('-')
        t = t.lstrip('-')
        
        # Heurística para detectar formato inglés vs español
        if ',' in t and '.' in t:
            if t.rindex(',') > t.rindex('.'):
                # Español: 1.234,56
                t = t.replace('.', '').replace(',', '.')
            else:
                # Inglés: 1,234.56
                t = t.replace(',', '')
        elif ',' in t:
            # Solo coma: asumimos decimal
            t = t.replace('.', '').replace(',', '.')
            
        try:
            val = float(t)
            return abs(val) # El sistema espera montos absolutos en debito/credito
        except ValueError:
            return 0.0
