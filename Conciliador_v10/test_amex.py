import os
import sys

# Agregar al path para importar correctamente
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from detector_banco import detectar_banco
from core.factory import FabricaParsers

def test_amex():
    pdf_path = r"c:\Pablo Ponti\Conciliador\Conciliador_V10\Ejemplos\Amex Paloma Vto 17-11-2025.pdf"
    
    banco = detectar_banco(pdf_path)
    
    if not banco:
        print("ERROR: No se detectó American Express")
        return
        
    parser = FabricaParsers.obtener_parser(banco)
    
    datos = parser.parse(pdf_path)
    
    with open("amex_test_out.txt", "w", encoding="utf-8") as f:
        f.write(f"Banco detectado: {banco}\n")
        f.write(f"Parser instanciado: {type(parser).__name__}\n\n")
        f.write("--- DATOS EXTRAÍDOS ---\n")
        f.write(f"Titular: {datos.titular}\n")
        f.write(f"Saldo Anterior: {datos.saldo_anterior}\n")
        f.write(f"Saldo Final: {datos.saldo_final}\n")
        f.write(f"Total Movimientos: {len(datos.movimientos)}\n\n")
        
        f.write("--- MOVIMIENTOS ---\n")
        tot_gastos = 0
        tot_pagos = 0
        for i, mov in enumerate(datos.movimientos):
            concepto_limpio = mov.concepto.replace('\n', ' ').replace('\r', '')
            f.write(f"{i+1}. Fecha: {mov.fecha.strftime('%Y-%m-%d')} | Concepto: {concepto_limpio} | D: {mov.debito} | C: {mov.credito} | Tipo: {mov.tipo}\n")
            tot_gastos += mov.debito
            tot_pagos += mov.credito
            
        f.write(f"\nSuma Débitos (Gastos): {tot_gastos}\n")
        f.write(f"Suma Créditos (Pagos): {tot_pagos}\n")
        f.write(f"Saldo calculado: {datos.saldo_anterior - tot_pagos + tot_gastos}\n")

if __name__ == '__main__':
    test_amex()
