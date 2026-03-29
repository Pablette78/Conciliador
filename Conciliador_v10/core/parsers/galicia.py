import re
from datetime import datetime
from typing import Tuple
from .base import BaseParser
from ..models import Movimiento, DatosExtracto

class GaliciaParser(BaseParser):
    PAT_FECHA = re.compile(r'^(\d{2}/\d{2}/\d{2})\s+(.+)')
    PAT_MONTO = re.compile(r'-?[\d.]+,\d{2}')
    
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

        # Detección de titular
        for linea in lineas_totales:
            l = linea.upper().strip()
            if ('SAIC' in l or 'SRL' in l or 'S.A' in l):
                if 'CUIT' not in l and 'BANCO' not in l and not titular:
                    titular = linea.strip()
                    break

        # Buscar saldos iniciales y finales
        for i, linea in enumerate(lineas_totales):
            l = linea.upper().strip()
            if 'SALDO INICIAL' in l or 'SALDO ANTERIOR' in l:
                numeros = self.PAT_MONTO.findall(linea)
                if numeros: saldo_anterior = self.limpiar_monto(numeros[-1])
            elif 'SALDO FINAL' in l:
                numeros = self.PAT_MONTO.findall(linea)
                if numeros: saldo_final = self.limpiar_monto(numeros[-1])

        # Fallback de saldo suelto
        if saldo_anterior == 0:
            buscando_saldos = False
            saldos_encon = []
            for linea in lineas_totales[:50]:
                if 'saldos' in linea.lower() and 'deudor' not in linea.lower():
                    buscando_saldos = True
                    continue
                if buscando_saldos:
                    m = re.match(r'^\$\s*([\d.]+,\d{2})$', linea.strip())
                    if m:
                        saldos_encon.append(self.limpiar_monto(m.group(1)))
                    elif saldos_encon:
                        break
            if len(saldos_encon) >= 2:
                saldo_anterior, saldo_final = saldos_encon[0], saldos_encon[1]
            elif len(saldos_encon) == 1:
                saldo_anterior = saldos_encon[0]

        saldo_actual = saldo_anterior
        mov_actual = None

        for linea in lineas_totales:
            linea = linea.strip()
            if not linea: continue

            # Ignorar encabezados
            if any(x in linea for x in ['Fecha Descripción', 'Resumen de Cuenta', 'Página', 'TOTAL RETENCION']):
                continue
            if linea.startswith('Total'):
                continue

            match = self.PAT_FECHA.match(linea)
            if match:
                if mov_actual:
                    movimientos.append(mov_actual)

                fecha_str = match.group(1)
                resto = match.group(2)
                
                try:
                    fecha = datetime.strptime(fecha_str, '%d/%m/%y')
                except ValueError:
                    continue

                montos_str = self.PAT_MONTO.findall(resto)
                
                # Concepto es el texto
                concepto = re.sub(r'-?[\d.]+,\d{2}', '', resto).strip()
                concepto = re.sub(r'\s+[A-Z0-9]{4}\s*$', '', concepto).strip()
                concepto = re.sub(r'\s+Q\s+\d+', '', concepto).strip()
                concepto = re.sub(r'\s{2,}', ' ', concepto).strip()

                mov_actual, saldo_actual = self._procesar_linea(fecha, concepto, montos_str, saldo_actual)
            
            elif mov_actual:
                # Líneas de continuación sin fecha
                if not re.match(r'^[\d\s]+$', linea) and linea not in ('VARIOS', 'ALQUILERES', 'CUOTA'):
                    mov_actual.descripcion += ' ' + linea
                    mov_actual.descripcion = mov_actual.descripcion.strip()
                    
                    # Reevaluar el tipo con la nueva descripción
                    texto_completo = f"{mov_actual.concepto} {mov_actual.descripcion}"
                    nuevo_tipo = self.clasificar_concepto(texto_completo)
                    if nuevo_tipo != 'OTRO' and mov_actual.tipo == 'OTRO':
                        mov_actual.tipo = nuevo_tipo

                # Revisar montos perdidos en líneas siguientes
                montos_cont = self.PAT_MONTO.findall(linea)
                if montos_cont and mov_actual.credito == 0 and mov_actual.debito == 0:
                    mov_actual, saldo_actual = self._procesar_linea(mov_actual.fecha, mov_actual.concepto, montos_cont, saldo_actual)

        if mov_actual:
            movimientos.append(mov_actual)

        # Limpiar movimientos estériles sin monto
        mov_finales = [m for m in movimientos if m.debito > 0 or m.credito > 0]

        # Corrección final de saldo
        if saldo_final == 0 and mov_finales:
            for linea in reversed(lineas_totales):
                montos = re.findall(r'\$\s*([\d.]+,\d{2})', linea)
                if montos:
                    val = self.limpiar_monto(montos[-1])
                    if val > 0:
                        saldo_final = val
                        break

        return DatosExtracto(
            banco="Banco Galicia",
            titular=titular,
            movimientos=mov_finales,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )

    def _procesar_linea(self, fecha, concepto: str, montos_str: list, saldo_actual: float) -> Tuple[Movimiento, float]:
        debito = 0.0
        credito = 0.0
        nuevo_saldo = saldo_actual

        if montos_str:
            if len(montos_str) >= 2:
                # El primero es monto, el último es saldo en Galicia
                monto_val = self.limpiar_monto(montos_str[0])
                nuevo_saldo = self.limpiar_monto(montos_str[-1])
                
                # Deducción matemática universal
                if nuevo_saldo > saldo_actual:
                    credito = monto_val
                else:
                    debito = monto_val

            elif len(montos_str) == 1:
                # Solo saldo por ahora (o monto sin saldo)
                monto_val = self.limpiar_monto(montos_str[0])
                if '-' in montos_str[0]:
                    debito = monto_val
                else:
                    credito = monto_val

        tipo = self.clasificar_concepto(concepto)

        mov = Movimiento(
            fecha=fecha,
            concepto=concepto,
            debito=debito,
            credito=credito,
            tipo=tipo
        )
        return mov, nuevo_saldo
