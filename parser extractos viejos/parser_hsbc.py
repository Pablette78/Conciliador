"""
Parser para extractos PDF del HSBC Argentina
Cuenta Corriente - Empresas

Formato típico:
  Cabecera:
    HSBC BANK ARGENTINA S.A.
    ESTADO DE CUENTA / ACCOUNT STATEMENT
    Titular / Account Name: NOMBRE EMPRESA SA
    CUIT: 30-XXXXXXXX-X
    Cuenta N° / Account No: XXXXXXXXXX
    Período: DD/MM/AAAA al DD/MM/AAAA

  Saldo anterior:
    Opening Balance / Saldo Anterior     <importe>

  Movimientos (tabla):
    DATE        DESCRIPTION                    DEBIT        CREDIT       BALANCE
    DD/MM/AA    Texto libre ...               1.234,56                  XX.XXX,XX
    DD/MM/AA    Texto libre ...                             5.678,90    XX.XXX,XX

  Pie:
    Closing Balance / Saldo Final:    XX.XXX,XX

Notas:
  - HSBC puede incluir encabezados bilingües (inglés/español)
  - Los gastos aparecen como: RETENC.SIRCREB, IMP.DB/CR LEY25413,
    COMISION ADMINISTRACION, IVA S/COMISION, PERC.IIBB, IMP.SELLOS
  - Algunos extractos HSBC usan punto como separador decimal (formato inglés):
    "1,234.56" — el parser intenta detectar el formato automáticamente.
"""

import re
import pdfplumber


GASTOS_BANCARIOS = [
    (re.compile(r'SIRCREB', re.I),                                      'RET_SIRCREB'),
    (re.compile(r'25413.*DEB|IMP\.?DB.*DEB|LEY.*25413.*DEB', re.I),    'LEY25413_DEBITO'),
    (re.compile(r'25413.*CR[EÉ]D|IMP\.?DB.*CR[EÉ]D', re.I),           'LEY25413_CREDITO'),
    (re.compile(r'IIBB.*TUCUM|TUCUM.*IIBB|RET.*TUCUM', re.I),          'RET_IIBB_TUCUMAN'),
    (re.compile(r'PERC.*IIBB|IIBB.*CABA|PERCEPCION.*IIBB|IIBB', re.I), 'PERC_IIBB_CABA'),
    (re.compile(r'PERC.*IVA|PERCEPCION.*IVA', re.I),                    'PERC_IVA'),
    (re.compile(r'\bIVA\b', re.I),                                      'IVA'),
    (re.compile(r'SELLOS|IMP.*SELLOS|STAMP', re.I),                     'IMP_SELLOS'),
    (re.compile(r'COMISI[OÓ]N|COMMISSION|ADMIN.*FEE|MANT.*CTA', re.I), 'COMISION'),
    (re.compile(r'INTER[EÉ]S(?:ES)?|INTEREST', re.I),                  'INTERESES'),
    (re.compile(r'DEV.*IIBB|DEVOL.*IIBB', re.I),                       'DEV_IIBB'),
    (re.compile(r'DEV.*IMP.*DEB|DEVOL.*25413', re.I),                  'DEV_IMP_DEBITOS'),
]


def _clasificar_tipo(concepto):
    for patron, tipo in GASTOS_BANCARIOS:
        if patron.search(concepto):
            return tipo
    return 'OPERATIVO'


def _parsear_importe(texto):
    if not texto or not texto.strip():
        return 0.0
    t = texto.strip().replace(' ', '')
    negativo = t.startswith('-')
    t = t.lstrip('-')
    # Detectar formato: si tiene coma y punto, determinar cuál es decimal
    if ',' in t and '.' in t:
        # "1.234,56" → argentino; "1,234.56" → anglosajón
        if t.index(',') > t.index('.'):
            # último separador es coma → formato argentino
            t = t.replace('.', '').replace(',', '.')
        else:
            # último separador es punto → formato anglosajón
            t = t.replace(',', '')
    elif ',' in t:
        t = t.replace('.', '').replace(',', '.')
    try:
        v = float(t)
        return -v if negativo else v
    except ValueError:
        return 0.0


def _parsear_fecha(texto):
    t = texto.strip()
    m = re.match(r'(\d{2})/(\d{2})/(\d{2,4})', t)
    if not m:
        return t
    d, mes, a = m.groups()
    if len(a) == 2:
        a = '20' + a
    return f'{d}/{mes}/{a}'


def parsear_pdf(ruta: str) -> dict:
    movimientos = []
    saldo_anterior = 0.0
    saldo_final = 0.0
    titular = ''

    RE_SALDO_ANT = re.compile(
        r'(?:OPENING\s+BALANCE|SALDO\s+ANTERIOR)(?:\s+AL\s+\d{2}/\d{2}/\d{2,4})?[:\s]+([\d.,]+)', re.I
    )
    RE_SALDO_FIN = re.compile(
        r'(?:CLOSING\s+BALANCE|SALDO\s+FINAL|SALDO\s+AL\s+\d{2}/\d{2})[:\s]+([\d.,]+)', re.I
    )
    RE_TITULAR = re.compile(
        r'(?:TITULAR|ACCOUNT\s+NAME|RAZ[OÓ]N\s+SOCIAL)[:\s]+(.+)', re.I
    )
    RE_MOV = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+([\d.,]+)?\s+([\d.,]+)?\s+([\d.,]+)?\s*$'
    )

    with pdfplumber.open(ruta) as pdf:
        bloques = [p.extract_text(x_tolerance=3, y_tolerance=3) for p in pdf.pages]

    lineas = '\n'.join(b for b in bloques if b).splitlines()
    en_movimientos = False

    for linea in lineas:
        ls = linea.strip()
        if not ls:
            continue
        m = RE_TITULAR.search(ls)
        if m and not titular:
            titular = m.group(1).strip()
            continue
        m = RE_SALDO_ANT.search(ls)
        if m:
            saldo_anterior = _parsear_importe(m.group(1))
            en_movimientos = True
            continue
        m = RE_SALDO_FIN.search(ls)
        if m:
            saldo_final = _parsear_importe(m.group(1))
            continue
        if not en_movimientos:
            continue
        m = RE_MOV.match(ls)
        if m:
            fecha_str, concepto, c1, c2, c3 = m.groups()
            # Con 3 cols numéricas: deb / cred / saldo
            debito  = _parsear_importe(c1)
            credito = _parsear_importe(c2)
            tipo    = _clasificar_tipo(concepto.strip())
            movimientos.append({
                'fecha': _parsear_fecha(fecha_str), 'concepto': concepto.strip(),
                'debito': debito, 'credito': credito,
                'descripcion': concepto.strip(), 'tipo': tipo,
            })

    return {'movimientos': movimientos, 'saldo_anterior': saldo_anterior,
            'saldo_final': saldo_final, 'titular': titular}


if __name__ == '__main__':
    import sys
    from collections import defaultdict
    if len(sys.argv) < 2:
        print("Uso: python parser_hsbc.py <extracto.pdf>")
        sys.exit(1)
    r = parsear_pdf(sys.argv[1])
    print(f"Titular: {r['titular']}")
    print(f"Saldo anterior: $ {r['saldo_anterior']:,.2f}")
    print(f"Saldo final:    $ {r['saldo_final']:,.2f}")
    print(f"Movimientos:    {len(r['movimientos'])}")
    td = sum(m['debito'] for m in r['movimientos'])
    tc = sum(m['credito'] for m in r['movimientos'])
    sc = r['saldo_anterior'] - td + tc
    dif = abs(sc - r['saldo_final'])
    print(f"Diferencia:     $ {dif:,.2f}  {'✓ OK' if dif < 1 else '✗ REVISAR'}")
    pt = defaultdict(float)
    for m in r['movimientos']:
        if m['tipo'] != 'OPERATIVO':
            pt[m['tipo']] += m['debito'] or m['credito']
    for t, v in sorted(pt.items()):
        print(f"  {t:<25} $ {v:,.2f}")
