import os
import re
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from collections import defaultdict

# ─── Estilos ───────────────────────────────────────────────────────────────────
BD = Border(left=Side(style='thin'), right=Side(style='thin'), 
            top=Side(style='thin'), bottom=Side(style='thin'))
TF = Font(name='Arial', bold=True, size=11)
DF = Font(name='Arial', size=11)
CA = Alignment(horizontal='center')
TB = PatternFill('solid', fgColor='D9E1F2') # Azul claro (Headers)
BB = PatternFill('solid', fgColor='FCE4D6') # Naranja (Saldos)
NB = PatternFill('solid', fgColor='F2F2F2') # Gris (Solo en...)
MB = PatternFill('solid', fgColor='C6EFCE') # Verde (Conciliado)
GB = PatternFill('solid', fgColor='FFC7CE') # Rojo (Diferencia)
MF = '#,##0.00'
DTF = 'DD/MM/YYYY'

def _h(ws, r, headers, fill=TB):
    for i, h in enumerate(headers):
        cl = ws.cell(row=r, column=i+1, value=h)
        cl.font = Font(name='Arial', bold=True, size=11)
        cl.alignment = CA
        if fill: cl.fill = fill
        cl.border = BD

def _sf(ws, r, cols, font=DF, fill=None):
    for c in range(1, cols + 1):
        cl = ws.cell(row=r, column=c)
        cl.font = font
        if fill: cl.fill = fill
        cl.border = BD

def _titulo(ws, r, texto, mc=7):
    ws.cell(row=r, column=1, value=texto).font = Font(name='Arial', bold=True, size=12, color='2F5496')

# ============================================================
# HOJA 0: RESUMEN
# ============================================================
def _crear_resumen(wb, resultado, datos_banco, mes_anio, movimientos_sistema=None):
    ws = wb.active
    ws.title = "Resumen"

    ws.merge_cells('A1:D1')
    ws['A1'] = f'RESUMEN CONCILIACIÓN - {mes_anio}'
    ws['A1'].font = Font(name='Arial', bold=True, size=16, color='2F5496')
    ws['A2'] = datos_banco.titular
    ws['A2'].font = Font(name='Arial', size=10, color='666666')

    r = 4
    v = resultado.validación_saldos
    items = [
        ('Saldo Anterior s/ Banco', v.get('saldo_anterior', 0)),
        ('(+) Total Créditos', v.get('total_creditos', 0)),
        ('(-) Total Débitos', v.get('total_debitos', 0)),
        ('(=) Saldo Final Calculado', v.get('saldo_final_calculado', 0)),
        ('Saldo Final s/ Banco (Extracto)', v.get('saldo_final_extracto', 0)),
    ]
    for desc, val in items:
        ws.cell(row=r, column=1, value=desc).font = Font(name='Arial', bold=True, size=11)
        ws.cell(row=r, column=1).border = BD
        ws.cell(row=r, column=2, value=val).number_format = MF
        ws.cell(row=r, column=2).font = Font(name='Arial', bold=True, size=11)
        ws.cell(row=r, column=2).border = BD
        ws.cell(row=r, column=1).fill = BB
        ws.cell(row=r, column=2).fill = BB
        r += 1

    if not v.get('coincide', True):
        ws.cell(row=r, column=1, value="⚠ DIFERENCIA EN SALDO FINAL").font = Font(name='Arial', bold=True, color='FF0000')
        ws.cell(row=r, column=2, value=v.get('saldo_final_extracto', 0) - v.get('saldo_final_calculado', 0)).number_format = MF
    r += 2

    ws.cell(row=r, column=1, value='CONCILIACIÓN').font = Font(name='Arial', bold=True, size=12, color='2F5496')
    r += 1

    total_conc = len(resultado.conciliados)
    con_diff = sum(1 for c in resultado.conciliados if c.diferencia != 0)
    
    stats = [
        ('Movimientos conciliados', total_conc),
        ('Con diferencia de monto', con_diff),
        ('Solo en banco (pendientes)', len(resultado.solo_banco)),
        ('Solo en sistema (pendientes)', len(resultado.solo_sistema)),
    ]

    for desc, val in stats:
        ws.cell(row=r, column=1, value=desc).font = DF
        ws.cell(row=r, column=1).border = BD
        ws.cell(row=r, column=2, value=val)
        ws.cell(row=r, column=2).font = DF
        ws.cell(row=r, column=2).border = BD
        r += 1

    r += 1
    ws.cell(row=r, column=1, value='GASTOS BANCARIOS E IMPUESTOS').font = Font(name='Arial', bold=True, size=12, color='2F5496')
    r += 1

    gran_total = 0
    for cat, datos in resultado.gastos_por_categoria.items():
        nombre = cat
        ws.cell(row=r, column=1, value=nombre).font = DF
        ws.cell(row=r, column=1).border = BD
        ws.cell(row=r, column=2, value=datos['total']).number_format = MF
        ws.cell(row=r, column=2).font = DF
        ws.cell(row=r, column=2).border = BD
        ws.cell(row=r, column=3, value=f"{len(datos['items'])} movimientos").font = Font(name='Arial', size=9, color='888888')
        gran_total += datos['total']
        r += 1

    ws.cell(row=r, column=1, value='TOTAL GASTOS').font = Font(name='Arial', bold=True, size=11)
    ws.cell(row=r, column=1).fill = TB
    ws.cell(row=r, column=1).border = BD
    ws.cell(row=r, column=2, value=gran_total).number_format = MF
    ws.cell(row=r, column=2).font = Font(name='Arial', bold=True, size=11)
    ws.cell(row=r, column=2).fill = TB
    ws.cell(row=r, column=2).border = BD

    # PRUEBA ÁCIDA
    r += 2
    ws.cell(row=r, column=1, value='PRUEBA ÁCIDA (Totales de Control)').font = Font(name='Arial', bold=True, size=11, color='2F5496')
    r += 1
    _h(ws, r, ['Concepto', 'Debito / Egreso', 'Credito / Ingreso', 'Check'])
    r += 1
    
    t_b_conc_deb = sum(c.banco.debito for c in resultado.conciliados)
    t_b_conc_cre = sum(c.banco.credito for c in resultado.conciliados)
    t_b_solo_deb = sum(m.debito for m in resultado.solo_banco)
    t_b_solo_cre = sum(m.credito for m in resultado.solo_banco)
    t_b_gast_deb = sum(sum(m.debito for m in cat['items']) for cat in resultado.gastos_por_categoria.values())
    t_b_gast_cre = sum(sum(m.credito for m in cat['items']) for cat in resultado.gastos_por_categoria.values())
    
    t_b_orig_deb = sum(m.debito for m in datos_banco.movimientos)
    t_b_orig_cre = sum(m.credito for m in datos_banco.movimientos)
    
    t_s_conc_deb = sum(c.sistema.debito for c in resultado.conciliados)
    t_s_conc_cre = sum(c.sistema.credito for c in resultado.conciliados)
    t_s_solo_deb = sum(m.debito for m in resultado.solo_sistema)
    t_s_solo_cre = sum(m.credito for m in resultado.solo_sistema)
    
    if movimientos_sistema:
        t_s_orig_deb = sum(m.debito for m in movimientos_sistema)
        t_s_orig_cre = sum(m.credito for m in movimientos_sistema)
    else:
        t_s_orig_deb = t_s_conc_deb + t_s_solo_deb
        t_s_orig_cre = t_s_conc_cre + t_s_solo_cre

    filas_control = [
        ('1. Banco Conciliado', t_b_conc_deb, t_b_conc_cre, 'OK' if round(t_b_conc_deb+t_b_conc_cre,2)>0 else ''),
        ('2. Solo en Banco (Operativos)', t_b_solo_deb, t_b_solo_cre, ''),
        ('3. Gastos e Impuestos (Banco)', t_b_gast_deb, t_b_gast_cre, ''),
        ('TOTAL EXPLICADO (1+2+3)', t_b_conc_deb + t_b_solo_deb + t_b_gast_deb, t_b_conc_cre + t_b_solo_cre + t_b_gast_cre, 'BANCO'),
        ('TOTAL ORIGINAL EXTRACTO', t_b_orig_deb, t_b_orig_cre, 'BANCO'),
        ('', None, None, ''),
        ('I. Sistema Conciliado', t_s_conc_deb, t_s_conc_cre, ''),
        ('II. Solo en Sistema', t_s_solo_deb, t_s_solo_cre, ''),
        ('TOTAL EXPLICADO (I+II)', t_s_conc_deb + t_s_solo_deb, t_s_conc_cre + t_s_solo_cre, 'SISTEMA'),
        ('TOTAL ORIGINAL MAYOR', t_s_orig_deb, t_s_orig_cre, 'SISTEMA')
    ]
    
    for desc, d, c, t_c in filas_control:
        if desc == '': r += 1; continue
        ws.cell(row=r, column=1, value=desc).font = DF
        ws.cell(row=r, column=1).border = BD
        if d is not None: 
            ws.cell(row=r, column=2, value=d).number_format = MF
            ws.cell(row=r, column=2).border = BD
        if c is not None: 
            ws.cell(row=r, column=3, value=c).number_format = MF
            ws.cell(row=r, column=3).border = BD
        
        if 'TOTAL' in desc:
            ws.cell(row=r, column=1).font = TF
            ws.cell(row=r, column=2).font = TF
            ws.cell(row=r, column=3).font = TF
            if 'ORIGINAL' in desc: 
                ws.cell(row=r, column=1).font = Font(name='Arial', bold=True, color='0070C0')
                target_deb = t_b_conc_deb + t_b_solo_deb + t_b_gast_deb if t_c == 'BANCO' else t_s_conc_deb + t_s_solo_deb
                target_cre = t_b_conc_cre + t_b_solo_cre + t_b_gast_cre if t_c == 'BANCO' else t_s_conc_cre + t_s_solo_cre
                orig_deb = t_b_orig_deb if t_c == 'BANCO' else t_s_orig_deb
                orig_cre = t_b_orig_cre if t_c == 'BANCO' else t_s_orig_cre
                if round(target_deb, 2) == round(orig_deb, 2) and round(target_cre, 2) == round(orig_cre, 2):
                    ws.cell(row=r, column=4, value='✅ EXCELENTE').font = Font(name='Arial', bold=True, color='00B050')
                else:
                    ws.cell(row=r, column=4, value='❌ DIFERENCIA').font = Font(name='Arial', bold=True, color='C00000')
        r += 1

    ws.column_dimensions['A'].width = 40
    ws.column_dimensions['B'].width = 22
    ws.column_dimensions['C'].width = 20

# ============================================================
# HOJA 1: AUDITORÍA BANCO
# ============================================================
def _crear_auditoria_banco(wb, datos_banco, mes_anio):
    ws = wb.create_sheet("1. Auditoría Banco")
    ws.merge_cells('A1:F1')
    ws['A1'] = f'AUDITORÍA: MOVIMIENTOS DETECTADOS EN BANCO - {mes_anio}'
    ws['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
    _h(ws, 3, ['Fecha', 'Concepto', 'Tipo Clasificación', 'Débito', 'Crédito', 'Saldo'])
    r = 4
    for m in datos_banco.movimientos:
        ws.cell(row=r, column=1, value=m.fecha).number_format = DTF
        ws.cell(row=r, column=2, value=m.concepto)
        ws.cell(row=r, column=3, value=m.tipo)
        if m.debito: ws.cell(row=r, column=4, value=m.debito).number_format = MF
        if m.credito: ws.cell(row=r, column=5, value=m.credito).number_format = MF
        if m.saldo is not None: ws.cell(row=r, column=6, value=m.saldo).number_format = MF
        _sf(ws, r, 6, DF)
        r += 1
    for c, w in [('A', 14), ('B', 50), ('C', 20), ('D', 16), ('E', 16), ('F', 16)]:
        ws.column_dimensions[c].width = w

# ============================================================
# HOJA 2: AUDITORÍA SISTEMA
# ============================================================
def _crear_auditoria_sistema(wb, movimientos_sistema, mes_anio):
    ws = wb.create_sheet("2. Auditoría Sistema")
    ws.merge_cells('A1:F1')
    ws['A1'] = f'AUDITORÍA: MOVIMIENTOS DETECTADOS EN SISTEMA - {mes_anio}'
    ws['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
    _h(ws, 3, ['Fecha', 'Documento/Ref', 'Concepto Original', 'Detalle', 'Debe', 'Haber'])
    r = 4
    for m in movimientos_sistema:
        ws.cell(row=r, column=1, value=m.fecha).number_format = DTF
        ws.cell(row=r, column=2, value=m.referencia) 
        ws.cell(row=r, column=3, value=m.concepto)    
        ws.cell(row=r, column=4, value=m.descripcion) 
        if m.debito: ws.cell(row=r, column=5, value=m.debito).number_format = MF
        if m.credito: ws.cell(row=r, column=6, value=m.credito).number_format = MF
        _sf(ws, r, 6, DF)
        r += 1
    for c, w in [('A', 14), ('B', 28), ('C', 32), ('D', 32), ('E', 16), ('F', 16)]:
        ws.column_dimensions[c].width = w

# ============================================================
# HOJA 3: DETALLE DE IMPUESTOS
# ============================================================
def _crear_detalle_impuestos(wb, resultado, mes_anio):
    ws = wb.create_sheet("3. Detalle Impuestos")
    ws.merge_cells('A1:D1')
    ws['A1'] = f'DETALLE DIARIO DE IMPUESTOS Y GASTOS BANCARIOS - {mes_anio}'
    ws['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
    r = 3
    for cat, datos in sorted(resultado.gastos_por_categoria.items(), key=lambda x: str(x[0])):
        if len(datos['items']) == 0: continue
        ws.cell(row=r, column=1, value=str(cat).replace('_', ' ')).font = Font(name='Arial', bold=True, size=12, color='FFFFFF')
        ws.cell(row=r, column=1).fill = PatternFill('solid', fgColor='4472C4')
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        r += 1
        _h(ws, r, ['Fecha', 'Concepto Banco', 'Referencia / Detalle', 'Monto'])
        r += 1
        start_r = r
        for m in sorted(datos['items'], key=lambda x: x.fecha):
            ws.cell(row=r, column=1, value=m.fecha).number_format = DTF
            ws.cell(row=r, column=2, value=m.concepto[:80]) 
            ws.cell(row=r, column=3, value=m.descripcion[:80])
            ws.cell(row=r, column=4, value=m.debito or m.credito).number_format = MF
            _sf(ws, r, 4, DF)
            r += 1
        ws.cell(row=r, column=3, value='TOTAL ' + str(cat)).font = TF
        ws.cell(row=r, column=3).fill = TB
        ws.cell(row=r, column=4, value=f'=SUM(D{start_r}:D{r-1})').number_format = MF
        ws.cell(row=r, column=4).font = TF; ws.cell(row=r, column=4).fill = TB
        _sf(ws, r, 4)
        ws.row_dimensions.group(start_r, r-1, hidden=True)
        r += 2
    for c, w in [('A', 14), ('B', 50), ('C', 45), ('D', 20)]:
        ws.column_dimensions[c].width = w

# ============================================================
# HOJA 4: CONCILIACIÓN
# ============================================================
def _crear_conciliacion(wb, resultado, datos_banco, mes_anio):
    ws = wb.create_sheet("4. Conciliación")
    ws.merge_cells('A1:K1')
    ws['A1'] = f'CONCILIACIÓN BANCARIA - {mes_anio}'
    ws['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
    r = 4
    _titulo(ws, r, '1. CRUCE DE MOVIMIENTOS (Banco vs Sistema)', mc=11)
    r += 1
    _h(ws, r, ['Fecha Banco', 'Monto Banco', 'Conc. Banco', 'Fecha Sist.', 'Monto Sist.', 'Ref. Sist.', 'Dif. $', 'Dif. Días', 'Nivel Cierre', 'Estado', 'Alerta/Nota'])
    r += 1
    for item in resultado.conciliados:
        b, s = item.banco, item.sistema
        ws.cell(row=r, column=1, value=b.fecha).number_format = DTF
        ws.cell(row=r, column=2, value=b.monto).number_format = MF
        ws.cell(row=r, column=3, value=b.concepto)
        ws.cell(row=r, column=4, value=s.fecha).number_format = DTF
        ws.cell(row=r, column=5, value=s.monto).number_format = MF
        ws.cell(row=r, column=6, value=s.referencia or s.concepto)
        ws.cell(row=r, column=7, value=item.diferencia).number_format = MF
        ws.cell(row=r, column=8, value=item.diferencia_dias)
        ws.cell(row=r, column=9, value=item.nivel)
        ws.cell(row=r, column=10, value=item.estado)
        if item.alerta:
            ws.cell(row=r, column=11, value=item.alerta).font = Font(name='Arial', color='C00000', bold=True)
        
        fill = MB if item.estado == 'CONCILIADO' else GB
        _sf(ws, r, 11, DF, fill=fill)
        r += 1
    if resultado.solo_banco:
        r += 1
        ws.cell(row=r, column=1, value=f'SOLO EN BANCO ({len(resultado.solo_banco)} movimientos sin match)').font = Font(name='Arial', bold=True, size=11, color='C00000')
        r += 1; _h(ws, r, ['Fecha', 'Concepto', 'Tipo Automático', 'Crédito', 'Débito', '', '', '']); r += 1
        start_sb = r
        for m in resultado.solo_banco:
            ws.cell(row=r, column=1, value=m.fecha).number_format = DTF
            ws.cell(row=r, column=2, value=m.concepto)
            ws.cell(row=r, column=3, value=m.tipo)
            if m.credito: ws.cell(row=r, column=4, value=m.credito).number_format = MF
            if m.debito: ws.cell(row=r, column=5, value=m.debito).number_format = MF
            _sf(ws, r, 5, DF, NB)
            r += 1
        ws.cell(row=r, column=1, value='TOTAL SOLO EN BANCO').font = TF; ws.cell(row=r, column=1).fill = NB
        ws.cell(row=r, column=4, value=f'=SUM(D{start_sb}:D{r-1})').number_format = MF; ws.cell(row=r, column=4).font = TF; ws.cell(row=r, column=4).fill = NB
        ws.cell(row=r, column=5, value=f'=SUM(E{start_sb}:E{r-1})').number_format = MF; ws.cell(row=r, column=5).font = TF; ws.cell(row=r, column=5).fill = NB
        r += 1

    if resultado.solo_sistema:
        r += 1
        ws.cell(row=r, column=1, value=f'SOLO EN SISTEMA ({len(resultado.solo_sistema)} movimientos sin match)').font = Font(name='Arial', bold=True, size=11, color='C00000')
        r += 1; _h(ws, r, ['Fecha', 'Ref.', 'Concepto', 'Debe', 'Haber', '', '', '']); r += 1
        for m in resultado.solo_sistema:
            ws.cell(row=r, column=1, value=m.fecha).number_format = DTF
            ws.cell(row=r, column=2, value=m.referencia)
            ws.cell(row=r, column=3, value=m.concepto)
            if m.debito: ws.cell(row=r, column=4, value=m.debito).number_format = MF
            if m.credito: ws.cell(row=r, column=5, value=m.credito).number_format = MF
            _sf(ws, r, 5, DF, NB)
            r += 1

    for c, w in [('A', 14), ('B', 16), ('C', 30), ('D', 14), ('E', 16), ('F', 25), ('G', 12), ('H', 10), ('I', 15), ('J', 20), ('K', 30)]:
        ws.column_dimensions[c].width = w

# ============================================================
# HOJA 5: CONCEPTOS AGRUPADOS
# ============================================================
def _crear_conceptos_agrupados(wb, datos_banco, mes_anio):
    ws = wb.create_sheet("5. Conceptos Agrupados")
    ws.merge_cells('A1:E1')
    ws['A1'] = f'AGRUPACIÓN TOTAL POR CONCEPTOS BANCARIOS - {mes_anio}'
    ws['A1'].font = Font(name='Arial', bold=True, size=14, color='2F5496')
    agrup = defaultdict(lambda: {'creditos': 0.0, 'debitos': 0.0, 'cantidad': 0})
    for m in datos_banco.movimientos:
        llave = (m.tipo, m.concepto.strip().upper())
        agrup[llave]['creditos'] += m.credito
        agrup[llave]['debitos'] += m.debito
        agrup[llave]['cantidad'] += 1
    r = 3
    _h(ws, r, ['Tipo Clasificación', 'Concepto Exacto', 'Cant.', 'Total Débitos', 'Total Créditos'])
    r += 1
    items = sorted(agrup.items(), key=lambda x: (x[0][0], -x[1]['debitos']))
    for (tipo, concepto), vals in items:
        ws.cell(row=r, column=1, value=tipo)
        ws.cell(row=r, column=2, value=concepto)
        ws.cell(row=r, column=3, value=vals['cantidad']).alignment = CA
        ws.cell(row=r, column=4, value=vals['debitos']).number_format = MF
        ws.cell(row=r, column=5, value=vals['creditos']).number_format = MF
        _sf(ws, r, 5, DF)
        r += 1
    for c, w in [('A', 22), ('B', 50), ('C', 8), ('D', 18), ('E', 18)]:
        ws.column_dimensions[c].width = w

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def generar_excel(resultado, datos_banco, ruta_salida, mes_anio="", movimientos_sistema=None):
    wb = Workbook()
    _crear_resumen(wb, resultado, datos_banco, mes_anio, movimientos_sistema)
    _crear_auditoria_banco(wb, datos_banco, mes_anio)
    if movimientos_sistema:
        _crear_auditoria_sistema(wb, movimientos_sistema, mes_anio)
    _crear_detalle_impuestos(wb, resultado, mes_anio)
    _crear_conciliacion(wb, resultado, datos_banco, mes_anio)
    _crear_conceptos_agrupados(wb, datos_banco, mes_anio)
    wb.save(ruta_salida)
    return ruta_salida
