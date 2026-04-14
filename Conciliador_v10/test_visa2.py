import os
import sys

# Agregar al sys.path para que encuentre los módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detector_banco import detectar_banco
from core.factory import FabricaParsers

def probar_pdf(pdf_path):
    print(f"\n--- PROBANDO: {os.path.basename(pdf_path)} ---")
    banco = detectar_banco(pdf_path)
    print(f"Banco detectado: {banco}")
    
    if banco:
        parser = FabricaParsers.obtener_parser(banco)
        print(f"Parser instanciado: {parser.__class__.__name__}")
        
        datos = parser.parse(pdf_path)
        
        print("\n--- DATOS EXTRAÍDOS ---")
        print(f"Banco/Validación: {datos.banco}")
        print(f"Titular: {datos.titular}")
        print(f"Saldo Anterior: {datos.saldo_anterior}")
        print(f"Saldo Final: {datos.saldo_final}")
        print(f"Total Movimientos: {len(datos.movimientos)}")
        
        print("\n--- MOVIMIENTOS ---")
        tot_gastos = 0
        tot_pagos = 0
        for i, mov in enumerate(datos.movimientos):
            concepto_limpio = mov.concepto.replace('\n', ' ').replace('\r', '')
            print(f"{i+1}. Concepto: {concepto_limpio} | D: {mov.debito} | C: {mov.credito} | Tipo: {mov.tipo}")
            tot_gastos += mov.debito
            tot_pagos += mov.credito
            
        print(f"\nSuma Débitos (Gastos): {tot_gastos}")
        print(f"Suma Créditos (Pagos): {tot_pagos}")
        print(f"Saldo calculado interno: {datos.saldo_anterior + tot_gastos - tot_pagos}")
    else:
        print("No se pudo detectar el banco.")

if __name__ == '__main__':
    probar_pdf(r"c:\Pablo Ponti\Conciliador\Conciliador_V10\Ejemplos\Resumen 06-10-2025 - Cuenta Visa 1313517922.pdf")
    probar_pdf(r"c:\Pablo Ponti\Conciliador\Conciliador_V10\Ejemplos\VENCIMIENTO ACTUAL 12 MAYO 2025.pdf")
