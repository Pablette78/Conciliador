from typing import List
from .models import Movimiento, DatosExtracto

def combinar_extractos(lista_datos: List[DatosExtracto]) -> DatosExtracto:
    if not lista_datos:
        return DatosExtracto(banco="Varios", titular="", movimientos=[])
    
    # Ordenar por fecha del primer movimiento
    lista_datos = sorted(
        [d for d in lista_datos if d.movimientos],
        key=lambda d: d.movimientos[0].fecha if d.movimientos else d.saldo_anterior
    )
    
    todos_movs = []
    for d in lista_datos:
        todos_movs.extend(d.movimientos)
    
    # Ordenar todos por fecha
    todos_movs.sort(key=lambda m: m.fecha)
    
    return DatosExtracto(
        banco=lista_datos[0].banco,
        titular=lista_datos[0].titular or "Varios",
        movimientos=todos_movs,
        saldo_anterior=lista_datos[0].saldo_anterior,
        saldo_final=lista_datos[-1].saldo_final
    )

def combinar_mayores(lista_movs: List[List[Movimiento]]) -> List[Movimiento]:
    combinados = []
    for movs in lista_movs:
        combinados.extend(movs)
    combinados.sort(key=lambda m: m.fecha)
    return combinados
