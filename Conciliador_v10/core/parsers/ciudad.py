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

        with pdfplumber.open(ruta_archivo) as pdf:
            lineas_totales = []
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    lineas_totales.extend(texto.split('\n'))

        for linea in lineas_totales:
            ls = linea.strip()
            if not ls: continue

            # Buscar saldo anterior
            if 'SALDO ANTERIOR' in ls.upper():
                numeros = re.findall(r'[\d.]+,\d{2}', ls)
                if numeros:
                    saldo_anterior = self.limpiar_monto(numeros[-1])
            
            # Buscar titular
            if ('INSTRUMENTAL' in ls.upper() or 'SRL' in ls.upper() or 'S.A' in ls.upper()) and 'CUIT' not in ls.upper():
                if not titular: titular = ls.strip()

            # Buscar saldo final
            if 'SALDO AL' in ls.upper():
                numeros = re.findall(r'[\d.]+,\d{2}', ls)
                if numeros:
                    saldo_final = self.limpiar_monto(numeros[-1])

            # Movimientos
            match = patron_fecha.match(ls)
            if match:
                fecha_str = match.group(1)
                resto = match.group(2)
                
                fecha = self._parsear_fecha_ciudad(fecha_str)
                if not fecha or 'TRANSPORTE' in resto.upper():
                    continue

                numeros = re.findall(r'[\d.]+,\d{2}', resto)
                
                # Extraer concepto
                concepto_parts = re.match(r'^([A-Za-zÁÉÍÓÚáéíóú\s/\d]+)', resto)
                if concepto_parts:
                    concepto = concepto_parts.group(1).strip()
                    concepto = re.sub(r'\s+\d+$', '', concepto)
                else:
                    concepto = resto.split()[0] if resto.split() else "DESC"

                tipo = self.clasificar_concepto(concepto)
                debito = 0.0
                credito = 0.0
                descripcion = ""

                if tipo == 'TRANSFERENCIA':
                    desc_match = re.search(r'(\d{11}[\s-][A-Z/\s]+)$', resto)
                    if desc_match:
                        descripcion = desc_match.group(1).strip()

                    if len(numeros) >= 1:
                        # En el Ciudad original, el primero es monto
                        credito = self.limpiar_monto(numeros[0])
                else:
                    if numeros:
                        debito = self.limpiar_monto(numeros[0])

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
        if len(partes) != 3: return None
        try:
            dia = int(partes[0])
            mes = self.MESES.get(partes[1].upper(), 0)
            anio = int(partes[2])
            if mes == 0: return None
            return datetime(anio, mes, dia)
        except:
            return None
