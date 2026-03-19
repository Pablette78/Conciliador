"""
Parser para extractos PDF del BBVA Argentina (ex Banco Francés)
Cuenta Corriente - Empresas

Formato típico del PDF:
  Cabecera:
    BBVA
    EXTRACTO DE CUENTA CORRIENTE
    Titular: NOMBRE EMPRESA SA
    CUIT: 30-XXXXXXXX-X
    Número de cuenta: XXX-XXXXXXX/X   (o CBU)
    Período: DD/MM/AAAA al DD/MM/AAAA

  Línea de saldo anterior (puede estar en tabla o línea separada):
    "Saldo anterior"                  <importe>

  Movimientos:
    FECHA     FECHA VALOR   CONCEPTO / DESCRIPCION       DÉBITOS      CRÉDITOS
    DD/MM/AA  DD/MM/AA      Texto libre ...              1.234,56
    DD/MM/AA  DD/MM/AA      Texto libre ...                           5.678,90

  Totales al pie:
    Total Débitos:   XX.XXX,XX
    Total Créditos:  XX.XXX,XX
    Saldo al DD/MM/AAAA:  XX.XXX,XX

Gastos bancarios típicos BBVA:
  - IMP DEB CRED LEY 25413 / IMP.DB.CR.LEY25413  → LEY25413_DEBITO / LEY25413_CREDITO
  - RETENCION SIRCREB / RET SIRCREB               → RET_SIRCREB
  - RETENCION IIBB TUCUMAN                        → RET_IIBB_TUCUMAN
  - PERCEPCION IIBB CABA / PERC IIBB              → PERC_IIBB_CABA
  - COMISION MANTENIMIENTO / COM.MANT             → COMISION
  - IVA S/COMISION / IVA                          → IVA
  - PERCEPCION IVA                                → PERC_IVA
  - IMP SELLOS                                    → IMP_SELLOS
  - INTERESES                                     → INTERESES

IMPORTANTE: Ajustar las regex según el PDF real.
BBVA a veces incluye DOS fechas por fila (operación + valor). Este parser
usa la primera (fecha de operación). Si el PDF real usa otra disposición,
ajustar RE_MOVIMIENTO.
"""

import re
import pdfplumber


# ---------------------------------------------------------------------------
# Mapeo de conceptos bancarios → tipos de gasto
# ---------------------------------------------------------------------------
GASTOS_BANCARIOS = [
    # SIRCREB
    (re.compile(r'SIRCREB', re.I),                               'RET_SIRCREB'),
    # Ley 25413 débito
    (re.compile(r'25413.*DEB|IMP.*DEB.*CRED.*25413|IMP\.?DB\.?CR.*DEB', re.I), 'LEY25413_DEBITO'),
    # Ley 25413 crédito
    (re.compile(r'25413.*CR[EÉ]D|IMP\.?DB\.?CR.*CR[EÉ]D', re.I), 'LEY25413_CREDITO'),
    # IIBB Tucumán
    (re.compile(r'IIBB.*TUCUM|TUCUM.*IIBB|RET.*TUCUM', re.I),   'RET_IIBB_TUCUMAN'),
    # IIBB CABA / genérico
    (re.compile(r'PERC.*IIBB|IIBB.*CABA|IIBB.*BS.*AS|PERCEPCION.*IIBB|IIBB', re.I), 'PERC_IIBB_CABA'),
    # Percepción IVA
    (re.compile(r'PERC.*IVA|PERCEPCION.*IVA', re.I),             'PERC_IVA'),
    # IVA genérico (después de PERC_IVA para no pisarlo)
    (re.compile(r'\bIVA\b', re.I),                               'IVA'),
    # Sellos
    (re.compile(r'SELLOS|IMP.*SELLOS', re.I),                    'IMP_SELLOS'),
    # Comisiones / mantenimiento
    (re.compile(r'COMISI[OÓ]N|COM\.?\s*MANT|MANT\.?\s*CTA|CARGO.*MANT', re.I), 'COMISION'),
    # Intereses
    (re.compile(r'INTER[EÉ]S(?:ES)?|INT\.?\s+DESC', re.I),      'INTERESES'),
    # Devolución IIBB
    (re.compile(r'DEV.*IIBB|DEVOL.*IIBB', re.I),                 'DEV_IIBB'),
    # Devolución imp débitos
    (re.compile(r'DEV.*IMP.*DEB|DEVOL.*25413', re.I),            'DEV_IMP_DEBITOS'),
]


def _clasificar_tipo(concepto: str) -> str:
    """Devuelve el tipo de gasto bancario o 'OPERATIVO'."""
    for patron, tipo in GASTOS_BANCARIOS:
        if patron.search(concepto):
            return tipo
    return 'OPERATIVO'


def _parsear_importe(texto: str) -> float:
    """Convierte '1.234.567,89' a float."""
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
    """Normaliza DD/MM/AA o DD/MM/AAAA → DD/MM/AAAA."""
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
    Lee el extracto PDF del BBVA Argentina y retorna:
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

    # --- Expresiones regulares ---

    # Movimiento con dos fechas (operación + valor):
    # "DD/MM/AA  DD/MM/AA  CONCEPTO ...  [debito]  [credito]"
    RE_MOV_2FECHAS = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+'    # fecha operación
        r'(\d{2}/\d{2}/\d{2,4})\s+'     # fecha valor
        r'(.+?)\s+'                       # concepto (lazy)
        r'([\d.,]+)?\s*'                  # débito (opcional)
        r'([\d.,]+)?\s*$'                 # crédito (opcional)
    )

    # Movimiento con una sola fecha:
    # "DD/MM/AA  CONCEPTO ...  [debito]  [credito]"
    RE_MOV_1FECHA = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+'    # fecha
        r'(.+?)\s+'                       # concepto (lazy)
        r'([\d.,]+)?\s*'                  # débito (opcional)
        r'([\d.,]+)?\s*$'                 # crédito (opcional)
    )

    RE_SALDO_ANT = re.compile(r'SALDO\s+ANTERIOR[:\s]+([\d.,]+)', re.I)
    RE_SALDO_FIN = re.compile(
        r'SALDO\s+(?:FINAL|AL\s+\d{2}/\d{2}(?:/\d{2,4})?)[:\s]+([\d.,]+)', re.I
    )
    RE_TITULAR = re.compile(r'(?:TITULAR|RAZ[OÓ]N\s+SOCIAL)[:\s]+(.+)', re.I)

    # BBVA a veces pone totales como:
    # "Total Débitos    1.234,56    Total Créditos    5.678,90"
    RE_TOTALES = re.compile(
        r'Total\s+D[EÉ]bitos?\s+([\d.,]+)\s+Total\s+Cr[EÉ]ditos?\s+([\d.,]+)', re.I
    )

    with pdfplumber.open(ruta) as pdf:
        bloques = []
        for pagina in pdf.pages:
            txt = pagina.extract_text(x_tolerance=3, y_tolerance=3)
            if txt:
                bloques.append(txt)

    texto_completo = '\n'.join(bloques)
    lineas = texto_completo.splitlines()

    en_movimientos = False  # flag: ya pasamos la cabecera

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

        # Totales en una línea
        m = RE_TOTALES.search(ls)
        if m:
            continue  # solo validación, no los guardamos

        # Movimiento con 2 fechas
        m = RE_MOV_2FECHAS.match(ls)
        if m and en_movimientos:
            fecha_op, _fecha_val, concepto, col_deb, col_cred = m.groups()
            _agregar_movimiento(movimientos, fecha_op, concepto, col_deb, col_cred)
            continue

        # Movimiento con 1 fecha
        m = RE_MOV_1FECHA.match(ls)
        if m and en_movimientos:
            fecha_op, concepto, col_deb, col_cred = m.groups()
            _agregar_movimiento(movimientos, fecha_op, concepto, col_deb, col_cred)
            continue

    return {
        'movimientos':    movimientos,
        'saldo_anterior': saldo_anterior,
        'saldo_final':    saldo_final,
        'titular':        titular,
    }


def _agregar_movimiento(movimientos, fecha_str, concepto, col_deb, col_cred):
    """Helper que construye y agrega un movimiento a la lista."""
    concepto = concepto.strip()
    if not concepto:
        return

    debito  = _parsear_importe(col_deb)
    credito = _parsear_importe(col_cred)

    # Si ambas columnas tienen valor, BBVA a veces pone el saldo en la segunda.
    # Heurística: si debito > 0 y credito > 0, revisar cuál es saldo.
    # Por ahora los dejamos como están; ajustar según PDF real.

    tipo = _clasificar_tipo(concepto)

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

    if len(sys.argv) < 2:
        print("Uso: python parser_bbva.py <ruta_extracto.pdf>")
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

    from collections import defaultdict
    por_tipo = defaultdict(float)
    for m in resultado['movimientos']:
        if m['tipo'] != 'OPERATIVO':
            por_tipo[m['tipo']] += m['debito'] or m['credito']

    if por_tipo:
        print("Gastos bancarios detectados:")
        for tipo, monto in sorted(por_tipo.items()):
            print(f"  {tipo:<25} $ {monto:,.2f}")
    else:
        print("Sin gastos bancarios detectados.")

    print()
    print("Primeros 10 movimientos:")
    for mov in resultado['movimientos'][:10]:
        signo = f"-{mov['debito']:>12,.2f}" if mov['debito'] else f"+{mov['credito']:>12,.2f}"
        print(f"  {mov['fecha']}  {mov['concepto'][:40]:<40}  {signo}  [{mov['tipo']}]")
