import pdfplumber
import sys

def main():
    pdf_path = r"c:\Pablo Ponti\Conciliador\Conciliador_V10\Ejemplos\Amex Paloma Vto 17-11-2025.pdf"
    output_path = r"c:\Pablo Ponti\Conciliador\Conciliador_V10\test_pdf_out.txt"
    
    with pdfplumber.open(pdf_path) as pdf, open(output_path, 'w', encoding='utf-8') as out:
        for i, page in enumerate(pdf.pages):
            out.write(f"--- PAGE {i+1} ---\n")
            text = page.extract_text(layout=True)
            if text:
                out.write(text)
            out.write("\n\n")

if __name__ == '__main__':
    main()
