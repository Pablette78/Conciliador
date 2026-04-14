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
        titular = ""

        re_mov = re.compile(r'^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(-?[\d\.]+)(?:\s+\d{2}-\d{2})?\s+([\d\.]+)$')
        re_saldo_ant = re.compile(r'^(\d{2}/\d{2}/\d{4})\s+SALDO ANTERIOR\s+([\d\.]+)$')
        re_titular = re.compile(r'(?:TITULAR|RAZ[OÓ]N\s+SOCIAL)[:\s]+(.+)', re.I)

        with pdfplumber.open(ruta_archivo) as pdf:
            ultimo_mov = None
            
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if not texto: continue
                
                lineas = texto.split('\n')
                for linea in lineas:
                    linea = linea.strip()
                    if not linea: continue

                    # Detectar titular
                    m_tit = re_titular.search(linea)
                    if m_tit and not titular:
                        titular = m_tit.group(1).strip()
                        continue
                    if not titular:
                        l_up = linea.upper()
                        if ('SRL' in l_up or 'SAIC' in l_up or 'S.A' in l_up) and 'CUIT' not in l_up and 'BANCO' not in l_up:
                            titular = linea.strip()

                    # 1. Intentar capturar Saldo Anterior
                    m_sa = re_saldo_ant.match(linea)
                    if m_sa:
                        saldo_anterior = self.limpiar_monto(m_sa.group(2))
                        continue

                    # 2. Intentar capturar Movimiento Normal
                    m_mov = re_mov.match(linea)
                    if m_mov:
                        fecha_str, concepto, importe_str, saldo_str = m_mov.groups()
                        
                        try:
                            fecha = datetime.strptime(fecha_str, '%d/%m/%Y')
                        except ValueError:
                            continue

                        monto = self.limpiar_monto(importe_str)
                        es_negativo = '-' in importe_str
                        
                        debito = monto if es_negativo else 0.0
                        credito = monto if not es_negativo else 0.0
                        
                        saldo_final = self.limpiar_monto(saldo_str)
                        tipo = self.clasificar_concepto(concepto)

                        ultimo_mov = Movimiento(
                            fecha=fecha,
                            concepto=concepto,
                            debito=debito,
                            credito=credito,
                            tipo=tipo,
                            descripcion=concepto
                        )
                        movimientos.append(ultimo_mov)
                    
                    elif ultimo_mov and not re.match(r'^\d{2}/\d{2}/\d{4}', linea):
                        # 3. Concatenar línea huérfana al concepto anterior (multilínea)
                        # Evitar capturar pie de página o encabezados
                        if "PAGINA" in linea.upper() or "FECHA" in linea.upper() or "TOTAL" in linea.upper():
                            continue
                        if len(linea) < 100: # Filtro simple para evitar líneas de ruido largas
                            ultimo_mov.concepto += " " + linea
                            ultimo_mov.descripcion = ultimo_mov.concepto
                            # Re-clasificar con el concepto completo
                            ultimo_mov.tipo = self.clasificar_concepto(ultimo_mov.concepto)

        return DatosExtracto(
            banco="Banco Provincia",
            titular=titular,
            movimientos=movimientos,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final
        )
