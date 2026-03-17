"""
Parser para extractos del Banco Ciudad.
Extrae los movimientos del PDF y los clasifica por tipo.
"""
import re
from datetime import datetime

MESES = {
    'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
}


def parsear_numero(texto):
    """Convierte '10.578,10' a 10578.10"""
    if not texto:
        return 0.0
    texto = texto.strip().replace('.', '').replace(',', '.')
    try:
        return float(texto)
    except ValueError:
        return 0.0


def parsear_fecha(texto):
    """Convierte '02-ENE-2026' a datetime"""
    partes = texto.strip().split('-')
    if len(partes) != 3:
        return None
    dia = int(partes[0])
    mes = MESES.get(partes[1].upper(), 0)
    anio = int(partes[2])
    if mes == 0:
        return None
    return datetime(anio, mes, dia)


def clasificar_movimiento(concepto):
    """Clasifica un movimiento bancario por su concepto"""
    concepto_upper = concepto.upper()
    if 'SIRCREB' in concepto_upper:
        return 'RET_SIRCREB'
    elif 'IIBB TUCUM' in concepto_upper:
        return 'RET_IIBB_TUCUMAN'
    elif 'PERC IIBB CABA' in concepto_upper:
        return 'PERC_IIBB_CABA'
    elif 'LEY 25413' in concepto_upper and 'CRED' in concepto_upper:
        return 'LEY25413_CREDITO'
    elif 'LEY 25413' in concepto_upper or 'LEY25413' in concepto_upper:
        return 'LEY25413_DEBITO'
    elif 'COMISION' in concepto_upper or 'COMIS' in concepto_upper:
        return 'COMISION'
    elif 'DEBITO FISCAL' in concepto_upper or 'IVA' in concepto_upper:
        return 'IVA'
    elif 'RETENCION IVA' in concepto_upper:
        return 'RET_IVA'
    elif 'TRANSFERENCIA' in concepto_upper:
        return 'TRANSFERENCIA'
    elif 'TRANSPORTE' in concepto_upper:
        return 'TRANSPORTE'
    else:
        return 'OTRO'


def parsear_pdf(ruta_pdf):
    """
    Lee un PDF del Banco Ciudad y devuelve:
    - movimientos: lista de dicts con fecha, concepto, debito, credito, descripcion, tipo
    - saldo_anterior: float
    - saldo_final: float
    - titular: str
    """
    import pdfplumber

    movimientos = []
    saldo_anterior = 0.0
    saldo_final = 0.0
    titular = ""

    with pdfplumber.open(ruta_pdf) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    lineas = texto_completo.split('\n')

    # Buscar saldo anterior
    for linea in lineas:
        if 'SALDO ANTERIOR' in linea.upper():
            numeros = re.findall(r'[\d.]+,\d{2}', linea)
            if numeros:
                saldo_anterior = parsear_numero(numeros[-1])

        # Buscar titular
        if 'INSTRUMENTAL' in linea.upper() or 'SRL' in linea.upper() or 'S.A' in linea.upper():
            if not titular and 'CUIT' not in linea.upper():
                titular = linea.strip()

    # Patron para lineas de movimientos
    # Formato: DD-MMM-YYYY CONCEPTO [DEBITO] [CREDITO] SALDO [DESCRIPCION]
    patron_fecha = re.compile(r'^(\d{2}-[A-Z]{3}-\d{4})\s+(.+)')

    for linea in lineas:
        linea = linea.strip()
        match = patron_fecha.match(linea)
        if not match:
            continue

        fecha_str = match.group(1)
        resto = match.group(2)
        fecha = parsear_fecha(fecha_str)
        if not fecha:
            continue

        # Ignorar transportes
        if 'TRANSPORTE' in resto.upper():
            continue

        # Extraer numeros del resto de la linea
        numeros = re.findall(r'[\d.]+,\d{2}', resto)
        # Extraer concepto (texto antes del primer numero)
        concepto_match = re.match(r'^([A-Za-z/\s\d]+?)(?:\s+\d)', resto)
        if concepto_match:
            concepto = concepto_match.group(1).strip()
        else:
            concepto = resto.split()[0] if resto.split() else "DESCONOCIDO"

        # Limpiar concepto
        concepto_parts = re.match(r'^([A-Za-zÁÉÍÓÚáéíóú\s/\d]+)', resto)
        if concepto_parts:
            concepto = concepto_parts.group(1).strip()
            # Remover numeros sueltos al final del concepto
            concepto = re.sub(r'\s+\d+$', '', concepto)

        tipo = clasificar_movimiento(concepto)

        debito = 0.0
        credito = 0.0
        descripcion = ""

        if tipo == 'TRANSFERENCIA':
            # Transferencias: pueden tener credito (entrada) o debito (salida)
            # Buscar descripcion al final (CUIT-NOMBRE)
            desc_match = re.search(r'(\d{11}[\s-][A-Z/\s]+)$', resto)
            if desc_match:
                descripcion = desc_match.group(1).strip()

            if len(numeros) >= 2:
                # Si hay al menos 2 numeros, el primero es monto y el segundo es saldo
                monto = parsear_numero(numeros[0])
                # Determinar si es debito o credito segun el saldo
                # Las transferencias entrantes son credito
                credito = monto
            elif len(numeros) == 1:
                credito = parsear_numero(numeros[0])
        else:
            # Débitos bancarios: el primer numero es el monto debitado
            if numeros:
                debito = parsear_numero(numeros[0])

        if debito > 0 or credito > 0:
            movimientos.append({
                'fecha': fecha,
                'concepto': concepto,
                'debito': debito,
                'credito': credito,
                'descripcion': descripcion,
                'tipo': tipo,
            })

    # Buscar saldo final
    for linea in lineas:
        if 'SALDO AL' in linea.upper():
            numeros = re.findall(r'[\d.]+,\d{2}', linea)
            if numeros:
                saldo_final = parsear_numero(numeros[-1])

    return {
        'movimientos': movimientos,
        'saldo_anterior': saldo_anterior,
        'saldo_final': saldo_final,
        'titular': titular,
    }
