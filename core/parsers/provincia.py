import re
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto

class ProvinciaParser(BaseParser):
    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber
        
        movimientos = []
        saldo_anterior = 0.0
        saldo_final = 0.0
        titular = "INSTRUMENTAL PASTEUR SRL" # Valor por defecto de los scripts originales

        with pdfplumber.open(ruta_archivo) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if not texto: continue
                
                lineas = texto.split('\n')
                for linea in lineas:
                    # El BAPRO suele separar por ," o ", 
                    partes = re.findall(r'"([^"]*)"', linea)
                    
                    if len(partes) >= 3:
                        fecha_raw = partes[0].strip()
                        concepto = partes[1].strip()
                        importe_raw = partes[2].strip()
                        
                        # Capturar Saldo Anterior
                        if "SALDO ANTERIOR" in concepto.upper():
                            if len(partes) >= 5:
                                saldo_anterior = self.limpiar_monto(partes[4])
                            continue

                        # Validar Fecha (DD/MM/YYYY)
                        try:
                            fecha = datetime.strptime(fecha_raw, '%d/%m/%Y')
                        except ValueError:
                            continue

                        monto = self.limpiar_monto(importe_raw)
                        # En BAPRO original: Montos negativos en archivo = Salida
                        # Pero limpiar_monto devuelve abs(). 
                        # Revisando el original: debito = abs(monto) if monto < 0 else 0.0
                        # Como limpiar_monto quita el signo, necesitamos saber si el original tenía '-'
                        
                        es_negativo = '-' in importe_raw
                        debito = monto if es_negativo else 0.0
                        credito = monto if not es_negativo else 0.0

                        tipo = self.clasificar_concepto(concepto)

                        movimientos.append(Movimiento(
                            fecha=fecha,
                            concepto=concepto,
                            debito=debito,
                            credito=credito,
                            tipo=tipo,
                            descripcion=concepto
                        ))
                        
                        # Actualizar saldo final si existe en la línea
                        if len(partes) >= 5:
                            val_saldo = self.limpiar_monto(partes[4])
                            if val_saldo != 0: saldo_final = val_saldo

        return DatosExtracto(
            banco="Banco Provincia",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )
