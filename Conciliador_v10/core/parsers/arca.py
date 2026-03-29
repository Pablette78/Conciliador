import xlrd
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto

class ARCAParser(BaseParser):
    def parse(self, ruta_archivo: str) -> DatosExtracto:
        wb = xlrd.open_workbook(ruta_archivo)
        ws = wb.sheet_by_index(0)
        
        headers = [str(h).strip() for h in ws.row_values(0)]
        
        # Mapeo de columnas
        idx_monto = -1
        idx_fecha = -1
        idx_ref = -1
        idx_desc = -1
        
        for i, h in enumerate(headers):
            h_up = h.upper()
            # Monto: 'IMPORTE RET./PERC.'
            if 'IMPORTE' in h_up and ('RET' in h_up or 'PERC' in h_up or 'RTE' in h_up):
                idx_monto = i
            # Fecha: 'FECHA RET./PERC.'
            if 'FECHA' in h_up and ('RET' in h_up or 'PERC' in h_up or 'REG' in h_up or 'COMP' in h_up):
                # Priorizar la de Retención sobre otras. Si ya encontramos una de Retención, no sobreescribir.
                actual_tiene_ret = idx_fecha != -1 and 'RET' in headers[idx_fecha].upper()
                nueva_tiene_ret = 'RET' in h_up
                
                if idx_fecha == -1 or (nueva_tiene_ret and not actual_tiene_ret):
                    idx_fecha = i
            # Referencia: 'NÚMERO COMPROBANTE' o 'NÚMERO CERTIFICADO'
            if 'NUMERO' in h_up or 'CERTIFICADO' in h_up or 'COMPROBANTE' in h_up:
                idx_ref = i
            # Descripción: 'DENOMINACIÓN O RAZÓN SOCIAL'
            if 'DENOMINACION' in h_up or 'RAZON SOCIAL' in h_up or 'AGENTE' in h_up:
                idx_desc = i
        
        # Si no se encontró por nombre, fallas silenciosas o logs serían buenos aquí.
        if idx_monto == -1 or idx_fecha == -1:
            # Intentar fallback de última instancia por posición si es un formato conocido
            if ws.ncols >= 13:
                idx_monto = 9
                idx_fecha = 6
                idx_ref = 7
                idx_desc = 1
        
        movimientos = []
        for r in range(1, ws.nrows):
            row = ws.row_values(r)
            if not row: continue
            
            # Fecha
            fecha_val = row[idx_fecha]
            fecha_dt = None
            if isinstance(fecha_val, str):
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        fecha_dt = datetime.strptime(fecha_val.strip(), fmt)
                        break
                    except ValueError:
                        continue
            elif isinstance(fecha_val, float):
                # Excel date
                try:
                    tupla = xlrd.xldate_as_tuple(fecha_val, wb.datemode)
                    fecha_dt = datetime(*tupla[:6])
                except:
                    pass
            
            if not fecha_dt:
                continue
            
            # Monto
            monto_val = row[idx_monto]
            monto = 0.0
            if isinstance(monto_val, (int, float)):
                monto = float(monto_val)
            elif isinstance(monto_val, str):
                monto = self.limpiar_monto(monto_val)
            
            if monto == 0:
                continue
                
            # Referencia y Descripción
            ref = str(row[idx_ref]) if idx_ref < len(row) else ""
            desc = str(row[idx_desc]) if idx_desc < len(row) else ""
            
            movimientos.append(Movimiento(
                fecha=fecha_dt,
                concepto="RETENCION ARCA",
                descripcion=desc,
                referencia=ref,
                debito=0.0,
                credito=abs(monto), # En el mayor suelen estar en el Haber (crédito) si son retenciones sufridas
                tipo="ARCA_RET"
            ))
            
        return DatosExtracto(
            banco="ARCA-Mis Retenciones",
            titular="AFIP / ARCA",
            movimientos=movimientos,
            saldo_anterior=0.0,
            saldo_final=0.0
        )
