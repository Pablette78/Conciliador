from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class Movimiento:
    fecha: datetime
    concepto: str
    debito: float = 0.0
    credito: float = 0.0
    descripcion: str = ""
    tipo: str = "OTRO"
    referencia: str = ""
    saldo: Optional[float] = None

    @property
    def monto(self) -> float:
        """Retorna el monto neto (positivo para créditos, negativo para débitos)"""
        return round(self.credito - self.debito, 2)

@dataclass
class DatosExtracto:
    banco: str
    titular: str
    movimientos: List[Movimiento]
    saldo_anterior: float = 0.0
    saldo_final: float = 0.0
    cuenta: str = ""
    cbu: str = ""

@dataclass
class ItemConciliado:
    banco: Movimiento
    sistema: Movimiento
    diferencia: float
    diferencia_dias: int
    nivel: str  # 'FUERTE', 'MEDIO', 'DEBIL'
    estado: str # 'CONCILIADO', 'CON_DIFERENCIA'

@dataclass
class ResultadoConciliacion:
    conciliados: List[ItemConciliado] = field(default_factory=list)
    solo_banco: List[Movimiento] = field(default_factory=list)
    solo_sistema: List[Movimiento] = field(default_factory=list)
    gastos_por_categoria: Dict[str, Dict] = field(default_factory=dict)
    validación_saldos: Dict = field(default_factory=dict)
