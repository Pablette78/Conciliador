import re
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto
import pdfplumber

class AmexParser(BaseParser):
    PAT_FECHA_MES = re.compile(r'^(\d{2}) de (Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre)', re.IGNORECASE)
    
    MESES = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }

    def parse(self, ruta_archivo: str) -> DatosExtracto:
        titular = ""
        saldo_anterior = 0.0
        saldo_final = 0.0
        movimientos = []
        año_vencimiento = datetime.now().year

        lineas = []
        with pdfplumber.open(ruta_archivo) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text(layout=True)
                if texto:
                    lineas.extend(texto.split('\n'))

        # Variables de estado
        en_bloque_pesos = False
        en_bloque_dolares = False
        
        # Primero una pasada para encontrar titular, saldos y fecha de vencimiento general
        for i, linea in enumerate(lineas):
            linea_str = linea.strip()
            
            # Buscar Titular
            if "Nuevos Cargos en PESOS para " in linea_str:
                parts = linea_str.split("Nuevos Cargos en PESOS para ")
                if len(parts) > 1:
                    tit_candidato = parts[1].split()[0] + " " + parts[1].split()[1] if len(parts[1].split()) >= 2 else parts[1]
                    # limpiar espacios adicionales
                    titular = re.sub(r'\s{2,}.*', '', parts[1]).strip()
            
            # Buscar Saldo Anterior y Saldo a Pagar en el cuadro principal
            # Típicamente está debajo de "Saldo Anterior $ Créditos $ Débitos $ Saldo a pagar $"
            if "Saldo Anterior $" in linea_str and "Créditos $" in linea_str:
                if i + 1 < len(lineas):
                    valores = re.findall(r'[\d.,]+', lineas[i+1])
                    if valores:
                        # saldo anterior suele ser el primer monto
                        saldo_anterior = self.limpiar_monto(valores[0])
            
            if "Total de Cargos en PESOS" in linea_str:
                valores = re.findall(r'[\d.,]+', linea_str)
                if valores:
                    saldo_final = self.limpiar_monto(valores[-1])
            
            # Buscar el año del vencimiento (Próxima fecha de vencimiento: 22/12/25 o similar)
            match_vto = re.search(r'Próxima fecha de vencimiento:\s*(\d{2}/\d{2}/\d{2})', linea_str, re.IGNORECASE)
            if match_vto:
                try:
                    fecha_vto = datetime.strptime(match_vto.group(1), '%d/%m/%y')
                    año_vencimiento = fecha_vto.year
                except ValueError:
                    pass

        # Parseo de transacciones
        mov_actual = None

        for linea in lineas:
            linea_str = linea.strip()
            if not linea_str:
                continue
                
            # Detectar sección de pesos/dólares
            # En Amex, suelen aparecer "Nuevos Cargos en PESOS para..." o "Fecha y detalle de las transacciones"
            if "Nuevos Cargos en PESOS" in linea_str or ("Fecha y detalle" in linea_str and "Importe en $" in linea_str):
                en_bloque_pesos = True
                continue
            if "Total de Cargos en PESOS" in linea_str:
                en_bloque_pesos = False
            
            if "DOLARES" in linea_str or "Importe en U$S" in linea_str:
                en_bloque_pesos = False
                en_bloque_dolares = True

            if not en_bloque_pesos:
                continue
            
            # Extraer fecha
            # Ej: "20 de Octubre CEAMSE  0000196008                                   4 .774,88"
            match_fecha = self.PAT_FECHA_MES.match(linea_str)
            if match_fecha:
                if mov_actual:
                    movimientos.append(mov_actual)

                dia = int(match_fecha.group(1))
                mes_str = match_fecha.group(2).lower()
                mes = self.MESES.get(mes_str, 1)
                
                # Asignamos el año de vencimiento. Si el mes es diciembre y el vto es enero, puede pasar, pero asumimos el del vto
                # Ajuste de año: Si el mes del movimiento es mayor al mes de vencimiento, probablemente sea del año anterior
                año_mov = año_vencimiento
                if mes == 12 and año_vencimiento == 2026: # Todo: logical check, if statement can be better but we trust the base year. 
                    pass

                fecha_mov = datetime(año_vencimiento, mes, dia)

                # Extraer monto al final.
                # En AMEX el monto siempre viene separado por MUCHOS espacios del resto (referencias, etc).
                # Buscamos al menos 3 espacios seguidos y tomamos todo lo que está a la derecha como el monto.
                partes = re.split(r'\s{3,}', linea_str)
                monto_val = 0.0
                concepto = linea_str

                if len(partes) > 1:
                    ultimo_bloque = partes[-1]
                    # Validar si el último bloque parece un monto (dígitos, comas, puntos y posibles espacios intermedios)
                    if re.match(r'^[\d., ]+$', ultimo_bloque):
                        monto_val = self.limpiar_monto(ultimo_bloque)
                        # El concepto es todo lo anterior unido
                        concepto = " ".join(partes[:-1]).strip()
                else:
                    # Fallback por si acaso
                    monto_match = re.search(r'\s+([\d.,]+)$', linea_str)
                    if monto_match:
                        monto_val = self.limpiar_monto(monto_match.group(1))
                        concepto = linea_str[:monto_match.start()].strip()
                
                
                # Quitar códigos numéricos largos (números de ticket/comprobante)
                concepto = re.sub(r'\b\d{6,}\b', '', concepto).strip()
                # Limpiar la fecha del concepto
                concepto = self.PAT_FECHA_MES.sub('', concepto).strip()
                
                # Reseteamos una flag para saber si el movimiento ya cargó su referencia
                mov_completo = False
                
                credito = 0.0
                debito = 0.0
                
                # En AMEX, un Pago o crédito viene con sufijo "CR" en líneas siguientes,
                # Pero en la misma línea a veces dice "Gracias por su pago".
                if "pago realizado" in concepto.lower() or "su pago" in concepto.lower() or "pago de su saldo" in concepto.lower():
                    credito = monto_val
                else:
                    debito = monto_val
                    
                tipo = self.clasificar_concepto(concepto)

                mov_actual = Movimiento(
                    fecha=fecha_mov,
                    concepto=concepto,
                    debito=debito,
                    credito=credito,
                    descripcion="",
                    tipo=tipo
                )
            
            elif mov_actual and not mov_completo and not ("Fecha y detalle" in linea_str or "Continuación" in linea_str):
                # Líneas adicionales del movimiento (ej: "Peaje", "Referencia 321011640 0 1", "CR")
                if "CR" in linea_str.split(): 
                    # si vemos un CR suelto, es crédito
                    if mov_actual.debito > 0:
                        mov_actual.credito = mov_actual.debito
                        mov_actual.debito = 0.0
                else:
                    if "Referencia" in linea_str:
                        mov_actual.referencia = linea_str.replace("Referencia", "").strip()
                        # En AMEX, la Referencia es la última línea estructural del consumo.
                        # Marcamos completo para no arrastrar basura de encabezados/pies de página (ej. urls que tengan .com y las detecte como COMISION)
                        mov_completo = True
                    else:
                        # Ignorar basura obvia de pie de página/headers
                        if "www.americanexpress" in linea_str.lower() or "estado de cuenta" in linea_str.lower() or "corporate services" in linea_str.lower():
                            continue
                            
                        mov_actual.descripcion += f" {linea_str}"
                        mov_actual.descripcion = mov_actual.descripcion.strip()
                        
                        # Reevaluar tipo
                        nuevo_tipo = self.clasificar_concepto(f"{mov_actual.concepto} {mov_actual.descripcion}")
                        if nuevo_tipo != 'OTRO':
                            mov_actual.tipo = nuevo_tipo

        if mov_actual:
            movimientos.append(mov_actual)

        # ---------------------------------------------------------------------
        # VALIDACIÓN MATEMÁTICA INTERNA
        # ---------------------------------------------------------------------
        suma_gastos = sum(m.debito for m in movimientos)
        # Si la suma de gastos detectados coincide con el Saldo a Pagar (o Total de Cargos en PESOS),
        # significa que levantamos estrictamente TODO el PDF al centavo.
        es_perfecto = (round(suma_gastos, 2) == round(saldo_final, 2))
        
        return DatosExtracto(
            banco=f"American Express{' (Validez Verificada)' if es_perfecto else ''}",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )
