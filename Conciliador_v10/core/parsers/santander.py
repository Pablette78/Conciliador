import re
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto

class SantanderParser(BaseParser):
    PAT_FECHA = re.compile(r'^(\d{2}/\d{2}/\d{2})$')
    PAT_FECHA_DATO = re.compile(r'^(\d{2}/\d{2}/\d{2})\s+(.+)')
    PAT_MONTO = re.compile(r'-?\$\s*[\d.]+,\d{2}')
    PAT_NUMERO = re.compile(r'[\d.]+,\d{2}')
    PAT_PAG = re.compile(r'^\d+ - \d+$')

    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber
        
        movimientos = []
        saldo_anterior = 0.0
        saldo_final = 0.0
        titular = ""

        with pdfplumber.open(ruta_archivo) as pdf:
            lineas_totales = []
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    lineas_totales.extend(texto.split('\n'))

        # Detección de titular (mismo criterio que antes)
        for linea in lineas_totales[:20]:
            l = linea.upper().strip()
            if ('SRL' in l or 'SAIC' in l or 'S.A' in l) and 'BANCO' not in l and 'CUIT' not in l:
                titular = linea.strip()
                break

        fecha_pendiente = None
        mov_actual = None
        en_movimientos = False
        fin_movimientos = False
        saldo_actual = 0.0

        for linea in lineas_totales:
            linea = linea.strip()
            if not linea: continue

            if 'Saldo en cuenta' in linea:
                en_movimientos = True
                continue

            if fin_movimientos: continue
            if 'Detalle impositivo' in linea or 'Cambio de comisiones' in linea:
                if mov_actual:
                    movimientos.append(mov_actual)
                    mov_actual = None
                fin_movimientos = True
                continue

            if not en_movimientos: continue

            # Salto de líneas irrelevantes
            if 'Cuenta Corriente' in linea and ('CBU' in linea or 'Nº' in linea): continue
            if linea.startswith('Fecha') and 'Comprobante' in linea: continue
            if self.PAT_PAG.match(linea): continue

            # Saldo Inicial
            if 'Saldo Inicial' in linea:
                montos = self.PAT_NUMERO.findall(linea)
                if montos:
                    saldo_anterior = self.limpiar_monto(montos[-1])
                    saldo_actual = saldo_anterior
                continue

            # Saldo final
            if 'Saldo total' in linea:
                montos = self.PAT_NUMERO.findall(linea)
                if montos:
                    saldo_final = self.limpiar_monto(montos[-1])
                continue

            # Procesamiento de fechas y movimientos
            m_fs = self.PAT_FECHA.match(linea)
            if m_fs:
                try:
                    fecha_pendiente = datetime.strptime(m_fs.group(1), '%d/%m/%y')
                except ValueError: pass
                continue

            m_fd = self.PAT_FECHA_DATO.match(linea)
            if m_fd:
                try:
                    fecha = datetime.strptime(m_fd.group(1), '%d/%m/%y')
                except ValueError: continue
                
                resto = m_fd.group(2)
                montos = self.PAT_MONTO.findall(resto)
                if montos:
                    if mov_actual: movimientos.append(mov_actual)
                    mov_actual, saldo_actual = self._crear_movimiento(fecha, resto, montos, saldo_actual)
                    fecha_pendiente = None
                else:
                    fecha_pendiente = fecha
                continue
            montos = self.PAT_MONTO.findall(linea)
            if montos and len(montos) >= 2:
                if mov_actual: movimientos.append(mov_actual)
                fecha = fecha_pendiente if fecha_pendiente else (mov_actual.fecha if mov_actual else datetime.now())
                mov_actual, saldo_actual = self._crear_movimiento(fecha, linea, montos, saldo_actual)
                fecha_pendiente = None
                continue

            # Descripción extendida
            if mov_actual:
                clean = re.sub(r'-?\$\s*[\d.]+,\d{2}', '', linea).strip()
                if clean and len(clean) > 3:
                    mov_actual.descripcion += " " + clean

        if mov_actual: movimientos.append(mov_actual)

        return DatosExtracto(
            banco="Banco Santander",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )

    def _crear_movimiento(self, fecha, texto, montos_raw, saldo_actual) -> tuple[Movimiento, float]:
        concepto = texto
        for m in montos_raw:
            concepto = concepto.replace(m, '')
        concepto = re.sub(r'^\d+\s+', '', concepto.strip())
        concepto = re.sub(r'\s{2,}', ' ', concepto).strip()

        monto_val = self.limpiar_monto(montos_raw[0])
        tipo = self.clasificar_concepto(concepto)
        
        # Determinar si es crédito usando el saldo si está disponible
        nuevo_saldo = saldo_actual
        if len(montos_raw) >= 2:
            nuevo_saldo = self.limpiar_monto(montos_raw[-1])
            es_credito = nuevo_saldo > saldo_actual
        else:
            # Fallback a deducción por tipo o por signo negativo en PDF
            es_credito = tipo in ('TRANSFERENCIA', 'CRED_TARJETA', 'FCI_RESCATE', 'DEPOSITO_CHEQUE', 'DEV_IMP_DEBITOS')
            if '-' in montos_raw[0]:
                es_credito = False
        
        mov = Movimiento(
            fecha=fecha,
            concepto=concepto,
            credito=monto_val if es_credito else 0.0,
            debito=0.0 if es_credito else monto_val,
            tipo=tipo
        )
        return mov, nuevo_saldo
