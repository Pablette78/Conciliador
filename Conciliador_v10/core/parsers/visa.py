import re
from datetime import datetime
from typing import Optional
import pdfplumber

from core.models import DatosExtracto, Movimiento
from core.parsers.base import BaseParser


class VisaParser(BaseParser):
    """
    Parser robusto para resúmenes de tarjetas VISA emitidos por Prisma/Payway.
    Aplica para bancos como Santander Río, Banco Galicia, etc.
    """
    
    # Patrón para identificar montos con formato monetario (ej: 1.234,56 o 1.234,56-)
    PAT_MONTO = re.compile(r'^-?[\d\.]+,\d{2}-?$')

    def parse(self, pdf_path: str) -> DatosExtracto:
        titular = ""
        saldo_anterior = 0.0
        saldo_final = 0.0
        movimientos = []
        
        texto_paginas = ""
        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text(layout=True)
                if texto:
                    texto_paginas += texto + "\n"
        
        # Iterar sobre cada línea de texto
        for linea in texto_paginas.split('\n'):
            linea_str = linea.strip()
            if not linea_str:
                continue
                
            # Extraer Titular de Cuenta
            if "TITULAR DE CUENTA" in linea_str:
                titular = linea_str.replace("TITULAR DE CUENTA", "").strip()
            elif "Cuenta:" in linea_str and "AT:" in linea_str:
                # Caso Santander "Cuenta:   AT: CAMPANIA01" 
                # Suele estar en la cuadricula. Busquemos un nombre abajo o dejemos vacío
                pass
            
            # Buscar saldo anterior
            if "SALDO ANTERIOR" in linea_str and "$" in linea_str:
                # Galicia: SALDO ANTERIOR $ 3.618.403,54
                m_ant = re.search(r'SALDO ANTERIOR\s+\$\s*([\d\.\s]+,\d{2})', linea_str)
                if m_ant:
                    ant_str = m_ant.group(1).replace(' ', '')
                    saldo_anterior = self.limpiar_monto(ant_str)
                    
            elif "SALDO ANTERIOR" in linea_str and not "$" in linea_str:
                # Santander: SALDO ANTERIOR     0,00     0,00
                partes = re.split(r'\s{2,}', linea_str)
                if len(partes) >= 2 and self.PAT_MONTO.match(partes[-2]):
                    saldo_anterior = self.limpiar_monto(partes[-2])
                elif len(partes) >= 1 and self.PAT_MONTO.match(partes[-1]):
                    saldo_anterior = self.limpiar_monto(partes[-1])

            # Buscar saldo final
            if "SALDO ACTUAL" in linea_str and "$" in linea_str:
                # SALDO ACTUAL $ 4.943.997,73 U$S 30,99
                m_fin = re.search(r'SALDO ACTUAL\s+\$\s*([\d\.\s]+,\d{2})', linea_str)
                if m_fin:
                    fin_str = m_fin.group(1).replace(' ', '')
                    saldo_final = self.limpiar_monto(fin_str)

            # Evitar headers y sub-totales
            if "Total Consumos" in linea_str or "SALDO ACTUAL" in linea_str or "PAGO MINIMO" in linea_str:
                continue

            # Buscar movimientos por separación tabular
            partes = re.split(r'\s{2,}', linea_str)
            if len(partes) >= 2:
                p1 = partes[-1].strip()
                p2 = partes[-2].strip()
                
                ars_str = ""
                concepto_crudo = ""
                
                es_p1_monto = bool(self.PAT_MONTO.match(p1))
                es_p2_monto = bool(self.PAT_MONTO.match(p2))
                
                if es_p1_monto and es_p2_monto:
                    # Trae ARS y USD
                    ars_str = p2
                    concepto_crudo = " ".join(partes[:-2]).strip()
                elif es_p1_monto:
                    # Trae un solo monto, hay que distinguir si es Pesos o Dolares
                    idx = linea_str.rfind(p1)
                    if "USD" in " ".join(partes[:-1]).upper() or "U$S" in " ".join(partes[:-1]).upper() or "BRL" in " ".join(partes[:-1]).upper():
                        # Es dolar, lo ignoramos
                        continue
                    if idx > 65: # La columna de USD suele estar a la derecha del carácter 65.
                        # Es dólar
                        continue
                    else:
                        ars_str = p1
                        concepto_crudo = " ".join(partes[:-1]).strip()
                        
                if ars_str:
                    ars_val = self.limpiar_monto(ars_str)
                    if ars_val == 0.0:
                        continue
                        
                    # Filtrar comprobante/ticket del concepto
                    # Ej concept: "16.02.25 006117* HIPERPLASTICOS COLOMBRARO C.03/03"
                    # Ej concept: "25 Setiem. 12 102480 * ESTACION DE SERVICIO S"
                    
                    # 1. Quitar fecha del inicio
                    concepto_limpio = re.sub(r'^(?:\d{2}\s+[A-Za-z\.]+\s+)?(?:\d{2}\.\d{2}\.\d{2}|\d{2})\s+', '', concepto_crudo)
                    
                    # 2. Quitar número de ticket (ej: 006117* o 102480 *)
                    concepto_limpio = re.sub(r'^\d{4,}\s*\*?\s*', '', concepto_limpio)
                    
                    # Si era pago en pesos: ("SU PAGO EN PESOS...") o descuento ("BONIF") u original con guion negativo
                    es_pago = False
                    if "PAGO " in concepto_limpio.upper() or "PAYMENT" in concepto_limpio.upper() or "BONIF" in concepto_limpio.upper() or "-" in ars_str:
                        es_pago = True
                        
                    ars_val = abs(ars_val)
                    tipo = self.clasificar_concepto(concepto_limpio)
                    
                    mov = Movimiento(
                        fecha=datetime.now(), # Aproximación por ahora
                        concepto=concepto_limpio,
                        referencia="",
                        descripcion="",
                        debito=0.0 if es_pago else ars_val,
                        credito=ars_val if es_pago else 0.0,
                        tipo=tipo
                    )
                    movimientos.append(mov)

        # Validación matemática de cierre
        suma_gastos = sum(m.debito for m in movimientos)
        suma_pagos = sum(m.credito for m in movimientos)
        es_perfecto = False
        if saldo_final > 0.0:
            calculo = saldo_anterior + suma_gastos - suma_pagos
            es_perfecto = (round(calculo, 2) == round(saldo_final, 2))

        return DatosExtracto(
            banco=f"Tarjeta VISA{' (Validez Verificada)' if es_perfecto else ''}",
            titular=titular if titular else "Titular Desconocido",
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )
