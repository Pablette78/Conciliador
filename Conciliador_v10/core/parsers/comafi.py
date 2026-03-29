import re
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto

class ComafiParser(BaseParser):
    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber
        
        movimientos = []
        saldo_anterior = 0.0
        saldo_final = 0.0
        titular = ""

        patron_fecha = re.compile(r'^(\d{2}/\d{2}/\d{2})\s+(.+)')
        patron_monto = re.compile(r'([\d.]+,\d{2})')

        with pdfplumber.open(ruta_archivo) as pdf:
            lineas_totales = []
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    lineas_totales.extend(texto.split('\n'))

        for linea in lineas_totales:
            ls = linea.strip()
            if not ls: continue

            # Titular
            l_up = ls.upper()
            if ('SAIC' in l_up or 'SRL' in l_up or 'S.A' in l_up) and not titular:
                if 'CUIT' not in l_up and 'BANCO' not in l_up and 'COMAFI' not in l_up:
                    titular = re.sub(r'Hoja:\d+/\d+', '', ls).strip()

            # Saldos
            if 'SALDO ANTERIOR' in l_up:
                montos = patron_monto.findall(ls)
                if montos: saldo_anterior = self.limpiar_monto(montos[-1])
            
            if 'SALDO AL:' in l_up:
                montos = patron_monto.findall(ls)
                if montos: saldo_final = self.limpiar_monto(montos[-1])

            # Movimientos
            if 'TRANSPORTE' in l_up or 'HOJA:' in l_up: continue

            match = patron_fecha.match(ls)
            if match:
                fecha_str = match.group(1)
                resto = match.group(2)
                
                try:
                    fecha = datetime.strptime(fecha_str, '%d/%m/%y')
                except ValueError:
                    continue

                montos = patron_monto.findall(resto)
                
                # Limpiar texto para concepto
                texto_sin_montos = resto
                for m in montos:
                    texto_sin_montos = texto_sin_montos.replace(m, '', 1)
                
                concepto_match = re.search(r'^\s*(.+?)\s*(\d{7})?\s*$', texto_sin_montos)
                concepto = concepto_match.group(1) if concepto_match else texto_sin_montos.strip()

                tipo = self.clasificar_concepto(concepto)
                
                # Refinar tipo para devoluciones
                if 'DEV.IMP.IB' in concepto.upper(): tipo = 'DEV_IIBB'
                elif 'DEV. IMP. A LOS DEBITOS' in concepto.upper(): tipo = 'DEV_IMP_DEBITOS'

                debito = 0.0
                credito = 0.0
                
                if montos:
                    monto_val = self.limpiar_monto(montos[0])
                    # Heurística de tipos crédito en Comafi
                    if tipo in ('TRANSFERENCIA', 'CRED_TARJETA', 'DEV_IIBB', 'DEV_IMP_DEBITOS', 'FCI_RESCATE'):
                        credito = monto_val
                    else:
                        debito = monto_val

                if debito > 0 or credito > 0:
                    movimientos.append(Movimiento(
                        fecha=fecha,
                        concepto=concepto.strip(),
                        debito=debito,
                        credito=credito,
                        tipo=tipo,
                        descripcion=""
                    ))

        return DatosExtracto(
            banco="Banco Comafi",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )
