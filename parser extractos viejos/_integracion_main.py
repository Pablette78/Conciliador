# ============================================================
# INTEGRACIÓN DE PARSERS EN main.py
# Reemplazar / agregar en la sección de imports y configuración
# ============================================================

# --- IMPORTS (agregar a los existentes) ---
import parser_banco_ciudad   as pb_ciudad
import parser_galicia        as pb_galicia
import parser_comafi         as pb_comafi
import parser_santander      as pb_santander
import parser_extracto_excel as pb_extracto_excel  # Galicia xlsx
# Nuevos:
import parser_bna            as pb_bna
import parser_bbva           as pb_bbva
import parser_bapro          as pb_bapro
import parser_macro          as pb_macro
import parser_hsbc           as pb_hsbc
import parser_supervielle    as pb_supervielle
import parser_icbc           as pb_icbc
import parser_patagonia      as pb_patagonia
import parser_credicoop      as pb_credicoop
import parser_bancor         as pb_bancor


# --- DICCIONARIO DE PARSERS ---
# Clave = nombre que aparece en el OptionMenu de la GUI
# Valor = módulo del parser (debe tener función parsear_pdf(ruta) o parsear_excel(ruta))
PARSERS_PDF = {
    'Ciudad':       pb_ciudad,
    'Galicia':      pb_galicia,
    'Comafi':       pb_comafi,
    'Santander':    pb_santander,
    'BNA':          pb_bna,
    'BBVA':         pb_bbva,
    'Provincia':    pb_bapro,
    'Macro':        pb_macro,
    'HSBC':         pb_hsbc,
    'Supervielle':  pb_supervielle,
    'ICBC':         pb_icbc,
    'Patagonia':    pb_patagonia,
    'Credicoop':    pb_credicoop,
    'Bancor':       pb_bancor,
}

# Bancos que también soportan extracto en Excel (además de PDF)
PARSERS_EXCEL = {
    'Galicia': pb_extracto_excel,
    # Agregar aquí cuando se agreguen parsers Excel de otros bancos
}

# Lista ordenada para el OptionMenu (orden alfabético, Ciudad primero por ser el más usado)
BANCOS_DISPONIBLES = [
    'Bancor',
    'BBVA',
    'BNA',
    'Ciudad',
    'Comafi',
    'Credicoop',
    'Galicia',
    'HSBC',
    'ICBC',
    'Macro',
    'Patagonia',
    'Provincia',
    'Santander',
    'Supervielle',
]


# --- EN LA FUNCIÓN QUE CARGA EL EXTRACTO ---
def cargar_extracto(ruta: str, banco: str) -> dict:
    """
    Llama al parser correcto según banco y extensión del archivo.
    Retorna {movimientos, saldo_anterior, saldo_final, titular}
    """
    ext = ruta.lower().split('.')[-1]

    if ext in ('xlsx', 'xls') and banco in PARSERS_EXCEL:
        return PARSERS_EXCEL[banco].parsear_excel(ruta)

    if banco not in PARSERS_PDF:
        raise ValueError(f"Banco '{banco}' no tiene parser disponible.")

    return PARSERS_PDF[banco].parsear_pdf(ruta)


# --- EN EL OptionMenu de tkinter ---
# Reemplazar la lista estática de bancos por BANCOS_DISPONIBLES:
#
#   banco_var = tk.StringVar(value=BANCOS_DISPONIBLES[3])  # 'Ciudad' por defecto
#   banco_menu = tk.OptionMenu(frame, banco_var, *BANCOS_DISPONIBLES)
