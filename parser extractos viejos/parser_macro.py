"""
Parser para extractos PDF del Banco Macro Argentina
Cuenta Corriente - Empresas / PyMEs

NOTA FUSIÓN: Desde mediados de 2024, Banco Macro absorbió Itaú Argentina.
Los clientes ex-Itaú pueden recibir extractos con el formato antiguo de Itaú
hasta la migración completa. Este parser intenta manejar AMBOS formatos.

Formato típico Banco Macro (formato propio):
  Cabecera:
    BANCO MACRO S.A.
    E-RESUMEN / EXTRACTO DE CUENTA
    Razón Social: NOMBRE EMPRESA SA
    CUIT: 30-XXXXXXXX-X
    Cuenta Corriente N°: XXX-XXXXXXXX/X
    Período: DD/MM/AAAA al DD/MM/AAAA

  Saldo anterior:
    Saldo Anterior          <importe>

  Movimientos:
    FECHA     DESCRIPCION / CONCEPTO              DEBITOS      CREDITOS    SALDO
    DD/MM/AA  Texto libre ...                    1.234,56                 XX.XXX,XX
    DD/MM/AA  Texto libre ...                                 5.678,90    XX.XXX,XX

  Pie:
    Total Débitos:     XX.XXX,XX
    Total Créditos:    XX.XXX,XX
    Saldo Final:       XX.XXX,XX

Formato ex-Itaú Argentina (puede aparecer en clientes migrados):
  Cabecera similar pero logo ITAÚ o MACRO-ITAÚ
  Columnas: Fecha | Histórico | Descripción | Valor | Saldo
  Los débitos aparecen como negativos (-1.234,56) o en columna separada.

Gastos bancarios típicos Banco Macro:
  - RET.SIRCREB / RETENCION SIRCREB              → RET_SIRCREB
  - IMP.DB.CR.LEY 25413 DEB                      → LEY25413_DEBITO
  - IMP.DB.CR.LEY 25413 CRED                     → LEY25413_CREDITO
  - RETENCION IIBB TUCUMAN                       → RET_IIBB_TUCUMAN
  - PERCEPCION IIBB CABA / PERC.IIBB             → PERC_IIBB_CABA
  - COMISION MANTENIMIENTO CTA                   → COMISION
  - IVA S/COMISION / IVA                         → IVA
  - PERCEPCION IVA                               → PERC_IVA
  - IMP.SELLOS                                   → IMP_SELLOS
  - INTERESES / INT.DESCUBIERTO                  → INTERESES
  - DEV.IIBB                                     → DEV_IIBB

IMPORTANTE: Ajustar las regex según el PDF real.
El modo diagnóstico imprime los primeros 20 movimientos para verificar
que débitos y créditos se asignen correctamente.
"""

import re
import pdfplumber


# ---------------------------------------------------------------------------
# Mapeo de conceptos → tipos de gasto
# ---------------------------------------------------------------------------
GASTOS_BANCARIOS = [
    (re.compile(r'SIRCREB', re.I),                                     'RET_SIRCREB'),
    (re.compile(r'25413.*DEB|IMP\.?DB\.?CR.*DEB|LEY.*25413.*DEB', re.I), 'LEY25413_DEBITO'),
    (re.compile(r'25413.*CR[EÉ]D|IMP\.?DB\.?CR.*CR[EÉ]D', re.I),     'LEY25413_CREDITO'),
    (re.compile(r'IIBB.*TUCUM|TUCUM.*IIBB|RET.*TUCUM', re.I),         'RET_IIBB_TUCUMAN'),
    (re.compile(r'PERC.*IIBB|IIBB.*CABA|PERCEPCION.*IIBB|IIBB', re.I),'PERC_IIBB_CABA'),
    (re.compile(r'PERC.*IVA|PERCEPCION.*IVA', re.I),                   'PERC_IVA'),
    (re.compile(r'\bIVA\b', re.I),                                     'IVA'),
    (re.compile(r'SELLOS|IMP.*SELLOS', re.I),                          'IMP_SELLOS'),
    (re.compile(r'COMISI[OÓ]N|COM\.?\s*MANT|MANT.*CTA|CARGO.*MANT', re.I), 'COMISION'),
    (re.compile(r'INTER[EÉ]S(?:ES)?|INT\.?\s*DESC', re.I),            'INTERESES'),
    (re.compile(r'DEV.*IIBB|DEVOL.*IIBB', re.I),                      'DEV_IIBB'),
    (re.compile(r'DEV.*IMP.*DEB|DEVOL.*25413', re.I),                 'DEV_IMP_DEBITOS'),
]


def _clasificar_tipo(concepto: str) -> str:
    for patron, tipo in GASTOS_BANCARIOS:
        if patron.search(concepto):
            return tipo
    return 'OPERATIVO'


def _parsear_importe(texto: str) -> float:
    """Convierte importe argentino a float. Soporta negativos con signo '-'."""
    if not texto or not texto.strip():
        return 0.0
    t = texto.strip().replace(' ', '')
    negativo = t.startswith('-')
    t = t.lstrip('-')
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    else:
        t = t.replace(',', '')
    try:
        valor = float(t)
        return -valor if negativo else valor
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
# Detección de formato
# ---------------------------------------------------------------------------
def _detectar_formato(lineas: list) -> str:
    """
    Intenta detectar si el PDF es formato Macro clásico o ex-Itaú.
    Retorna 'macro' o 'itau'.
    """
    texto = ' '.join(lineas[:30]).upper()
    if 'ITAU' in texto or 'ITAÚ' in texto:
        return 'itau'
    return 'macro'


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------
def parsear_pdf(ruta: str) -> dict:
    """
    Lee el extracto PDF del Banco Macro Argentina y retorna:
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

    # --- Regex comunes ---
    RE_SALDO_ANT = re.compile(
        r'SALDO\s+ANTERIOR(?:\s+AL\s+\d{2}/\d{2}/\d{2,4})?[:\s]+([\d.,]+)', re.I
    )
    RE_SALDO_FIN = re.compile(
        r'SALDO\s+(?:FINAL|AL\s+\d{2}/\d{2}(?:/\d{2,4})?)[:\s]+([\d.,]+)', re.I
    )
    RE_TITULAR = re.compile(r'(?:TITULAR|RAZ[OÓ]N\s+SOCIAL)[:\s]+(.+)', re.I)

    # --- Regex formato Macro clásico ---
    # "DD/MM/AA  DESCRIPCION ...  [debito]  [credito]  [saldo]"
    RE_MOV_MACRO = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+'
        r'(.+?)\s+'
        r'([\d.,]+)?\s+'
        r'([\d.,]+)?\s+'
        r'([\d.,]+)?\s*$'
    )

    # --- Regex formato ex-Itaú ---
    # "DD/MM/AA  DD/MM/AA  DESCRIPCION ...  -importe  saldo"  (débitos con signo negativo)
    # o "DD/MM/AA  DD/MM/AA  DESCRIPCION ...  +importe  saldo"  (créditos)
    RE_MOV_ITAU = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+'
        r'(\d{2}/\d{2}/\d{2,4})\s+'   # fecha valor (ex-Itaú tiene dos fechas)
        r'(.+?)\s+'
        r'(-?[\d.,]+)\s+'              # importe con posible signo negativo
        r'(-?[\d.,]+)\s*$'             # saldo
    )

    with pdfplumber.open(ruta) as pdf:
        bloques = []
        for pagina in pdf.pages:
            txt = pagina.extract_text(x_tolerance=3, y_tolerance=3)
            if txt:
                bloques.append(txt)

    lineas = '\n'.join(bloques).splitlines()
    formato = _detectar_formato(lineas)

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

        if not en_movimientos:
            continue

        # --- Formato ex-Itaú (dos fechas, importe con signo) ---
        if formato == 'itau':
            m = RE_MOV_ITAU.match(ls)
            if m:
                fecha_op, _fecha_val, concepto, importe_str, _saldo = m.groups()
                concepto = concepto.strip()
                importe  = _parsear_importe(importe_str)
                # En ex-Itaú, negativo = débito, positivo = crédito
                debito  = abs(importe) if importe < 0 else 0.0
                credito = importe      if importe > 0 else 0.0
                tipo    = _clasificar_tipo(concepto)
                movimientos.append({
                    'fecha':       _parsear_fecha(fecha_op),
                    'concepto':    concepto,
                    'debito':      debito,
                    'credito':     credito,
                    'descripcion': concepto,
                    'tipo':        tipo,
                })
                continue

        # --- Formato Macro clásico (tres columnas numéricas) ---
        m = RE_MOV_MACRO.match(ls)
        if m:
            fecha_str, concepto, col_deb, col_cred, _saldo = m.groups()
            _agregar_movimiento(movimientos, fecha_str, concepto, col_deb, col_cred)
            continue

        # Fallback: si hay fecha + concepto + UN solo importe
        # Intentar inferir déb/cred por el saldo acumulado
        m = re.match(
            r'^(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+(-?[\d.,]+)\s*$', ls
        )
        if m:
            fecha_str, concepto, importe_str = m.groups()
            concepto = concepto.strip()
            importe  = _parsear_importe(importe_str)
            debito  = abs(importe) if importe < 0 else 0.0
            credito = importe      if importe > 0 else 0.0
            tipo    = _clasificar_tipo(concepto)
            movimientos.append({
                'fecha':       _parsear_fecha(fecha_str),
                'concepto':    concepto,
                'debito':      debito,
                'credito':     credito,
                'descripcion': concepto,
                'tipo':        tipo,
                '_ambiguo':    True,
            })

    return {
        'movimientos':    movimientos,
        'saldo_anterior': saldo_anterior,
        'saldo_final':    saldo_final,
        'titular':        titular,
        '_formato':       formato,
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
        print("Uso: python parser_macro.py <ruta_extracto.pdf>")
        sys.exit(1)

    resultado = parsear_pdf(sys.argv[1])

    print(f"Titular:        {resultado['titular']}")
    print(f"Formato PDF:    {resultado.get('_formato', 'desconocido')}")
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

    por_tipo = defaultdict(float)
    for m in resultado['movimientos']:
        if m['tipo'] != 'OPERATIVO':
            por_tipo[m['tipo']] += m['debito'] or m['credito']

    if por_tipo:
        print("Gastos bancarios detectados:")
        for tipo, monto in sorted(por_tipo.items()):
            print(f"  {tipo:<25} $ {monto:,.2f}")

    ambiguos = [m for m in resultado['movimientos'] if m.get('_ambiguo')]
    if ambiguos:
        print(f"\n⚠  {len(ambiguos)} movimiento(s) ambiguo(s) — revisar déb/cred manualmente.")

    print(f"\nPrimeros 20 movimientos (verificar que déb/cred sean correctos):")
    for mov in resultado['movimientos'][:20]:
        if mov['debito']:
            signo = f"DEB -{mov['debito']:>12,.2f}"
        else:
            signo = f"CRE +{mov['credito']:>12,.2f}"
        print(f"  {mov['fecha']}  {mov['concepto'][:38]:<38}  {signo}  [{mov['tipo']}]")
