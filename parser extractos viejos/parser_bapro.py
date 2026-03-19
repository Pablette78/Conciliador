"""
Parser para extractos PDF del Banco de la Provincia de Buenos Aires (BAPRO)
Cuenta Corriente - Empresas / PyMEs

Formato típico del PDF:
  Cabecera:
    BANCO DE LA PROVINCIA DE BUENOS AIRES
    EXTRACTO DE CUENTA CORRIENTE
    Titular / Razón Social: NOMBRE EMPRESA SA
    CUIT: 30-XXXXXXXX-X
    Sucursal: XXX   Cuenta N°: XXXXXXXXX   Tipo: CC $
    Período: DD/MM/AAAA al DD/MM/AAAA

  Línea de saldo anterior:
    SALDO ANTERIOR AL DD/MM/AAAA          <importe>
    (a veces aparece como primera fila de la tabla de movimientos)

  Movimientos (tabla):
    FECHA       DESCRIPCION                     DEBITOS      CREDITOS     SALDO
    DD/MM/AA    Texto libre ...                 1.234,56                  XX.XXX,XX
    DD/MM/AA    Texto libre ...                              5.678,90     XX.XXX,XX

  Bloque de totales al pie (MUY ÚTIL para validación):
    TOTAL DEBITOS:        XX.XXX,XX
    TOTAL CREDITOS:       XX.XXX,XX
    SALDO FINAL:          XX.XXX,XX

  Bloque consolidado de retenciones (presente en muchos extractos BAPRO):
    RETENCIONES SIRCREB:  XX.XXX,XX
    IMP. LEY 25413 DEB:   XX.XXX,XX
    IMP. LEY 25413 CRED:  XX.XXX,XX

Gastos bancarios típicos BAPRO:
  - RET.SIRCREB / RETENCION SIRCREB          → RET_SIRCREB
  - IMP.DB.CR.LEY 25413 DEB                  → LEY25413_DEBITO
  - IMP.DB.CR.LEY 25413 CRED                 → LEY25413_CREDITO
  - RET.IIBB TUCUMAN / RETENCION IIBB TUC    → RET_IIBB_TUCUMAN
  - PERC.IIBB CABA / PERCEPCION IIBB         → PERC_IIBB_CABA
  - COMISION / COM.MANT.CTA.CTE              → COMISION
  - IVA S/COMISION / IVA S/COM               → IVA
  - PERCEPCION IVA                           → PERC_IVA
  - IMP.SELLOS / IMPUESTO SELLOS             → IMP_SELLOS
  - INTERESES / INT.DESC.                    → INTERESES
  - DEV.IIBB                                 → DEV_IIBB
  - DEV.IMP.DEBITOS                          → DEV_IMP_DEBITOS

IMPORTANTE: Ajustar las regex según el PDF real.
BAPRO frecuentemente incluye un bloque consolidado al pie con los totales de
SIRCREB y Ley 25413. Usar esos valores para validar el parser.
"""

import re
import pdfplumber


# ---------------------------------------------------------------------------
# Mapeo de conceptos → tipos de gasto
# ---------------------------------------------------------------------------
GASTOS_BANCARIOS = [
    (re.compile(r'SIRCREB', re.I),                                   'RET_SIRCREB'),
    (re.compile(r'25413.*DEB|IMP\.?DB\.?CR.*DEB|LEY.*25413.*DEB', re.I), 'LEY25413_DEBITO'),
    (re.compile(r'25413.*CR[EÉ]D|IMP\.?DB\.?CR.*CR[EÉ]D', re.I),   'LEY25413_CREDITO'),
    (re.compile(r'IIBB.*TUCUM|TUCUM.*IIBB|RET.*TUCUM', re.I),       'RET_IIBB_TUCUMAN'),
    (re.compile(r'PERC.*IIBB|IIBB.*CABA|PERCEPCION.*IIBB|IIBB', re.I), 'PERC_IIBB_CABA'),
    (re.compile(r'PERC.*IVA|PERCEPCION.*IVA', re.I),                 'PERC_IVA'),
    (re.compile(r'\bIVA\b', re.I),                                   'IVA'),
    (re.compile(r'SELLOS|IMP.*SELLOS', re.I),                        'IMP_SELLOS'),
    (re.compile(r'COMISI[OÓ]N|COM\.?\s*MANT|MANT.*CTA|CARGO.*MANT', re.I), 'COMISION'),
    (re.compile(r'INTER[EÉ]S(?:ES)?|INT\.?\s*DESC', re.I),          'INTERESES'),
    (re.compile(r'DEV.*IIBB|DEVOL.*IIBB', re.I),                    'DEV_IIBB'),
    (re.compile(r'DEV.*IMP.*DEB|DEVOL.*25413', re.I),               'DEV_IMP_DEBITOS'),
]


def _clasificar_tipo(concepto: str) -> str:
    for patron, tipo in GASTOS_BANCARIOS:
        if patron.search(concepto):
            return tipo
    return 'OPERATIVO'


def _parsear_importe(texto: str) -> float:
    if not texto or not texto.strip():
        return 0.0
    t = texto.strip().replace(' ', '')
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    else:
        t = t.replace(',', '')
    try:
        return float(t)
    except ValueError:
        return 0.0


def _parsear_fecha(texto: str) -> str:
    t = texto.strip()
    m = re.match(r'(\d{2})/(\d{2})/(\d{2,4})', t)
    if not m:
        return t
    d, mes, a = m.groups()
    if len(a) == 2:
        a = '20' + a
    return f'{d}/{mes}/{a}'


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------
def parsear_pdf(ruta: str) -> dict:
    """
    Lee el extracto PDF del BAPRO y retorna:
    {
        'movimientos':    list[dict],
        'saldo_anterior': float,
        'saldo_final':    float,
        'titular':        str,
    }
    """

    movimientos = []
    saldo_anterior = 0.0
    saldo_final = 0.0
    titular = ''

    # Regex de movimiento principal:
    # "DD/MM/AA  DESCRIPCION ...  [debito]  [credito]  [saldo]"
    # BAPRO generalmente tiene saldo acumulado por fila.
    RE_MOVIMIENTO = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+'   # fecha
        r'(.+?)\s+'                      # concepto
        r'([\d.,]+)?\s+'                 # débito (puede estar vacío)
        r'([\d.,]+)?\s+'                 # crédito (puede estar vacío)
        r'([\d.,]+)?\s*$'               # saldo acumulado
    )

    # Variante con solo 2 columnas numéricas al final (sin saldo por fila)
    RE_MOV_SIMPLE = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+'
        r'(.+?)\s+'
        r'([\d.,]+)\s*$'                # un solo importe al final
    )

    RE_SALDO_ANT = re.compile(r'SALDO\s+ANTERIOR(?:\s+AL\s+\d{2}/\d{2}/\d{2,4})?[:\s]+([\d.,]+)', re.I)
    RE_SALDO_FIN = re.compile(r'SALDO\s+(?:FINAL|AL\s+\d{2}/\d{2}(?:/\d{2,4})?)[:\s]+([\d.,]+)', re.I)
    RE_TITULAR   = re.compile(r'(?:TITULAR|RAZ[OÓ]N\s+SOCIAL)[:\s]+(.+)', re.I)

    # Totales de validación al pie
    RE_TOT_DEB  = re.compile(r'TOTAL\s+D[EÉ]BITOS?[:\s]+([\d.,]+)', re.I)
    RE_TOT_CRED = re.compile(r'TOTAL\s+CR[EÉ]DITOS?[:\s]+([\d.,]+)', re.I)

    # Bloque consolidado SIRCREB / Ley 25413 (para validación)
    RE_TOT_SIRCREB = re.compile(r'(?:TOTAL\s+)?(?:RET(?:ENCIONES?)?\s+)?SIRCREB[:\s]+([\d.,]+)', re.I)
    RE_TOT_L25_DEB = re.compile(r'(?:TOTAL\s+)?IMP\.?\s*(?:LEY\s*)?25413\s*DEB[:\s]+([\d.,]+)', re.I)
    RE_TOT_L25_CRE = re.compile(r'(?:TOTAL\s+)?IMP\.?\s*(?:LEY\s*)?25413\s*CR[EÉ]D[:\s]+([\d.,]+)', re.I)

    # Totales de validación (guardados para diagnóstico)
    totales_pdf = {}

    with pdfplumber.open(ruta) as pdf:
        bloques = []
        for pagina in pdf.pages:
            txt = pagina.extract_text(x_tolerance=3, y_tolerance=3)
            if txt:
                bloques.append(txt)

    lineas = '\n'.join(bloques).splitlines()

    en_movimientos = False

    for linea in lineas:
        ls = linea.strip()
        if not ls:
            continue

        # Titular
        m = RE_TITULAR.search(ls)
        if m and not titular:
            titular = m.group(1).strip()
            continue

        # Saldo anterior
        m = RE_SALDO_ANT.search(ls)
        if m:
            saldo_anterior = _parsear_importe(m.group(1))
            en_movimientos = True
            continue

        # Saldo final
        m = RE_SALDO_FIN.search(ls)
        if m:
            saldo_final = _parsear_importe(m.group(1))
            continue

        # Totales de validación (no los guardamos como movimientos)
        m = RE_TOT_DEB.search(ls)
        if m:
            totales_pdf['total_debitos'] = _parsear_importe(m.group(1))
            continue

        m = RE_TOT_CRED.search(ls)
        if m:
            totales_pdf['total_creditos'] = _parsear_importe(m.group(1))
            continue

        m = RE_TOT_SIRCREB.search(ls)
        if m:
            totales_pdf['sircreb'] = _parsear_importe(m.group(1))
            continue

        m = RE_TOT_L25_DEB.search(ls)
        if m:
            totales_pdf['ley25413_deb'] = _parsear_importe(m.group(1))
            continue

        m = RE_TOT_L25_CRE.search(ls)
        if m:
            totales_pdf['ley25413_cred'] = _parsear_importe(m.group(1))
            continue

        if not en_movimientos:
            continue

        # Movimiento con 3 columnas numéricas (deb / cred / saldo)
        m = RE_MOVIMIENTO.match(ls)
        if m:
            fecha_str, concepto, col_deb, col_cred, _saldo = m.groups()
            _agregar_movimiento(movimientos, fecha_str, concepto, col_deb, col_cred)
            continue

        # Movimiento con un solo importe — necesitamos inferir si es débito o crédito.
        # Heurística: comparar con saldo anterior + movimientos anteriores.
        # Por defecto lo dejamos en crédito si no podemos determinarlo;
        # esto deberá ajustarse con el PDF real.
        m = RE_MOV_SIMPLE.match(ls)
        if m:
            fecha_str, concepto, importe_str = m.groups()
            concepto = concepto.strip()
            importe = _parsear_importe(importe_str)
            tipo = _clasificar_tipo(concepto)
            movimientos.append({
                'fecha':       _parsear_fecha(fecha_str),
                'concepto':    concepto,
                'debito':      0.0,
                'credito':     importe,
                'descripcion': concepto,
                'tipo':        tipo,
                '_ambiguo':    True,   # marcar para revisión manual
            })

    return {
        'movimientos':    movimientos,
        'saldo_anterior': saldo_anterior,
        'saldo_final':    saldo_final,
        'titular':        titular,
        '_totales_pdf':   totales_pdf,   # para diagnóstico
    }


def _agregar_movimiento(movimientos, fecha_str, concepto, col_deb, col_cred):
    concepto = concepto.strip()
    if not concepto:
        return
    debito  = _parsear_importe(col_deb)
    credito = _parsear_importe(col_cred)
    tipo    = _clasificar_tipo(concepto)
    movimientos.append({
        'fecha':       _parsear_fecha(fecha_str),
        'concepto':    concepto,
        'debito':      debito,
        'credito':     credito,
        'descripcion': concepto,
        'tipo':        tipo,
    })


# ---------------------------------------------------------------------------
# Diagnóstico / test rápido
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    from collections import defaultdict

    if len(sys.argv) < 2:
        print("Uso: python parser_bapro.py <ruta_extracto.pdf>")
        sys.exit(1)

    resultado = parsear_pdf(sys.argv[1])

    print(f"Titular:        {resultado['titular']}")
    print(f"Saldo anterior: $ {resultado['saldo_anterior']:,.2f}")
    print(f"Saldo final:    $ {resultado['saldo_final']:,.2f}")
    print(f"Movimientos:    {len(resultado['movimientos'])}")
    print()

    total_deb = sum(m['debito']  for m in resultado['movimientos'])
    total_cre = sum(m['credito'] for m in resultado['movimientos'])
    saldo_calc = resultado['saldo_anterior'] - total_deb + total_cre
    print(f"Total débitos:  $ {total_deb:,.2f}")
    print(f"Total créditos: $ {total_cre:,.2f}")
    print(f"Saldo calculado:$ {saldo_calc:,.2f}  (esperado: $ {resultado['saldo_final']:,.2f})")
    diferencia = abs(saldo_calc - resultado['saldo_final'])
    print(f"Diferencia:     $ {diferencia:,.2f}  {'✓ OK' if diferencia < 1 else '✗ REVISAR PARSER'}")
    print()

    # Validación contra bloque consolidado del PDF
    totales = resultado.get('_totales_pdf', {})
    if totales:
        print("Validación contra consolidado del PDF:")
        if 'total_debitos' in totales:
            dif = abs(total_deb - totales['total_debitos'])
            print(f"  Débitos:   calculado={total_deb:,.2f}  PDF={totales['total_debitos']:,.2f}  "
                  f"{'✓' if dif < 1 else '✗ DIFERENCIA=' + f'{dif:,.2f}'}")
        if 'total_creditos' in totales:
            dif = abs(total_cre - totales['total_creditos'])
            print(f"  Créditos:  calculado={total_cre:,.2f}  PDF={totales['total_creditos']:,.2f}  "
                  f"{'✓' if dif < 1 else '✗ DIFERENCIA=' + f'{dif:,.2f}'}")

        calc_sircreb = sum(m['debito'] or m['credito']
                           for m in resultado['movimientos'] if m['tipo'] == 'RET_SIRCREB')
        if 'sircreb' in totales:
            dif = abs(calc_sircreb - totales['sircreb'])
            print(f"  SIRCREB:   calculado={calc_sircreb:,.2f}  PDF={totales['sircreb']:,.2f}  "
                  f"{'✓' if dif < 1 else '✗ DIFERENCIA=' + f'{dif:,.2f}'}")

        calc_l25d = sum(m['debito']
                        for m in resultado['movimientos'] if m['tipo'] == 'LEY25413_DEBITO')
        if 'ley25413_deb' in totales:
            dif = abs(calc_l25d - totales['ley25413_deb'])
            print(f"  Ley25413D: calculado={calc_l25d:,.2f}  PDF={totales['ley25413_deb']:,.2f}  "
                  f"{'✓' if dif < 1 else '✗ DIFERENCIA=' + f'{dif:,.2f}'}")
        print()

    # Resumen por tipo
    por_tipo = defaultdict(float)
    for m in resultado['movimientos']:
        if m['tipo'] != 'OPERATIVO':
            por_tipo[m['tipo']] += m['debito'] or m['credito']

    if por_tipo:
        print("Gastos bancarios detectados:")
        for tipo, monto in sorted(por_tipo.items()):
            print(f"  {tipo:<25} $ {monto:,.2f}")

    # Advertencia movimientos ambiguos
    ambiguos = [m for m in resultado['movimientos'] if m.get('_ambiguo')]
    if ambiguos:
        print(f"\n⚠  {len(ambiguos)} movimiento(s) con importe ambiguo (un solo valor). Revisar manualmente.")

    print("\nPrimeros 10 movimientos:")
    for mov in resultado['movimientos'][:10]:
        signo = f"-{mov['debito']:>12,.2f}" if mov['debito'] else f"+{mov['credito']:>12,.2f}"
        print(f"  {mov['fecha']}  {mov['concepto'][:40]:<40}  {signo}  [{mov['tipo']}]")
