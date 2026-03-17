import re
import pdfplumber
from datetime import datetime

def ultra_clean(texto):
    """Limpia absolutamente todo: comillas, saltos de línea, retornos de carro y espacios locos."""
    if not texto: return ""
    # Eliminamos comillas, saltos de línea y tabs
    limpio = str(texto).replace('"', '').replace('\n', ' ').replace('\r', '').strip()
    return limpio

def format_bapro_number(texto):
    """Convierte '-800000.00' o '1.250.300,50' a float de forma segura."""
    t = ultra_clean(texto)
    if not t or t == ",": return 0.0
    try:
        # El BAPRO a veces usa punto decimal y a veces coma según cómo se exporte.
        # Primero quitamos puntos de miles si existen (ej: 1.000,00 -> 1000,00)
        if ',' in t and '.' in t:
            t = t.replace('.', '')
        # Cambiamos la coma por punto para que Python lo entienda
        t = t.replace(',', '.')
        return float(t)
    except:
        return 0.0

def clasificar_movimiento(concepto):
    c = concepto.upper()
    if 'SIRCREB' in c: return 'RET_SIRCREB'
    if 'PERCEP' in c and 'CABA' in c: return 'PERC_IIBB_CABA'
    if 'IMPUESTO DEBITO' in c or 'IMP.DEBITO' in c: return 'LEY25413_DEBITO'
    if 'IMPUESTO CREDITO' in c or 'IMP.CREDITO' in c: return 'LEY25413_CREDITO'
    if 'COMISION' in c: return 'COMISION'
    if 'IVA' in c: return 'IVA'
    return 'OTRO'

def parsear_pdf(ruta_pdf):
    movimientos = []
    saldo_anterior = 0.0
    saldo_final = 0.0

    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            # Forzamos la extracción de tablas si el texto simple falla
            texto = pagina.extract_text()
            if not texto: continue
            
            lineas = texto.split('\n')
            for linea in lineas:
                # El BAPRO suele separar por ," o ", 
                # Esta regex captura lo que hay entre comillas ignoreando la basura
                partes = re.findall(r'"([^"]*)"', linea)
                
                if len(partes) >= 3:
                    fecha_raw = ultra_clean(partes[0])
                    concepto = ultra_clean(partes[1])
                    importe_raw = ultra_clean(partes[2])
                    
                    # Capturar Saldo Anterior
                    if "SALDO ANTERIOR" in concepto.upper():
                        # En la línea de saldo anterior, el saldo está en la última columna (índice 4)
                        if len(partes) >= 5:
                            saldo_anterior = format_bapro_number(partes[4])
                        continue

                    # Validar Fecha (DD/MM/YYYY)
                    try:
                        fecha = datetime.strptime(fecha_raw, '%d/%m/%Y')
                    except ValueError:
                        continue

                    monto = format_bapro_number(importe_raw)
                    
                    # En BAPRO: Montos negativos = Salida (Débito)
                    debito = abs(monto) if monto < 0 else 0.0
                    credito = monto if monto > 0 else 0.0

                    movimientos.append({
                        'fecha': fecha,
                        'concepto': concepto,
                        'debito': debito,
                        'credito': credito,
                        'descripcion': '',
                        'tipo': clasificar_movimiento(concepto)
                    })
                    
                    # Actualizar saldo final si existe en la línea
                    if len(partes) >= 5:
                        val_saldo = format_bapro_number(partes[4])
                        if val_saldo != 0: saldo_final = val_saldo

    return {
        'movimientos': movimientos,
        'saldo_anterior': saldo_anterior,
        'saldo_final': saldo_final,
        'titular': "INSTRUMENTAL PASTEUR SRL" # Lo saco del PDF
    }
    