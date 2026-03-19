import re
from datetime import datetime
from collections import defaultdict
from .base import BaseParser
from ..models import Movimiento, DatosExtracto

class ICBCParser(BaseParser):
    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber
        
        movimientos = []
        saldo_anterior = 0.0
        saldo_final = 0.0
        titular = ""
        anio = datetime.now().year

        PATRON_NUMERO = re.compile(r'^[\d.]+,\d{2}-?$')
        PATRON_FECHA_MOV = re.compile(r'^\d{2}-\d{2}$')
        PATRON_PERIODO = re.compile(r'PERIODO\s+\d{2}-\d{2}-(\d{4})')
        PATRON_SALDO_ANT = re.compile(r'SALDO ULTIMO EXTRACTO AL.*?([\d.]+,\d{2})', re.IGNORECASE)
        PATRON_SALDO_FINAL = re.compile(r'SALDO FINAL AL.*?([\d.]+,\d{2})', re.IGNORECASE)
        PATRON_TITULAR = re.compile(r'A NOMBRE DE:\s*(.+)', re.IGNORECASE)

        with pdfplumber.open(ruta_archivo) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text() or ''
                words = pagina.extract_words()

                m_per = PATRON_PERIODO.search(texto)
                if m_per: anio = int(m_per.group(1))

                if not titular:
                    m_tit = PATRON_TITULAR.search(texto)
                    if m_tit: titular = m_tit.group(1).strip()

                if saldo_anterior == 0.0:
                    m_ant = PATRON_SALDO_ANT.search(texto)
                    if m_ant: saldo_anterior = self.limpiar_monto(m_ant.group(1))

                m_fin = PATRON_SALDO_FINAL.search(texto)
                if m_fin: saldo_final = self.limpiar_monto(m_fin.group(1))

                # Detección de layout
                x_fecha = x_debitos = x_creditos = x_saldos = None
                for w in words:
                    t = w['text'].upper()
                    if t == 'FECHA' and x_fecha is None: x_fecha = w['x0']
                    if t == 'DEBITOS' and x_debitos is None: x_debitos = w['x0']
                    if t == 'CREDITOS' and x_creditos is None: x_creditos = w['x0']
                    if t == 'SALDOS' and x_saldos is None: x_saldos = w['x0']

                if x_fecha is None: x_fecha = 20.0
                if x_debitos is None: x_debitos = 310.0
                if x_creditos is None: x_creditos = 381.0
                if x_saldos is None: x_saldos = 473.0

                x_max_debito = (x_debitos + x_creditos) / 2
                x_max_credito = (x_creditos + x_saldos) / 2
                x_fecha_max = x_fecha + 40

                lineas_grouped = defaultdict(list)
                for w in words:
                    lineas_grouped[round(w['top'])].append(w)

                for top in sorted(lineas_grouped.keys()):
                    ws = sorted(lineas_grouped[top], key=lambda w: w['x0'])
                    if not ws: continue

                    primera = ws[0]
                    if not (PATRON_FECHA_MOV.match(primera['text']) and primera['x0'] <= x_fecha_max):
                        continue

                    fecha_str = primera['text']
                    try:
                        dia, mes = int(fecha_str[:2]), int(fecha_str[3:])
                        fecha = datetime(anio, mes, dia)
                    except ValueError:
                        continue

                    debito = credito = 0.0
                    nums = [(w['x0'], w['text']) for w in ws if PATRON_NUMERO.match(w['text'])]

                    for x0, num_texto in nums:
                        valor = self.limpiar_monto(num_texto)
                        if x0 <= x_max_debito:
                            debito = valor
                        elif x0 <= x_max_credito:
                            credito = valor

                    if debito == 0.0 and credito == 0.0: continue

                    palabras_concepto = []
                    for w in ws[1:]:
                        if PATRON_NUMERO.match(w['text']): break
                        palabras_concepto.append(w['text'])
                    concepto = ' '.join(palabras_concepto).strip()

                    if not concepto or any(x in concepto.upper() for x in ('SALDO', 'TOTAL', 'CONTINUA')):
                        continue

                    tipo = self.clasificar_concepto(concepto)

                    movimientos.append(Movimiento(
                        fecha=fecha,
                        concepto=concepto,
                        debito=debito,
                        credito=credito,
                        tipo=tipo,
                        descripcion=concepto
                    ))

        return DatosExtracto(
            banco="Banco ICBC",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )
