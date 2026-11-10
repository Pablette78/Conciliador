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

        # ── Pasada 1: Extraer tablas anexas de Pagos de Servicios y Transferencias ──
        # Esto permite enriquecer las transferencias y débitos con el nombre del cliente/proveedor
        detalles_por_ref = {}
        detalles_por_clave = {}

        seccion_actual = None
        for linea in lineas_totales:
            l_strip = linea.strip()
            l_up = l_strip.upper()
            if 'PAGO DE SERVICIOS' in l_up:
                seccion_actual = 'SERVICIOS'
                continue
            elif 'TRANSFERENCIAS ELECTRONICAS' in l_up or 'TRANSFERENCIAS ELECTRONICAS .' in l_up:
                seccion_actual = 'TRANSFERENCIAS'
                continue
            elif 'ENVIADAS' in l_up and seccion_actual in ('TRANSFERENCIAS', None):
                seccion_actual = 'TRANSF_ENVIADAS'
                continue
            elif 'RECIBIDAS' in l_up and seccion_actual in ('TRANSFERENCIAS', 'TRANSF_ENVIADAS', None):
                seccion_actual = 'TRANSF_RECIBIDAS'
                continue
            elif 'CHEQUES' in l_up or 'VISA DEBITO' in l_up or 'IMPUESTOS DEBITADOS' in l_up:
                seccion_actual = None
                continue

            if seccion_actual == 'SERVICIOS':
                # Ej: YPF Pago Directo 0189004636 FACTURA 1095117758 1120-01026-5 07/10/26 $ 1007.470,07
                # GOOGLEADWORDS Pago Electrónico 12589255295786 000056273 1120-01026-5 08/10/26 $ 500.000,00
                m_imp = patron_monto.findall(l_strip)
                m_fecha = re.search(r'(\d{2}/\d{2}/\d{2})', l_strip)
                if m_imp and m_fecha:
                    monto_val = self.limpiar_monto(m_imp[-1])
                    f_val = m_fecha.group(1)
                    empresa_match = re.match(r'^([A-Z0-9.\-_]+(?:\s+[A-Z0-9.\-_]+)?)\s+(Pago Directo|Pago Electr[oó]nico)', l_strip, re.I)
                    nombre_empresa = empresa_match.group(1).strip() if empresa_match else ""
                    # Buscar referencia numérica
                    ref_m = re.search(r'(\d{7,10})', l_strip)
                    if ref_m and nombre_empresa:
                        ref_clean = ref_m.group(1).lstrip('0')
                        detalles_por_ref[ref_clean] = nombre_empresa
                    if nombre_empresa:
                        detalles_por_clave[(f_val, monto_val)] = nombre_empresa

            elif seccion_actual == 'TRANSF_ENVIADAS':
                # Ej: 06/10/2026 Hon000001999597 1120-01026-5 20265225390 PONTI PABLO $ 1.500.000,00
                # Ej: 13/10/2026 000000000003 1120-01026-5 30580111315 DHL $ 228.431,70
                m_imp = patron_monto.findall(l_strip)
                m_fecha = re.search(r'(\d{2}/\d{2}/\d{4})', l_strip)
                if m_imp and m_fecha:
                    monto_val = self.limpiar_monto(m_imp[-1])
                    f_2dig = m_fecha.group(1)[:6] + m_fecha.group(1)[8:]  # DD/MM/YY
                    # Extraer referencia si existe tipo 1999597
                    ref_m = re.search(r'(?:Var|Fac|Hon)?0*(\d{7})', l_strip, re.I)
                    # Extraer nombre destinatario
                    dest_m = re.search(r'\d{11}\s+([^$]+?)\s+\$', l_strip)
                    nombre_dest = dest_m.group(1).strip() if dest_m else ""
                    if ref_m and nombre_dest:
                        detalles_por_ref[ref_m.group(1)] = nombre_dest
                    if nombre_dest:
                        detalles_por_clave[(f_2dig, monto_val)] = nombre_dest

            elif seccion_actual == 'TRANSF_RECIBIDAS':
                # Ej: 02/10/2026 Sureda/yanina VAR BBVA 27320926020 1120-01026-5 $ 543.830,00
                # Ej: 05/10/2026 Villa Victoria Sa PRO3349476 GALICIA 30710806035 1120-01026-5 $ 17.307.822,70
                m_imp = patron_monto.findall(l_strip)
                m_fecha = re.search(r'(\d{2}/\d{2}/\d{4})', l_strip)
                if m_imp and m_fecha:
                    monto_val = self.limpiar_monto(m_imp[-1])
                    f_2dig = m_fecha.group(1)[:6] + m_fecha.group(1)[8:]
                    rem_m = re.match(r'^\d{2}/\d{2}/\d{4}\s+([A-Za-z0-9/\.\s\-]+?)\s+(VAR|PRO\d+|\d{7})', l_strip)
                    nombre_rem = rem_m.group(1).strip() if rem_m else ""
                    if nombre_rem:
                        detalles_por_clave[(f_2dig, monto_val)] = nombre_rem

        # ── Pasada 2: Extraer movimientos bancarios ───────────────────────────
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
                montos = patron_monto.findall(ls)
                if montos and saldo_running is None:
                    saldo_running = self.limpiar_monto(montos[-1])
                continue

            # Si llegamos a las secciones anexas de cheques o impuestos debitados, no procesar como movimientos
            if 'IMPUESTOS DEBITADOS EN EL PERIODO' in l_up or 'DETALLE DE CHEQUES' in l_up:
                break

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

            # ── Deducción matemática ─────────────────────────────────────────
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
                lu_resto = resto.upper()
                if 'DEV.' in lu_resto or 'CRED' in lu_resto or 'RESCATE' in lu_resto or 'DEPOSITO' in lu_resto:
                    credito = monto
                else:
                    debito = monto
            else:
                texto_limpio = patron_monto.sub('', resto).strip()
                concepto_temp = re.search(r'^([A-Za-zÁÉÍÓÚáéíóú\s/\d]+)', texto_limpio)
                concepto_str = concepto_temp.group(1).strip() if concepto_temp else texto_limpio
                tipo_temp = self.clasificar_concepto(concepto_str)
                if tipo_temp in ('TRANSFERENCIA', 'DEV_IIBB', 'DEV_IMP_DEBITOS', 'INVERSIONES', 'DEPOSITOS'):
                    credito = monto
                else:
                    debito = monto

            # Limpiar texto para el concepto y extraer posible referencia
            texto_sin_montos = resto
            for m in montos:
                texto_sin_montos = texto_sin_montos.replace(m, '', 1)

            concepto_match = re.search(r'^\s*(.+?)\s*(\d{7})?\s*$', texto_sin_montos)
            concepto = concepto_match.group(1).strip() if concepto_match else texto_sin_montos.strip()
            referencia_extraida = concepto_match.group(2).strip() if (concepto_match and concepto_match.group(2)) else ""
            concepto = re.sub(r'\s{2,}', ' ', concepto).strip()

            tipo = self.clasificar_concepto(concepto)

            # Tipos específicos adicionales de Comafi
            if 'DEV.IMP.IB' in concepto.upper():
                tipo = 'DEV_IIBB'
            elif 'DEV. IMP. A LOS DEBITOS' in concepto.upper():
                tipo = 'DEV_IMP_DEBITOS'

            # Buscar detalle de beneficiario/remitente por referencia o por clave (fecha, monto)
            descripcion_detalle = ""
            if referencia_extraida and referencia_extraida in detalles_por_ref:
                descripcion_detalle = detalles_por_ref[referencia_extraida]
            elif (fecha_str, monto) in detalles_por_clave:
                descripcion_detalle = detalles_por_clave[(fecha_str, monto)]

            if debito > 0 or credito > 0:
                movimientos.append(Movimiento(
                    fecha=fecha,
                    concepto=concepto.strip(),
                    debito=debito,
                    credito=credito,
                    tipo=tipo,
                    referencia=referencia_extraida,
                    descripcion=descripcion_detalle
                ))

        return DatosExtracto(
            banco="Banco Comafi",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )
