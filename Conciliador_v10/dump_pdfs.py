import pdfplumber
import sys

def dump_pdf(pdf_path, output_path):
    with pdfplumber.open(pdf_path) as pdf, open(output_path, 'w', encoding='utf-8') as out:
        for i, page in enumerate(pdf.pages[:4]):
            out.write(f"--- PAGE {i+1} ---\n")
            text = page.extract_text(layout=True)
            if text:
                out.write(text)
            out.write("\n\n")

if __name__ == '__main__':
    dump_pdf(r"c:\Pablo Ponti\Conciliador\Conciliador_V10\Ejemplos\Resumen 06-10-2025 - Cuenta Visa 1313517922.pdf", r"c:\Pablo Ponti\Conciliador\Conciliador_V10\dump_visa.txt")
    dump_pdf(r"c:\Pablo Ponti\Conciliador\Conciliador_V10\Ejemplos\VENCIMIENTO ACTUAL 12 MAYO 2025.pdf", r"c:\Pablo Ponti\Conciliador\Conciliador_V10\dump_otro.txt")
