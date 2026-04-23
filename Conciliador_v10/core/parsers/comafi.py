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

        saldo_running = None

        for linea in lineas_totales:
            ls = linea.strip()
            if not ls:
                continue

            # Titular
            l_up = ls.upper()
            if ('SAIC' in l_up or 'SRL' in l_up or 'S.A' in l_up) and not titular:
                if 'CUIT' not in l_up and 'BANCO' not in l_up and 'COMAFI' not in l_up:
                    titular = re.sub(r'Hoja:\d+/\d+', '', ls).strip()

            # Saldos
            if 'SALDO ANTERIOR' in l_up:
                montos = patron_monto.findall(ls)
                if montos:
                    saldo_anterior = self.limpiar_monto(montos[-1])
                    if saldo_running is None:
                        saldo_running = saldo_anterior

            if 'SALDO AL:' in l_up:
                montos = patron_monto.findall(ls)
                if montos:
                    saldo_final = self.limpiar_monto(montos[-1])

            # Movimientos
            if 'TRANSPORTE' in l_up or 'HOJA:' in l_up:
                # Actualizar saldo running con el arrastre de página
                montos = patron_monto.findall(ls)
                if montos and saldo_running is None:
                    saldo_running = self.limpiar_monto(montos[-1])
                continue

            match = patron_fecha.match(ls)
            if not match:
                continue

            fecha_str = match.group(1)
            resto = match.group(2)

            try:
                fecha = datetime.strptime(fecha_str, '%d/%m/%y')
            except ValueError:
                continue

            montos = patron_monto.findall(resto)
            if not montos:
                continue

            # ── Formato Comafi ────────────────────────────────────────────────
            # Si hay 2 o más números → penúltimo=monto, último=saldo_nuevo
            # Si hay 1 número → es el monto solo (casos de formato simple)
            if len(montos) >= 2:
                monto = self.limpiar_monto(montos[-2])
                saldo_nuevo = self.limpiar_monto(montos[-1])
            else:
                monto = self.limpiar_monto(montos[0])
                saldo_nuevo = None

            if monto == 0:
                if saldo_nuevo is not None:
                    saldo_running = saldo_nuevo
                continue

            # ── Deducción matemática universal ───────────────────────────────
            debito = 0.0
            credito = 0.0

            if saldo_nuevo is not None and saldo_running is not None:
                if saldo_nuevo > saldo_running:
                    credito = monto
                else:
                    debito = monto
                saldo_running = saldo_nuevo
            elif saldo_nuevo is not None:
                saldo_running = saldo_nuevo
                # Sin saldo anterior conocido → fallback por keywords
                lu_resto = resto.upper()
                if 'DEV.' in lu_resto or 'CRED' in lu_resto or 'RESCATE' in lu_resto:
                    credito = monto
                else:
                    debito = monto
            else:
                # Solo 1 monto sin saldo → fallback por tipo de concepto
                texto_limpio = patron_monto.sub('', resto).strip()
                concepto_temp = re.search(r'^([A-Za-zÁÉÍÓÚáéíóú\s/\d]+)', texto_limpio)
                concepto_str = concepto_temp.group(1).strip() if concepto_temp else texto_limpio
                tipo_temp = self.clasificar_concepto(concepto_str)
                if tipo_temp in ('TRANSFERENCIA', 'DEV_IIBB', 'DEV_IMP_DEBITOS', 'FCI_RESCATE'):
                    credito = monto
                else:
                    debito = monto

            # Limpiar texto para el concepto
            texto_sin_montos = resto
            for m in montos:
                texto_sin_montos = texto_sin_montos.replace(m, '', 1)

            concepto_match = re.search(r'^\s*(.+?)\s*(\d{7})?\s*$', texto_sin_montos)
            concepto = concepto_match.group(1).strip() if concepto_match else texto_sin_montos.strip()
            concepto = re.sub(r'\s{2,}', ' ', concepto).strip()

            tipo = self.clasificar_concepto(concepto)

            # Tipos específicos de Comafi
            if 'DEV.IMP.IB' in concepto.upper():
                tipo = 'DEV_IIBB'
            elif 'DEV. IMP. A LOS DEBITOS' in concepto.upper():
                tipo = 'DEV_IMP_DEBITOS'

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
