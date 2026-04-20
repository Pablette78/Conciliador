"""
Parser Banco Santander — extrae movimientos usando coordenadas X de pdfplumber.

Estructura de columnas del PDF (coordenadas X aproximadas):
  Fecha       : x ≈ 23
  Comprobante : x ≈ 65
  Movimiento  : x ≈ 115
  Débito      : x ≈ 340 – 420  (monto negativo / egreso)
  Crédito     : x ≈ 421 – 510  (monto positivo / ingreso)
  Saldo       : x ≈ 511 – 590

El texto plano mezcla las columnas, por eso usamos extract_words() con
coordenadas para clasificar cada monto en Débito, Crédito o Saldo.
"""
import re
from datetime import datetime
from .base import BaseParser
from ..models import Movimiento, DatosExtracto

# ── Límites de columna (X en puntos PDF) ──────────────────────────────────────
X_DEBITO_MIN  = 330
X_DEBITO_MAX  = 420
X_CREDITO_MIN = 421
X_CREDITO_MAX = 512
X_SALDO_MIN   = 513
X_SALDO_MAX   = 600

PAT_MONTO   = re.compile(r'^\$?-?[\d.]+,\d{2}$')
PAT_FECHA   = re.compile(r'^\d{2}/\d{2}/\d{2}$')
PAT_PAG     = re.compile(r'^\d+ - \d+$')


def _es_monto(texto: str) -> bool:
    return bool(PAT_MONTO.match(texto.replace(' ', '')))


def _limpiar_float(texto: str) -> float:
    """Convierte '$ 1.234.567,89' o '1.234.567,89' a float."""
    t = texto.replace('$', '').replace('.', '').replace(',', '.').strip()
    try:
        return abs(float(t))
    except ValueError:
        return 0.0


class SantanderParser(BaseParser):

    def parse(self, ruta_archivo: str) -> DatosExtracto:
        import pdfplumber

        movimientos      = []
        saldo_anterior   = 0.0
        saldo_final      = 0.0
        titular          = ""
        en_movimientos   = False
        fin_movimientos  = False

        # ── 1. Extraer TODAS las palabras de todas las páginas ─────────────────
        todas_palabras = []   # list de dict con keys: x0, top, text, page
        lineas_texto   = []   # para detección de titular y marcas de sección

        with pdfplumber.open(ruta_archivo) as pdf:
            for num_pag, pagina in enumerate(pdf.pages):
                texto = pagina.extract_text()
                if texto:
                    lineas_texto.extend(texto.split('\n'))
                words = pagina.extract_words(x_tolerance=3, y_tolerance=3)
                for w in words:
                    todas_palabras.append({
                        'x0'  : w['x0'],
                        'top' : w['top'],
                        'text': w['text'],
                        'page': num_pag,
                    })

        # ── 2. Detectar titular ────────────────────────────────────────────────
        for linea in lineas_texto[:20]:
            l = linea.upper().strip()
            if any(kw in l for kw in ('SRL', 'SAIC', 'S.A', 'S.A.S')) \
                    and 'BANCO' not in l and 'CUIT' not in l:
                titular = linea.strip()
                break

        # ── 2b. Detectar saldo final desde texto de portada ───────────────────
        # El PDF muestra "Saldo total en cuentas al DD/MM/AA" seguido de
        # "$N.NNN.NNN,NN" — pero a veces el PDF omite la coma: "$N.NNN.NNNN"
        # Regex permisivo: captura todo lo que sigue al $ hasta fin de token
        PAT_SALDO_PORTADA = re.compile(r'\$\s*([\d.,]+)')
        for i, linea in enumerate(lineas_texto[:15]):
            if 'Saldo total en cuentas' in linea or 'Saldo total' in linea:
                for j in range(i, min(i + 3, len(lineas_texto))):
                    m = PAT_SALDO_PORTADA.search(lineas_texto[j])
                    if m:
                        raw = m.group(1).strip()
                        try:
                            if ',' in raw:
                                # formato normal: 2.692.160,82
                                saldo_final = float(raw.replace('.', '').replace(',', '.'))
                            else:
                                # formato roto: 2.692.16082 → últimos 2 dígitos = centavos
                                digits = raw.replace('.', '')
                                saldo_final = float(digits[:-2] + '.' + digits[-2:])
                        except (ValueError, IndexError):
                            pass
                        break
                break

        # ── 3. Agrupar palabras por fila (top redondeado) ─────────────────────
        filas: dict[tuple, list] = {}
        for w in todas_palabras:
            key = (w['page'], round(w['top'] / 4) * 4)
            filas.setdefault(key, []).append(w)

        filas_ordenadas = sorted(filas.keys())

        # ── 4. Parsear fila a fila ─────────────────────────────────────────────
        mov_actual   = None
        fecha_pend   = None   # última fecha vista (se propaga hacia adelante y atrás)
        pendientes_sin_fecha: list = []  # movimientos que aún no tienen fecha
        saldo_actual = 0.0

        for key in filas_ordenadas:
            palabras = sorted(filas[key], key=lambda w: w['x0'])
            textos   = [w['text'] for w in palabras]
            linea    = ' '.join(textos)

            # ── Marcas de sección ─────────────────────────────────────────────
            if 'Saldo en cuenta' in linea:
                en_movimientos = True
                continue
            if 'Detalle impositivo' in linea or 'Cambio de comisiones' in linea:
                if mov_actual:
                    movimientos.append(mov_actual)
                    mov_actual = None
                fin_movimientos = True
                continue
            if not en_movimientos or fin_movimientos:
                continue

            # ── Ignorar encabezados y paginación ──────────────────────────────
            if PAT_PAG.match(linea.strip()):
                continue
            if 'Fecha' in linea and 'Comprobante' in linea:
                continue
            if 'Cuenta Corriente' in linea and ('CBU' in linea or 'Nº' in linea or 'N°' in linea):
                continue
            if 'Salvo error' in linea:
                continue

            # ── Clasificar palabras por columna ───────────────────────────────
            fecha_words  = [w for w in palabras if PAT_FECHA.match(w['text']) and w['x0'] < 60]
            comp_words   = [w for w in palabras if w['x0'] >= 60 and w['x0'] < 115
                            and not PAT_FECHA.match(w['text'])]
            desc_words   = [w for w in palabras if w['x0'] >= 115 and w['x0'] < X_DEBITO_MIN]
            debito_words = [w for w in palabras if X_DEBITO_MIN <= w['x0'] <= X_DEBITO_MAX and _es_monto(w['text'])]
            credito_words= [w for w in palabras if X_CREDITO_MIN <= w['x0'] <= X_CREDITO_MAX and _es_monto(w['text'])]
            saldo_words  = [w for w in palabras if w['x0'] >= X_SALDO_MIN and _es_monto(w['text'])]

            # ── Saldo Inicial ─────────────────────────────────────────────────
            if 'Saldo' in linea and 'Inicial' in linea:
                if saldo_words:
                    saldo_anterior = _limpiar_float(saldo_words[-1]['text'])
                    saldo_actual   = saldo_anterior
                continue

            # ── Saldo total (fin) ─────────────────────────────────────────────
            if 'Saldo total' in linea or 'Saldo Total' in linea:
                if saldo_words:
                    saldo_final = _limpiar_float(saldo_words[-1]['text'])
                continue

            # ── ¿Llegó una fecha en esta fila? ────────────────────────────────
            if fecha_words:
                try:
                    nueva_fecha = datetime.strptime(fecha_words[0]['text'], '%d/%m/%y')
                    fecha_pend  = nueva_fecha
                    # Si hay movimientos que estaban esperando fecha, asignársela
                    for m in pendientes_sin_fecha:
                        m.fecha = nueva_fecha
                    pendientes_sin_fecha.clear()
                except ValueError:
                    pass

            # ── ¿Hay un movimiento en esta fila? ──────────────────────────────
            tiene_monto = debito_words or credito_words

            if tiene_monto:
                # Guardar el movimiento anterior
                if mov_actual:
                    movimientos.append(mov_actual)
                    mov_actual = None

                # Descripción = comprobante + desc
                comprobante = ' '.join(w['text'] for w in comp_words)
                descripcion = ' '.join(w['text'] for w in desc_words)
                desc_full   = f"{comprobante} {descripcion}".strip()
                desc_full   = re.sub(r'\s{2,}', ' ', desc_full)

                # Monto y columna
                if debito_words:
                    monto     = _limpiar_float(debito_words[0]['text'])
                    es_debito = True
                else:
                    monto     = _limpiar_float(credito_words[0]['text'])
                    es_debito = False

                # Nuevo saldo
                if saldo_words:
                    saldo_actual = _limpiar_float(saldo_words[-1]['text'])

                tipo = self.clasificar_concepto(desc_full)

                # Fecha: la de esta misma fila tiene prioridad, sino la pendiente
                fecha_mov = fecha_pend  # puede ser None si no llegó ninguna aún

                mov_actual = Movimiento(
                    fecha     = fecha_mov,
                    concepto  = desc_full,
                    credito   = 0.0   if es_debito else monto,
                    debito    = monto if es_debito else 0.0,
                    tipo      = tipo,
                )
                # Si todavía no tiene fecha, lo encolamos para resolverla después
                if fecha_mov is None:
                    pendientes_sin_fecha.append(mov_actual)

            elif not tiene_monto and desc_words and mov_actual:
                # Línea de continuación de descripción (sin monto ni fecha propia)
                extra = ' '.join(w['text'] for w in desc_words).strip()
                if extra and len(extra) > 3:
                    mov_actual.concepto += ' ' + extra

        # Guardar último movimiento pendiente
        if mov_actual:
            movimientos.append(mov_actual)

        return DatosExtracto(
            banco          = "Banco Santander",
            titular        = titular,
            movimientos    = movimientos,
            saldo_anterior = saldo_anterior,
            saldo_final    = saldo_final,
        )
