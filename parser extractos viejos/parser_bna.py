"""
Parser para extractos PDF del Banco de la Nación Argentina (BNA)
Cuenta Corriente - Empresas / PyMEs

Formato típico del PDF:
  Cabecera:
    BANCO DE LA NACION ARGENTINA
    Razón Social: NOMBRE EMPRESA SA
    CUIT: 30-XXXXXXXX-X
    Cuenta Corriente N°: XXX-XXXXXXX/X
    Período: DD/MM/AAAA al DD/MM/AAAA

  Línea de saldo anterior:
    "SALDO ANTERIOR"    <importe>

  Movimientos (tabla):
    FECHA       DESCRIPCION / CONCEPTO          DEBITOS      CREDITOS     SALDO
    DD/MM/AA    Texto libre ...                 1.234,56                  XX.XXX,XX
    DD/MM/AA    Texto libre ...                              5.678,90     XX.XXX,XX

  Totales al pie:
    TOTAL DEBITOS:   XX.XXX,XX
    TOTAL CREDITOS:  XX.XXX,XX
    SALDO FINAL:     XX.XXX,XX

Gastos bancarios típicos BNA:
  - IMP.DB.CR.LEY 25413 DEB  →  LEY25413_DEBITO
  - IMP.DB.CR.LEY 25413 CRED →  LEY25413_CREDITO
  - RET.SIRCREB / SIRCREB     →  RET_SIRCREB
  - COMISION / COMISIONES      →  COMISION
  - IVA S/COMISION / IVA       →  IVA
  - IMP.SELLOS                 →  IMP_SELLOS
  - INTERESES                  →  INTERESES
  - PERC.IIBB / IIBB           →  PERC_IIBB_CABA  (ajustar según jurisdicción)
  - RET.IIBB TUCUMAN           →  RET_IIBB_TUCUMAN

IMPORTANTE: Ajustar las regex según el PDF real.
Verificar siempre los totales SIRCREB y Ley 25413 contra el consolidado del PDF.
"""

import re
import pdfplumber


# ---------------------------------------------------------------------------
# Mapeo de conceptos bancarios → tipos de gasto
# ---------------------------------------------------------------------------
GASTOS_BANCARIOS = [
    # SIRCREB
    (re.compile(r'SIRCREB', re.I),                          'RET_SIRCREB'),
    # Ley 25413 débito
    (re.compile(r'25413.*DEB|IMP.*DEB.*CRED.*LEY|IMP\.DB.*DEB', re.I), 'LEY25413_DEBITO'),
    # Ley 25413 crédito
    (re.compile(r'25413.*CRED|IMP\.DB.*CR', re.I),          'LEY25413_CREDITO'),
    # IIBB Tucumán
    (re.compile(r'IIBB.*TUCUM|TUCUM.*IIBB|RET.*TUCUM', re.I), 'RET_IIBB_TUCUMAN'),
    # IIBB CABA / Bs As / genérico
    (re.compile(r'PERC.*IIBB|IIBB.*CABA|IIBB.*BS.*AS|IIBB', re.I), 'PERC_IIBB_CABA'),
    # Percepción IVA
    (re.compile(r'PERC.*IVA|PERCEPCION.*IVA', re.I),        'PERC_IVA'),
    # IVA sobre comisión
    (re.compile(r'IVA\s+S/|IVA\s+SOBRE|^IVA$', re.I),      'IVA'),
    # Impuesto de Sellos
    (re.compile(r'SELLOS|IMP.*SELLOS', re.I),               'IMP_SELLOS'),
    # Comisiones
    (re.compile(r'COMISI[OÓ]N|COMISIONES|MANT.*CUENTA|CARGO.*MANT', re.I), 'COMISION'),
    # Intereses
    (re.compile(r'INTER[EÉ]S|INTERESES|INT\.?\s+DESC', re.I), 'INTERESES'),
    # Devolución IIBB
    (re.compile(r'DEV.*IIBB|DEVOL.*IIBB', re.I),            'DEV_IIBB'),
    # Devolución imp débitos
    (re.compile(r'DEV.*IMP.*DEB|DEVOL.*25413', re.I),       'DEV_IMP_DEBITOS'),
]


def _clasificar_tipo(concepto: str) -> str:
    """Devuelve el tipo de gasto bancario o 'OPERATIVO'."""
    for patron, tipo in GASTOS_BANCARIOS:
        if patron.search(concepto):
            return tipo
    return 'OPERATIVO'


def _parsear_importe(texto: str) -> float:
    """Convierte '1.234.567,89' o '1234567.89' a float."""
    if not texto or not texto.strip():
        return 0.0
    t = texto.strip().replace(' ', '')
    # Formato argentino: punto=miles, coma=decimal
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
    Lee el extracto PDF del BNA y retorna:
    {
        'movimientos':   list[dict],   # ver estructura abajo
        'saldo_anterior': float,
        'saldo_final':    float,
        'titular':        str,
    }

    Cada movimiento:
    {
        'fecha':       str,    # DD/MM/AAAA
        'concepto':    str,    # descripción original del banco
        'debito':      float,  # 0.0 si no aplica
        'credito':     float,  # 0.0 si no aplica
        'descripcion': str,    # igual a concepto (para compatibilidad)
        'tipo':        str,    # OPERATIVO | RET_SIRCREB | LEY25413_DEBITO | ...
    }
    """

    movimientos = []
    saldo_anterior = 0.0
    saldo_final = 0.0
    titular = ''

    # Regex para detectar una línea de movimiento.
    # BNA típicamente: "DD/MM/AA  DESCRIPCION ...  [débito]  [crédito]  saldo"
    # Las columnas numéricas pueden estar vacías (solo hay débito O crédito).
    RE_MOVIMIENTO = re.compile(
        r'^(\d{2}/\d{2}/\d{2,4})\s+'   # fecha
        r'(.+?)\s+'                      # descripción (lazy)
        r'([\d.,]+|-)\s+'               # débito o guión
        r'([\d.,]+|-)?\s*'              # crédito (opcional)
        r'([\d.,]+)?$'                  # saldo (opcional, puede estar en col aparte)
    )

    # Regex para líneas de saldo anterior / saldo final
    RE_SALDO_ANT = re.compile(r'SALDO\s+ANTERIOR[:\s]+([\d.,]+)', re.I)
    RE_SALDO_FIN = re.compile(r'SALDO\s+(?:FINAL|AL\s+\d{2}/\d{2})[:\s]+([\d.,]+)', re.I)
    RE_TITULAR   = re.compile(r'(?:RAZ[OÓ]N\s+SOCIAL|TITULAR)[:\s]+(.+)', re.I)

    # Regex alternativos para saldo anterior cuando está en tabla
    RE_SALDO_ANT2 = re.compile(r'SALDO\s+ANTERIOR', re.I)

    with pdfplumber.open(ruta) as pdf:
        texto_completo = []
        for pagina in pdf.pages:
            # Extraer texto con tolerancia para columnas
            texto = pagina.extract_text(x_tolerance=3, y_tolerance=3)
            if texto:
                texto_completo.append(texto)

        lineas = '\n'.join(texto_completo).splitlines()

    fecha_actual = None

    for i, linea in enumerate(lineas):
        linea_strip = linea.strip()
        if not linea_strip:
            continue

        # --- Titular ---
        m = RE_TITULAR.search(linea_strip)
        if m and not titular:
            titular = m.group(1).strip()
            continue

        # --- Saldo anterior ---
        m = RE_SALDO_ANT.search(linea_strip)
        if m:
            saldo_anterior = _parsear_importe(m.group(1))
            continue

        # --- Saldo final ---
        m = RE_SALDO_FIN.search(linea_strip)
        if m:
            saldo_final = _parsear_importe(m.group(1))
            continue

        # --- Línea de movimiento ---
        m = RE_MOVIMIENTO.match(linea_strip)
        if m:
            fecha_str, concepto, col_deb, col_cred, _ = m.groups()
            fecha_actual = _parsear_fecha(fecha_str)
            concepto = concepto.strip()

            debito  = _parsear_importe(col_deb)  if col_deb  and col_deb  != '-' else 0.0
            credito = _parsear_importe(col_cred) if col_cred and col_cred != '-' else 0.0

            tipo = _clasificar_tipo(concepto)

            movimientos.append({
                'fecha':       fecha_actual,
                'concepto':    concepto,
                'debito':      debito,
                'credito':     credito,
                'descripcion': concepto,
                'tipo':        tipo,
            })

    # Si no encontró saldo final por regex, intentar deducirlo del último movimiento
    # (algunos PDFs no lo muestran en línea separada)
    if saldo_final == 0.0 and movimientos:
        # No calcular: dejar que el conciliador lo determine.
        pass

    return {
        'movimientos':    movimientos,
        'saldo_anterior': saldo_anterior,
        'saldo_final':    saldo_final,
        'titular':        titular,
    }


# ---------------------------------------------------------------------------
# Diagnóstico / test rápido
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys, json

    if len(sys.argv) < 2:
        print("Uso: python parser_bna.py <ruta_extracto.pdf>")
        sys.exit(1)

    resultado = parsear_pdf(sys.argv[1])

    print(f"Titular:        {resultado['titular']}")
    print(f"Saldo anterior: $ {resultado['saldo_anterior']:,.2f}")
    print(f"Saldo final:    $ {resultado['saldo_final']:,.2f}")
    print(f"Movimientos:    {len(resultado['movimientos'])}")
    print()

    # Validación básica
    total_deb = sum(m['debito']  for m in resultado['movimientos'])
    total_cre = sum(m['credito'] for m in resultado['movimientos'])
    saldo_calc = resultado['saldo_anterior'] - total_deb + total_cre
    print(f"Total débitos:  $ {total_deb:,.2f}")
    print(f"Total créditos: $ {total_cre:,.2f}")
    print(f"Saldo calculado:$ {saldo_calc:,.2f}  (esperado: $ {resultado['saldo_final']:,.2f})")
    diferencia = abs(saldo_calc - resultado['saldo_final'])
    print(f"Diferencia:     $ {diferencia:,.2f}  {'✓ OK' if diferencia < 1 else '✗ REVISAR PARSER'}")
    print()

    # Resumen gastos bancarios
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
