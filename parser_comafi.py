"""
Parser para extractos del Banco Comafi.
Formato: Fecha DD/MM/YY, Conceptos, Referencias, Débitos, Créditos, Saldo
Particularidades:
- Líneas "Transporte" entre páginas (ignorar)
- Devoluciones de impuestos como créditos (Dev.Imp.IB, Dev. Imp. a los debitos)
- Créditos a comercios Tarj.Cred como ingresos
- Saldo Anterior en primera línea de datos
- Saldo final en "Saldo al: DD/MM/YYYY"
"""
import re
from datetime import datetime


def parsear_numero(texto):
    """Convierte '10.578,10' a float"""
    if not texto:
        return 0.0
    texto = texto.strip().replace('.', '').replace(',', '.')
    try:
        return abs(float(texto))
    except ValueError:
        return 0.0


def clasificar_movimiento(concepto):
    c = concepto.upper()

    # Devoluciones de impuestos (son créditos, no gastos)
    if 'DEV.IMP.IB' in c or 'DEV IMP.IB' in c:
        return 'DEV_IIBB'
    if 'DEV. IMP. A LOS DEBITOS' in c or 'DEV.IMP. A LOS DEBITOS' in c:
        return 'DEV_IMP_DEBITOS'

    # Retenciones IIBB
    if 'SIRCREB' in c or 'SIRC' in c:
        return 'RET_SIRCREB'
    if 'TUCU' in c and ('IB' in c or 'BRUTOS' in c):
        return 'RET_IIBB_TUCUMAN'
    if 'PERCEP' in c and 'IIBB' in c and 'CABA' in c:
        return 'PERC_IIBB_CABA'

    # Ley 25413
    if 'CREDITOS' in c and ('TASA' in c or 'LEY' in c):
        return 'LEY25413_CREDITO'
    if 'DEBITOS' in c and ('TASA' in c or 'LEY' in c):
        return 'LEY25413_DEBITO'

    # IVA
    if 'PERCEPCION IVA' in c or 'PERCEP IVA' in c or 'PERCEPCION IVA RG' in c:
        return 'PERC_IVA'
    if 'IVA' in c and ('ALICUOTA' in c or 'GENERAL' in c or 'REDUCIDA' in c):
        return 'IVA'

    # Comisiones
    if 'COMISION' in c or 'COMIS' in c:
        return 'COMISION'

    # Intereses
    if 'INTERESES' in c or 'INTERES' in c:
        return 'INTERESES'

    # Sellos
    if 'SELLOS' in c:
        return 'IMP_SELLOS'

    # Créditos tarjeta (ingresos operativos)
    if 'CREDITOS A COMERCIOS' in c:
        return 'CRED_TARJETA'

    # Débitos tarjeta
    if 'DEBITOS A COMERCIOS' in c:
        return 'DEB_TARJETA'

    # Acreditación de recaudaciones
    if 'ACREDITACION DE RECAUD' in c:
        return 'TRANSFERENCIA'

    # Transferencias propias
    if 'CUENTAS PROPIAS' in c or 'TRANSF INMED' in c:
        return 'TRANSFER_PROPIA'

    # Pago de servicios
    if 'PAGO DE SERVICIOS' in c:
        return 'PAGO_SERVICIOS'

    return 'OTRO'


def parsear_pdf(ruta_pdf):
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

    # Buscar titular
    for linea in lineas:
        l = linea.upper().strip()
        if 'TITULAR' in l and 'CUIT' in l:
            continue
        if ('ETRA' in l or 'SAIC' in l or 'SRL' in l or 'S.A' in l):
            if 'CUIT' not in l and 'BANCO' not in l and 'COMAFI' not in l:
                # Limpiar "Hoja:X/Y" y similares
                limpio = re.sub(r'Hoja:\d+/\d+', '', linea).strip()
                limpio = re.sub(r'\d+\.\d+ - \d+/\d+.*', '', limpio).strip()
                if limpio and not titular:
                    titular = limpio
                    break

    # Patron: DD/MM/YY seguido de texto
    patron_fecha = re.compile(r'^(\d{2}/\d{2}/\d{2})\s+(.+)')
    patron_monto = re.compile(r'([\d.]+,\d{2})')

    for linea in lineas:
        linea = linea.strip()

        # Buscar saldo anterior (formato: "31/12/25 Saldo Anterior 194.916,26")
        if 'Saldo Anterior' in linea or 'saldo anterior' in linea.lower():
            montos = patron_monto.findall(linea)
            if montos and saldo_anterior == 0:
                val = parsear_numero(montos[-1])
                if val > 0 or saldo_anterior == 0:
                    saldo_anterior = val
            continue

        # Buscar saldo final (formato: "Saldo al: 31/01/2026 5.564.617,02")
        if 'Saldo al:' in linea or 'saldo al:' in linea.lower():
            montos = patron_monto.findall(linea)
            if montos:
                val = parsear_numero(montos[-1])
                if val > 0 or saldo_final == 0:
                    saldo_final = val
            continue

        # Ignorar transportes, encabezados, separadores
        if 'Transporte' in linea or 'transporte' in linea.lower():
            continue
        if linea.startswith('Fecha') or linea.startswith('---') or not linea:
            continue
        if 'Hoja:' in linea or 'ETRA SAICF' in linea or '80.554' in linea or '80.555' in linea:
            continue
        if 'IMPUESTOS DEBITADOS' in linea.upper() or 'Base Imponible' in linea:
            continue

        match = patron_fecha.match(linea)
        if not match:
            continue

        fecha_str = match.group(1)
        resto = match.group(2)

        try:
            fecha = datetime.strptime(fecha_str, '%d/%m/%y')
        except ValueError:
            continue

        # Extraer concepto y referencia
        # Formato: "Concepto texto referencia NNNNNNN monto1 [monto2]"
        # Los montos están al final de la línea

        montos = patron_monto.findall(resto)

        # Quitar montos del texto para obtener concepto
        texto_sin_montos = resto
        for m in montos:
            texto_sin_montos = texto_sin_montos.replace(m, '', 1)
        texto_sin_montos = re.sub(r'\s+', ' ', texto_sin_montos).strip()

        # Separar concepto de referencia
        # La referencia suele ser un número de 7 dígitos al final del concepto
        ref_match = re.search(r'\s(\d{7})\s*$', texto_sin_montos)
        if ref_match:
            concepto = texto_sin_montos[:ref_match.start()].strip()
        else:
            concepto = texto_sin_montos.strip()

        if not concepto:
            continue

        tipo = clasificar_movimiento(concepto)

        credito = 0.0
        debito = 0.0

        # Determinar si es débito o crédito según el tipo de movimiento
        # En Comafi: Débitos y Créditos están en columnas separadas
        # Pero en el texto extraído vienen como números sueltos

        if len(montos) >= 2:
            # Dos montos: uno es débito/crédito, otro es saldo
            monto_val = parsear_numero(montos[0])
            # Tipos que son crédito (entrada de dinero)
            if tipo in ('TRANSFERENCIA', 'CRED_TARJETA',
                        'DEV_IIBB', 'DEV_IMP_DEBITOS'):
                credito = monto_val
            else:
                debito = monto_val
        elif len(montos) == 1:
            monto_val = parsear_numero(montos[0])
            if tipo in ('TRANSFERENCIA', 'CRED_TARJETA',
                        'DEV_IIBB', 'DEV_IMP_DEBITOS'):
                credito = monto_val
            else:
                debito = monto_val

        if debito > 0 or credito > 0:
            movimientos.append({
                'fecha': fecha,
                'concepto': concepto,
                'debito': debito,
                'credito': credito,
                'descripcion': '',
                'tipo': tipo,
            })

    return {
        'movimientos': movimientos,
        'saldo_anterior': saldo_anterior,
        'saldo_final': saldo_final,
        'titular': titular,
    }
