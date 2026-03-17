"""
Parser para extractos del Banco ICBC (Industrial and Commercial Bank of China Argentina).
Formato: PDF con columnas fijas FECHA | CONCEPTO | F.VALOR | COMPROBANTE | ORIGEN | CANAL | DEBITOS | CREDITOS | SALDOS

Particularidades ICBC:
- Fechas en formato DD-MM (el año se obtiene del encabezado del período)
- Débitos terminan con '-' (ej: 250,96-)
- Créditos son números planos (ej: 1.647.301,90)
- Usa coordenadas X de pdfplumber para distinguir columna Débito/Crédito/Saldo
- Multi-hoja con continuaciones ("SALDO PAGINA ANTERIOR", "SALDO HOJA ANTERIOR")
- Consolidados al pie: SIRCREB y IIBB Tucumán para validación
"""
import re
from datetime import datetime
from collections import defaultdict


# ─── Tolerancia para agrupar palabras en la misma línea ─────────────────────
TOP_TOLERANCIA = 1   # pt; las tops del ICBC son exactas (ej: 330.06) 

PATRON_NUMERO = re.compile(r'^[\d.]+,\d{2}-?$')
PATRON_FECHA_MOV = re.compile(r'^\d{2}-\d{2}$')
PATRON_PERIODO = re.compile(r'PERIODO\s+\d{2}-\d{2}-(\d{4})')
PATRON_SALDO_ANT = re.compile(r'SALDO ULTIMO EXTRACTO AL.*?([\d.]+,\d{2})', re.IGNORECASE)
PATRON_SALDO_FINAL = re.compile(r'SALDO FINAL AL.*?([\d.]+,\d{2})', re.IGNORECASE)
PATRON_TITULAR = re.compile(r'A NOMBRE DE:\s*(.+)', re.IGNORECASE)


def _parsear_numero(texto):
    """Convierte '10.578,10-' o '10.578,10' a float (siempre positivo)."""
    s = str(texto).strip().rstrip('-').replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def _clasificar(concepto):
    """Clasifica el concepto ICBC en tipo de movimiento."""
    c = concepto.upper()

    # ── Gastos bancarios / impuestos (van a TIPOS_GASTOS, no se cruzan) ──────
    if 'SIRCREB' in c:
        return 'RET_SIRCREB'
    if 'IIBB TUCUMAN' in c or 'IIBB TUC' in c or 'RENTA FINAN-TUCUM' in c:
        return 'RET_IIBB_TUCUMAN'
    if 'ING BRUTOS PERCEP' in c or 'PERCEP. C.A.B.A' in c or 'PERCEPCION IIBB CABA' in c:
        return 'PERC_IIBB_CABA'
    if 'IMP S/CRED EN CTA' in c:
        return 'LEY25413_CREDITO'
    if 'IMP S/DEBITOS EN CTA' in c or 'IMP S/DEB EN CTA' in c:
        return 'LEY25413_DEBITO'
    if 'PERCEPCION IVA' in c or 'PERCEP IVA' in c:
        return 'PERC_IVA'
    if 'IMPUESTO AL VALOR AGREGADO' in c or (c.startswith('IVA') and 'TRANSFISC' in c):
        return 'IVA'
    if 'IMPUESTO DE SELLOS' in c:
        return 'IMP_SELLOS'
    if 'COM MPAY' in c or 'COMISION PAQUETE' in c or 'COMISION' in c:
        return 'COMISION'
    if 'INTERESES' in c:
        return 'INTERESES'
    # Retenciones IIBB sobre rentas financieras (FCI) - Córdoba
    if 'RENTA FINAN-CORDO' in c or 'RENTA FINAN-COR' in c:
        return 'COMISION'   # no hay tipo CORDOBA; se agrupa en gastos bancarios

    # ── Operativos (se cruzan con el sistema) ────────────────────────────────
    if 'DEB SUSCR FCI' in c or 'SUSCRIPCION FCI' in c:
        return 'FCI_SUSCRIPCION'
    if 'CRED RESC FCI' in c or 'CREDITO POR RESCATE FCI' in c or 'RESCATE FCI' in c:
        return 'FCI_RESCATE'
    if 'TRANS PAG PROV' in c or 'TRF.DATANET' in c or 'PAGO PROVEEDORES' in c:
        return 'TRANSFERENCIA'
    if 'TRANSF. E/BCOS' in c or 'TRANSFERENCIA PUSH' in c or 'TRANSFERENCIA INMEDIATA' in c:
        return 'TRANSFERENCIA'
    if 'TRANS DN MTITU' in c or 'DEBITO TRANSF CONNECTION' in c or 'DEB TRANSF CONNECTION' in c:
        return 'TRANSFERENCIA'
    if 'CREDITO INMEDIATO' in c or 'CREDITO TRANSF' in c:
        return 'TRANSFERENCIA'
    if 'IMPORTACIONES' in c:
        return 'TRANSFERENCIA'
    if 'PAGO METROGAS' in c or 'PAGO HSBC' in c or 'PAGO DE SERVICIOS' in c:
        return 'PAGO_SERVICIOS'
    if 'HABERES' in c or 'SUELDO' in c:
        return 'HABERES'
    return 'OTRO'


def parsear_pdf(ruta_pdf):
    """
    Lee un PDF del Banco ICBC y devuelve:
      movimientos   : lista de dicts {fecha, concepto, debito, credito, descripcion, tipo}
      saldo_anterior: float
      saldo_final   : float
      titular       : str

    Validación interna (verificar contra totales del pie del PDF):
      TOTAL SIRCREB   = suma de RET_SIRCREB
      TOTAL IIBB TUC  = suma de RET_IIBB_TUCUMAN (sólo R/RECAUDACION, no FCI)
      TOT.IMP.LEY COMP = suma LEY25413_DEBITO + LEY25413_CREDITO
    """
    import pdfplumber

    movimientos    = []
    saldo_anterior = 0.0
    saldo_final    = 0.0
    titular        = ''
    anio           = datetime.now().year   # fallback

    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ''
            words = pagina.extract_words()

            # ── Extraer año del período ──────────────────────────────────────
            m = PATRON_PERIODO.search(texto)
            if m:
                anio = int(m.group(1))

            # ── Titular ──────────────────────────────────────────────────────
            if not titular:
                m = PATRON_TITULAR.search(texto)
                if m:
                    titular = m.group(1).strip()

            # ── Saldo anterior ───────────────────────────────────────────────
            if saldo_anterior == 0.0:
                m = PATRON_SALDO_ANT.search(texto)
                if m:
                    saldo_anterior = _parsear_numero(m.group(1))

            # ── Saldo final (última página que lo tenga) ──────────────────────
            m = PATRON_SALDO_FINAL.search(texto)
            if m:
                saldo_final = _parsear_numero(m.group(1))

            # ── Detectar layout de columnas dinámicamente ────────────────────
            # El ICBC tiene dos layouts: páginas con logo (x más a la derecha)
            # y páginas de continuación. Buscamos los encabezados DEBITOS/CREDITOS/SALDOS/FECHA.
            x_fecha   = None
            x_debitos = None
            x_creditos = None
            x_saldos  = None
            for w in words:
                t = w['text'].upper()
                if t == 'FECHA'    and x_fecha    is None: x_fecha    = w['x0']
                if t == 'DEBITOS'  and x_debitos  is None: x_debitos  = w['x0']
                if t == 'CREDITOS' and x_creditos is None: x_creditos = w['x0']
                if t == 'SALDOS'   and x_saldos   is None: x_saldos   = w['x0']

            # Fallback a valores conocidos si no se encuentran los headers
            if x_fecha   is None: x_fecha   = 20.0
            if x_debitos is None: x_debitos = 310.0
            if x_creditos is None: x_creditos = 381.0
            if x_saldos  is None: x_saldos  = 473.0

            # Límites: débito hasta la mitad entre debitos y creditos, etc.
            x_max_debito  = (x_debitos + x_creditos) / 2
            x_max_credito = (x_creditos + x_saldos) / 2
            # Un número es fecha-columna si su x0 está cerca de x_fecha
            x_fecha_max   = x_fecha + 40   # DD-MM tiene ~35pt de ancho

            # ── Agrupar palabras por línea (top exacto redondeado a 1pt) ─────
            lineas = defaultdict(list)
            for w in words:
                key = round(w['top'])
                lineas[key].append(w)

            for top in sorted(lineas.keys()):
                ws = sorted(lineas[top], key=lambda w: w['x0'])
                if not ws:
                    continue

                # Primera palabra en la columna FECHA con formato DD-MM
                primera = ws[0]
                if not (PATRON_FECHA_MOV.match(primera['text'])
                        and primera['x0'] <= x_fecha_max):
                    continue

                fecha_str = primera['text']
                try:
                    dia, mes = int(fecha_str[:2]), int(fecha_str[3:])
                    fecha = datetime(anio, mes, dia)
                except ValueError:
                    continue

                # Separar números por columna (débito / crédito / saldo)
                debito  = 0.0
                credito = 0.0
                nums    = [(w['x0'], w['text']) for w in ws if PATRON_NUMERO.match(w['text'])]

                for x0, num_texto in nums:
                    valor = _parsear_numero(num_texto)
                    if x0 <= x_max_debito:
                        debito = valor
                    elif x0 <= x_max_credito:
                        credito = valor
                    # más allá de x_max_credito → saldo, se ignora

                if debito == 0.0 and credito == 0.0:
                    continue

                # Concepto: palabras no-número entre la fecha y el primer número
                palabras_concepto = []
                for w in ws[1:]:
                    if PATRON_NUMERO.match(w['text']):
                        break
                    palabras_concepto.append(w['text'])
                concepto = ' '.join(palabras_concepto).strip()

                if not concepto:
                    continue

                concepto_upper = concepto.upper()
                if any(x in concepto_upper for x in ('SALDO', 'TOTAL', 'CONTINUA')):
                    continue

                tipo = _clasificar(concepto)

                movimientos.append({
                    'fecha':       fecha,
                    'concepto':    concepto,
                    'debito':      round(debito, 2),
                    'credito':     round(credito, 2),
                    'descripcion': '',
                    'tipo':        tipo,
                })

    return {
        'movimientos':    movimientos,
        'saldo_anterior': saldo_anterior,
        'saldo_final':    saldo_final,
        'titular':        titular,
    }
