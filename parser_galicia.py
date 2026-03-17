"""
Parser para extractos del Banco Galicia.
Extrae los movimientos del PDF y los clasifica por tipo.

Formato Galicia:
- Fechas: DD/MM/YY
- Descripciones multilínea (transferencias incluyen nombre, CUIT, CBU, etc.)
- Débitos como números negativos con signo menos
- Créditos como números positivos
"""
import re
from datetime import datetime


def parsear_numero(texto):
    """Convierte '10.578,10' o '-281,91' a float"""
    if not texto:
        return 0.0
    texto = texto.strip().replace('.', '').replace(',', '.')
    try:
        return float(texto)
    except ValueError:
        return 0.0


def clasificar_movimiento(concepto):
    """Clasifica un movimiento bancario del Galicia por su concepto"""
    c = concepto.upper()

    # Retenciones e impuestos
    if 'SIRCREB' in c:
        return 'RET_SIRCREB'
    if 'TUCUMAN' in c or 'DT.301' in c:
        return 'RET_IIBB_TUCUMAN'
    if 'IMP. ING. BRUTOS' in c or 'ING. BRUTOS' in c and 'CAPITAL' in c:
        return 'PERC_IIBB_CABA'
    if 'IMP. CRE. LEY 25413' in c or 'IMP CRE LEY 25413' in c:
        return 'LEY25413_CREDITO'
    if 'IMP. DEB. LEY 25413' in c or 'IMP DEB LEY 25413' in c:
        return 'LEY25413_DEBITO'
    if 'PERCEP. IVA' in c or 'PERCEP IVA' in c:
        return 'PERC_IVA'
    if 'IMPUESTO DE SELLOS' in c:
        return 'IMP_SELLOS'

    # Comisiones y gastos bancarios
    if 'COMISION' in c:
        return 'COMISION'
    if c.startswith('IVA') or c == 'IVA':
        return 'IVA'
    if 'INTERESES SOBRE SALDO' in c or 'INTERES' in c:
        return 'INTERESES'

    # Transferencias propias
    if 'MISMA TITULARIDAD' in c or 'TRANSFER. CASH MISMA' in c:
        return 'TRANSFER_PROPIA'

    # Transferencias de terceros (ingresos)
    if 'TRANSFERENCIA DE TERCEROS' in c:
        return 'TRANSFERENCIA'
    if 'CREDITO TRANSFERENCIA' in c and 'COELSA' in c:
        return 'TRANSFERENCIA'

    # Pagos a proveedores (pueden ser créditos o débitos según el caso)
    if 'SERVICIO PAGO A PROVEEDORES' in c or 'SNP PAGO A PROVEEDORES' in c:
        return 'PAGO_PROVEEDORES'
    if 'TRANSFERENCIAS CASH' in c and 'PROVEEDORES' in c:
        return 'PAGO_PROVEEDORES'
    if 'TRF INMED PROVEED' in c:
        return 'PAGO_PROVEEDORES'

    # ECHEQ
    if 'ECHEQ' in c:
        return 'ECHEQ'

    # Pagos de servicios
    if 'PAGO DE SERVICIOS' in c:
        return 'PAGO_SERVICIOS'
    if 'PAGO VISA' in c:
        return 'PAGO_SERVICIOS'

    # Débitos automáticos
    if 'DEB. AUTOM' in c or 'DEB.AUTOM' in c:
        return 'DEB_AUTOMATICO'

    # Depósitos en efectivo
    if 'DEP.EFVO' in c or 'DEP EFVO' in c:
        return 'DEPOSITO_EFECTIVO'

    # Haberes / sueldos
    if 'HABERES' in c or 'ACRED.HABERES' in c:
        return 'HABERES'

    # AFIP
    if 'TRANSF. AFIP' in c or 'AFIP' in c:
        return 'TRANSF_AFIP'

    return 'OTRO'


def parsear_pdf(ruta_pdf):
    """
    Lee un PDF del Banco Galicia y devuelve:
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

    # Buscar titular
    for linea in lineas:
        if 'SAIC' in linea.upper() or 'SRL' in linea.upper() or 'S.A' in linea.upper():
            if 'CUIT' not in linea.upper() and 'BANCO' not in linea.upper() and not titular:
                titular = linea.strip()
                break

    # Buscar saldos - Galicia usa formato "$32.338.025,88"
    for i, linea in enumerate(lineas):
        l = linea.upper().strip()
        if 'SALDO INICIAL' in l or 'SALDO ANTERIOR' in l:
            numeros = re.findall(r'\$?\s*([\d.]+,\d{2})', linea)
            if numeros:
                saldo_anterior = parsear_numero(numeros[-1])
        if 'SALDO FINAL' in l:
            numeros = re.findall(r'\$?\s*([\d.]+,\d{2})', linea)
            if numeros:
                saldo_final = parsear_numero(numeros[-1])

    # Segundo intento: buscar "Saldo inicial" (case mixed) y monto en línea siguiente
    if saldo_anterior == 0:
        for i, linea in enumerate(lineas):
            if 'saldo inicial' in linea.lower():
                numeros = re.findall(r'\$\s*([\d.]+,\d{2})', linea)
                if numeros:
                    saldo_anterior = parsear_numero(numeros[-1])
                elif i + 1 < len(lineas):
                    numeros = re.findall(r'\$\s*([\d.]+,\d{2})', lineas[i + 1])
                    if numeros:
                        saldo_anterior = parsear_numero(numeros[-1])
            if 'saldo final' in linea.lower():
                numeros = re.findall(r'\$\s*([\d.]+,\d{2})', linea)
                if numeros:
                    saldo_final = parsear_numero(numeros[-1])
                elif i + 1 < len(lineas):
                    numeros = re.findall(r'\$\s*([\d.]+,\d{2})', lineas[i + 1])
                    if numeros:
                        saldo_final = parsear_numero(numeros[-1])

    # Tercer intento: Galicia pone los saldos como líneas sueltas "$XX.XXX,XX"
    # después de la línea "Saldos" en la primera página
    if saldo_anterior == 0:
        buscando_saldos = False
        saldos_encontrados = []
        for linea in lineas[:50]:  # solo en las primeras líneas
            if 'saldos' in linea.lower() and 'deudor' not in linea.lower():
                buscando_saldos = True
                continue
            if buscando_saldos:
                m = re.match(r'^\$\s*([\d.]+,\d{2})$', linea.strip())
                if m:
                    saldos_encontrados.append(parsear_numero(m.group(1)))
                elif saldos_encontrados:
                    break
        if len(saldos_encontrados) >= 2:
            saldo_anterior = saldos_encontrados[0]
            saldo_final = saldos_encontrados[1]
        elif len(saldos_encontrados) == 1:
            saldo_anterior = saldos_encontrados[0]

    # Patron para fechas Galicia: DD/MM/YY
    patron_fecha = re.compile(r'^(\d{2}/\d{2}/\d{2})\s+(.+)')

    # Patron para montos: con o sin signo negativo
    patron_monto = re.compile(r'-?[\d.]+,\d{2}')

    # Parsear movimientos
    # Cada movimiento empieza con una fecha DD/MM/YY
    # Las líneas siguientes sin fecha son continuación de la descripción
    movimiento_actual = None

    for linea in lineas:
        linea = linea.strip()

        # Ignorar líneas de encabezado
        if any(x in linea for x in ['Fecha Descripción', 'Resumen de Cuenta',
                                     'Página', '20260227', 'Consolidado',
                                     'PERIODO COMPRENDIDO', 'TOTAL RETENCION',
                                     'TOTAL IMPUESTO', 'TOTAL MENSUAL']):
            continue

        # Ignorar la línea de totales
        if linea.startswith('Total'):
            continue

        match = patron_fecha.match(linea)

        if match:
            # Guardar movimiento anterior si existe
            if movimiento_actual:
                movimientos.append(movimiento_actual)

            fecha_str = match.group(1)
            resto = match.group(2)

            # Parsear fecha DD/MM/YY
            try:
                fecha = datetime.strptime(fecha_str, '%d/%m/%y')
            except ValueError:
                movimiento_actual = None
                continue

            # Extraer montos del resto de la línea
            montos = patron_monto.findall(resto)

            # Extraer concepto (texto antes del primer monto o código origen)
            # El concepto es la parte textual
            concepto = re.sub(r'-?[\d.]+,\d{2}', '', resto).strip()
            # Limpiar códigos de origen como "Q 284", "00D4", "0001", etc.
            concepto = re.sub(r'\s+[A-Z0-9]{4}\s*$', '', concepto).strip()
            concepto = re.sub(r'\s+Q\s+\d+', '', concepto).strip()
            concepto = re.sub(r'\s{2,}', ' ', concepto).strip()

            credito = 0.0
            debito = 0.0
            descripcion = ""

            if montos:
                # En Galicia: el último monto siempre es el saldo
                # Si hay 3 montos: crédito, débito(?), saldo - raro
                # Si hay 2 montos: monto + saldo
                # Si hay 1 monto: solo saldo (monto en línea anterior?)

                if len(montos) >= 2:
                    monto_val = parsear_numero(montos[0])
                    # saldo = montos[-1]
                    if monto_val < 0:
                        debito = abs(monto_val)
                    else:
                        credito = monto_val
                elif len(montos) == 1:
                    # Solo saldo, no hay monto - probablemente es continuación
                    monto_val = parsear_numero(montos[0])
                    # Chequear si el concepto sugiere que es solo una línea de saldo
                    pass

            tipo = clasificar_movimiento(concepto)

            movimiento_actual = {
                'fecha': fecha,
                'concepto': concepto,
                'debito': debito,
                'credito': credito,
                'descripcion': '',
                'tipo': tipo,
            }

        elif movimiento_actual:
            # Línea de continuación de descripción
            stripped = linea.strip()

            if not stripped:
                continue

            # Verificar si esta línea tiene un monto que corresponde al movimiento
            montos_cont = patron_monto.findall(stripped)

            if montos_cont and movimiento_actual['credito'] == 0 and movimiento_actual['debito'] == 0:
                for m in montos_cont:
                    val = parsear_numero(m)
                    if val != 0:
                        if val < 0:
                            movimiento_actual['debito'] = abs(val)
                        else:
                            movimiento_actual['credito'] = val
                        break

            # Agregar a la descripción (nombre de persona, etc.)
            if not re.match(r'^[\d\s]+$', stripped) and \
               not stripped.startswith('5892440') and \
               not stripped.startswith('0070') and \
               stripped not in ('VARIOS', 'ALQUILERES', 'CUOTA', 'FACTURA', 'FACTURAS'):
                if movimiento_actual['descripcion']:
                    movimiento_actual['descripcion'] += ' ' + stripped
                else:
                    movimiento_actual['descripcion'] = stripped

            # Reclasificar usando concepto + descripción completa
            # (las retenciones IIBB tienen la jurisdicción en la 2da línea)
            texto_completo_mov = movimiento_actual['concepto'] + ' ' + movimiento_actual['descripcion']
            nuevo_tipo = clasificar_movimiento(texto_completo_mov)
            if nuevo_tipo != 'OTRO' and movimiento_actual['tipo'] == 'OTRO':
                movimiento_actual['tipo'] = nuevo_tipo

    # No olvidar el último movimiento
    if movimiento_actual:
        movimientos.append(movimiento_actual)

    # Limpiar: remover movimientos sin monto
    movimientos = [m for m in movimientos if m['debito'] > 0 or m['credito'] > 0]

    # Si no encontramos saldo final, usar el último saldo
    if saldo_final == 0 and movimientos:
        # Buscar en el texto "$ 99.447.097,34" al final
        for linea in reversed(lineas):
            montos = re.findall(r'\$\s*([\d.]+,\d{2})', linea)
            if montos:
                val = parsear_numero(montos[-1])
                if val > 0:
                    saldo_final = val
                    break

    return {
        'movimientos': movimientos,
        'saldo_anterior': saldo_anterior,
        'saldo_final': saldo_final,
        'titular': titular,
    }
