from typing import List
from .models import Movimiento, DatosExtracto

def combinar_extractos(lista_datos: List[DatosExtracto]) -> DatosExtracto:
    if not lista_datos:
        return DatosExtracto(banco="Varios", titular="", movimientos=[])
    
    # Ordenar por fecha del primer movimiento (filtrar vacíos para order, pero conservar datos)
    lista_con_movs = sorted(
        [d for d in lista_datos if d.movimientos],
        key=lambda d: d.movimientos[0].fecha
    )
    
    todos_movs = []
    for d in lista_con_movs:
        todos_movs.extend(d.movimientos)
    todos_movs.sort(key=lambda m: m.fecha)

    # Usar lista completa para metadata (puede tener extractos sin movs pero con saldos)
    if not lista_con_movs:
        # Todos los extractos llegaron vacíos → devolver con metadata del primero
        return DatosExtracto(
            banco=lista_datos[0].banco,
            titular=lista_datos[0].titular or "",
            movimientos=[],
            saldo_anterior=lista_datos[0].saldo_anterior,
            saldo_final=lista_datos[-1].saldo_final
        )

    return DatosExtracto(
        banco=lista_con_movs[0].banco,
        titular=lista_con_movs[0].titular or "Varios",
        movimientos=todos_movs,
        saldo_anterior=lista_con_movs[0].saldo_anterior,
        saldo_final=lista_con_movs[-1].saldo_final
    )


def combinar_mayores(lista_movs: List[List[Movimiento]]) -> List[Movimiento]:
    combinados = []
    for movs in lista_movs:
        combinados.extend(movs)
    combinados.sort(key=lambda m: m.fecha)
    return combinados
