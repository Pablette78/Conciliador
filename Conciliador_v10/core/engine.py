from datetime import timedelta
from typing import List, Dict
from .models import Movimiento, ItemConciliado, ResultadoConciliacion, DatosExtracto

class MotorConciliacion:
    def __init__(self):
        self.niveles = [
            {'nombre': 'EXACTO', 'tol_monto': 0.0, 'tol_dias': 0},
            {'nombre': 'FUERTE', 'tol_monto': 10.0, 'tol_dias': 1},
            {'nombre': 'MEDIO',  'tol_monto': 50.0, 'tol_dias': 5},
            {'nombre': 'DEBIL',  'tol_monto': 100.0, 'tol_dias': 31},
        ]

    def conciliar(self, extracto: DatosExtracto, movimientos_sistema: List[Movimiento]) -> ResultadoConciliacion:
        banco_disp = list(extracto.movimientos)
        sist_disp = list(movimientos_sistema)
        resultado = ResultadoConciliacion()

        es_arca = extracto.banco == "ARCA-Mis Retenciones"
        
        # Si es ARCA, dos niveles estrictos:
        #   ARCA_FUERTE: monto exacto, +/- 3 días
        #   ARCA_MEDIANO: diferencia de hasta $1, mismo mes
        niveles_usar = self.niveles.copy()
        if es_arca:
            niveles_usar = [
                {'nombre': 'ARCA_FUERTE',  'tol_monto': 0.0, 'tol_dias': 3,  'mismo_mes': False},
                {'nombre': 'ARCA_MEDIANO', 'tol_monto': 1.0, 'tol_dias': 999, 'mismo_mes': True},
            ]

        # Separar solo gastos bancarios e impuestos usando prefijos de taxonomía
        # EXCEPCIÓN: Si es ARCA, queremos conciliar TODO, no separamos gastos.
        solo_operativos_banco = []
        gastos_banco = []
        
        TIPOS_GASTOS = (
            'RET_', 'PERC_', 'LEY25413', 'IVA', 
            'COMISION', 'INTERES', 'IMP_SELLOS'
        )
        
        for m in banco_disp:
            if not es_arca and m.tipo.startswith(TIPOS_GASTOS):
                gastos_banco.append(m)
            else:
                solo_operativos_banco.append(m)
        
        banco_disp = solo_operativos_banco
        
        # Procesar niveles de conciliación
        for nivel in niveles_usar:
            conciliados = self._hacer_pasada(banco_disp, sist_disp, nivel)
            resultado.conciliados.extend(conciliados)

        resultado.solo_banco = banco_disp
        resultado.solo_sistema = sist_disp
        
        # Categorizar gastos bancarios para el resumen
        self._procesar_gastos(gastos_banco, resultado)
        
        # Validar saldos (Saltar para ARCA ya que no tiene saldo anterior/final bancario)
        if not es_arca:
            self._validar_saldos(extracto, resultado)
        
        return resultado

    def _hacer_pasada(self, banco_list: List[Movimiento], sist_list: List[Movimiento], nivel: Dict) -> List[ItemConciliado]:
        conciliados = []
        banco_matched = set()
        sist_matched = set()
        
        candidatos = []
        mismo_mes = nivel.get('mismo_mes', False)
        for i, mb in enumerate(banco_list):
            for j, ms in enumerate(sist_list):
                diff_m = abs(abs(mb.monto) - abs(ms.monto))
                diff_d = abs((mb.fecha - ms.fecha).days)
                
                # Verificar restricción de mismo mes si aplica
                if mismo_mes:
                    if mb.fecha.year != ms.fecha.year or mb.fecha.month != ms.fecha.month:
                        continue
                
                if diff_m <= nivel['tol_monto'] and diff_d <= nivel['tol_dias']:
                    # El score prioriza monto exacto, luego cercanía de fecha
                    score = diff_m * 1000 + diff_d
                    candidatos.append((score, i, j, diff_m))
        
        candidatos.sort(key=lambda x: x[0])
        
        for score, i, j, diff_m in candidatos:
            if i in banco_matched or j in sist_matched:
                continue
                
            mb = banco_list[i]
            ms = sist_list[j]
            
            conciliados.append(ItemConciliado(
                banco=mb,
                sistema=ms,
                diferencia=round(diff_m, 2),
                diferencia_dias=diff_d, # Atributo dinámico, no en dataclass base
                nivel=nivel['nombre'],
                estado='CONCILIADO' if diff_m == 0 else 'CON_DIFERENCIA'
            ))
            banco_matched.add(i)
            sist_matched.add(j)
            
        # Remover de las listas originales (de atrás para adelante)
        for i in sorted(banco_matched, reverse=True):
            banco_list.pop(i)
        for j in sorted(sist_matched, reverse=True):
            sist_list.pop(j)
            
        return conciliados

    def _procesar_gastos(self, gastos: List[Movimiento], resultado: ResultadoConciliacion):
        for g in gastos:
            cat = g.tipo
            if cat not in resultado.gastos_por_categoria:
                resultado.gastos_por_categoria[cat] = {'total': 0.0, 'items': []}
            resultado.gastos_por_categoria[cat]['total'] += (g.debito + g.credito)
            resultado.gastos_por_categoria[cat]['items'].append(g)

    def _validar_saldos(self, extracto: DatosExtracto, resultado: ResultadoConciliacion):
        # Validación: Saldo Anterior + Créditos - Débitos = Saldo Final
        total_creditos = sum(m.credito for m in extracto.movimientos)
        total_debitos = sum(m.debito for m in extracto.movimientos)
        calculado = round(extracto.saldo_anterior + total_creditos - total_debitos, 2)
        
        resultado.validación_saldos = {
            'saldo_anterior': extracto.saldo_anterior,
            'total_creditos': total_creditos,
            'total_debitos': total_debitos,
            'saldo_final_extracto': extracto.saldo_final,
            'saldo_final_calculado': calculado,
            'coincide': calculado == extracto.saldo_final
        }
