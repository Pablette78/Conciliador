import pdfplumber
import re
import sys

def parse_visa(pdf_path):
    print(f"\n--- PROCESANDO: {pdf_path} ---")
    lineas = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text:
                lineas.extend(text.split('\n'))

    movimientos = []
    
    # regex robusta:
    # Inicio con posibles fechas:
    # 1. Santander: "25 Setiem. 12" o "      12"
    # 2. Galicia: "16.02.25"
    patron_mov = re.compile(
        r'^\s*'
        r'(?:(?:\d{2}\s+[A-Za-z\.]+\s+)?\d{2}|\d{2}\.\d{2}\.\d{2})\s+' # Fecha o dia
        r'(?:[A-Za-z\d\*]+\s+)*' # Posibles comprobantes, tickets, "SU PAGO...", etc.
        r'(.*)'
    )
    
    for linea in lineas:
        if not linea.strip(): continue
        
        # Omitimos totales agrupados u headers por ahora para solo imprimir
        if "Total Consumos" in linea or "SALDO " in linea.upper() or "PAGO" in linea.upper() and not "SU PAGO" in linea:
            continue
            
        # Santander format often sets the Amounts starting at specific character positions (e.g., col 60 for ARS, col 75 for USD)
        # We can just split by multiple spaces!
        partes = re.split(r'\s{2,}', linea.strip())
        if len(partes) >= 2:
            # Detect amounts
            def is_amount(s):
                return bool(re.match(r'^-?[\d\.]+,\d{2}-?$', s.strip()))
            
            p1 = partes[-1]
            p2 = partes[-2]
            
            ars_val = 0.0
            usd_val = 0.0
            concepto_str = ""
            
            if is_amount(p1) and is_amount(p2):
                ars_val = p2
                usd_val = p1
                concepto_str = " ".join(partes[:-2])
            elif is_amount(p1):
                idx = linea.rfind(p1)
                # Usually USD is beyond char 70.
                if idx > 70 or "USD" in " ".join(partes[:-1]).upper():
                    usd_val = p1
                else:
                    ars_val = p1
                concepto_str = " ".join(partes[:-1])
                
            if ars_val != 0.0:
                print(f"ARS: {ars_val} | Concepto: {concepto_str}")
                movimientos.append(ars_val)

if __name__ == '__main__':
    parse_visa(r"c:\Pablo Ponti\Conciliador\Conciliador_V10\Ejemplos\Resumen 06-10-2025 - Cuenta Visa 1313517922.pdf")
    parse_visa(r"c:\Pablo Ponti\Conciliador\Conciliador_V10\Ejemplos\VENCIMIENTO ACTUAL 12 MAYO 2025.pdf")
