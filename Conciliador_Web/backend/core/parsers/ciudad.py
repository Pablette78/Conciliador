import re
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto


class CiudadParser(BaseParser):
    MESES = {
        'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
    }

    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber

        movimientos = []
        saldo_anterior = 0.0
        saldo_final = 0.0
        titular = ""

        patron_fecha = re.compile(r'^(\d{2}-[A-Z]{3}-\d{4})\s+(.+)')
        patron_numeros = re.compile(r'[\d.]+,\d{2}')
        patron_desc = re.compile(r'(\d{11}[\s\-][A-Z0-9/\s\-]+)$')

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

            lu = ls.upper()

            # Titular: primera línea con la razón social de la empresa
            if ('SRL' in lu or 'S.A.' in lu or 'SAIC' in lu or 'INSTRUMENTAL' in lu):
                if 'CUIT' not in lu and 'BANCO' not in lu and 'FLORIDA' not in lu and not titular:
                    # Quitar el CUIT pegado al nombre y CBU/cuenta
                    cand = re.sub(r'\s+\d{2}-\d{8}-\d.*$', '', ls).strip()
                    cand = re.sub(r'\s+\d{6,}.*$', '', cand).strip()
                    if cand:
                        titular = cand

            # Saldo Anterior: en el encabezado de la primera hoja.
            # El banco imprime en formato espaciado: 'S A L D O A N T E R IO R' + monto
            # Usamos un regex flexible que tolera espacios entre letras.
            if re.search(r'S\s*A\s*L\s*D\s*O\s+A\s*N\s*T\s*E\s*R', lu) and saldo_running is None:
                numeros = patron_numeros.findall(ls)
                if numeros:
                    saldo_anterior = self.limpiar_monto(numeros[-1])
                    if saldo_running is None:
                        saldo_running = saldo_anterior

            # Saldo Final
            if 'SALDO AL' in lu:
                numeros = patron_numeros.findall(ls)
                if numeros:
                    saldo_final = self.limpiar_monto(numeros[-1])

            # Procesar líneas de movimientos (empiezan con fecha DD-MMM-YYYY)
            match = patron_fecha.match(ls)
            if not match:
                continue

            fecha_str = match.group(1)
            resto = match.group(2)

            # TRANSPORTE = arrastre de saldo entre páginas; actualizar saldo running y saltar
            if 'TRANSPORTE' in resto.upper():
                numeros = patron_numeros.findall(resto)
                if numeros and saldo_running is None:
                    saldo_running = self.limpiar_monto(numeros[-1])
                continue

            fecha = self._parsear_fecha_ciudad(fecha_str)
            if not fecha:
                continue

            numeros = patron_numeros.findall(resto)

            # El formato Ciudad es siempre: [monto]  [saldo_nuevo]  [descripcion_opcional]
            # Necesitamos al menos 2 números
            if len(numeros) < 2:
                continue

            # El penúltimo número es el monto del movimiento
            # El último número es el saldo resultante
            monto = self.limpiar_monto(numeros[-2])
            saldo_nuevo = self.limpiar_monto(numeros[-1])

            if monto == 0:
                saldo_running = saldo_nuevo
                continue

            # ── Deducción matemática universal ───────────────────────────────
            # Si el saldo sube respecto al anterior → fue un Crédito (entra plata)
            # Si el saldo baja respecto al anterior → fue un Débito  (sale plata)
            debito = 0.0
            credito = 0.0

            if saldo_running is not None:
                if saldo_nuevo > saldo_running:
                    credito = monto
                else:
                    debito = monto
            else:
                # Fallback solo para el primer movimiento si no tenemos saldo anterior
                lu_resto = resto.upper()
                if 'CRED' in lu_resto or 'TRANSFERENCIA' in lu_resto:
                    credito = monto
                else:
                    debito = monto

            saldo_running = saldo_nuevo

            # Extraer descripción: CUIT-Nombre al final de la línea (transferencias)
            desc_match = patron_desc.search(resto)
            descripcion = desc_match.group(1).strip() if desc_match else ""

            # Extraer concepto: texto sin números ni descripción del CUIT
            texto_limpio = patron_numeros.sub('', resto)
            if descripcion:
                texto_limpio = texto_limpio.replace(descripcion, '')
            concepto = re.sub(r'\s{2,}', ' ', texto_limpio).strip()
            # Quitar dígitos sueltos residuales al final
            concepto = re.sub(r'\s+\d+\s*$', '', concepto).strip()

            tipo = self.clasificar_concepto(concepto)

            if debito > 0 or credito > 0:
                movimientos.append(Movimiento(
                    fecha=fecha,
                    concepto=concepto,
                    debito=debito,
                    credito=credito,
                    descripcion=descripcion,
                    tipo=tipo
                ))

        return DatosExtracto(
            banco="Banco Ciudad",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )

    def _parsear_fecha_ciudad(self, texto):
        partes = texto.strip().split('-')
        if len(partes) != 3:
            return None
        try:
            dia = int(partes[0])
            mes = self.MESES.get(partes[1].upper(), 0)
            anio = int(partes[2])
            if mes == 0:
                return None
            return datetime(anio, mes, dia)
        except Exception:
            return None
