# Conciliador Bancario

Aplicación de escritorio para conciliación bancaria automática.
Cruza extractos bancarios (PDF) con movimientos del sistema contable (Excel).

## Bancos soportados

- ✅ Banco Ciudad

## Qué hace

1. Lee el extracto bancario en PDF
2. Lee los movimientos del sistema contable en Excel
3. Cruza las transferencias por monto y fecha
4. Discrimina gastos bancarios e impuestos por tipo:
   - Retenciones IIBB SIRCREB
   - Retenciones IIBB Tucumán
   - Percepción IIBB CABA
   - Impuesto Ley 25413 (Débito y Crédito)
   - Comisiones bancarias
   - IVA / Débito Fiscal
   - Retención IVA
5. Genera un Excel con el resultado completo

## Instalación

### Requisitos

- Python 3.10 o superior (descargar de https://python.org)

### Pasos

1. Abrí una terminal (CMD o PowerShell) en la carpeta del proyecto
2. Instalá las dependencias:

```
pip install pdfplumber openpyxl
```

3. Ejecutá la aplicación:

```
python main.py
```

## Crear ejecutable (.exe)

Hacé doble click en `crear_exe.bat` o ejecutá en la terminal:

```
pip install pyinstaller
pyinstaller --onefile --windowed --name "ConciliadorBancario" main.py
```

El ejecutable queda en la carpeta `dist/`.

## Uso

1. Seleccioná el banco
2. Cargá el extracto bancario (PDF)
3. Cargá el mayor contable (Excel)
4. Click en CONCILIAR
5. El archivo de resultado se guarda en la misma carpeta del PDF

## Agregar un nuevo banco

Para agregar soporte para otro banco, creá un archivo `parser_NOMBREBANCO.py` 
siguiendo el mismo formato que `parser_banco_ciudad.py`. El parser debe exportar
una función `parsear_pdf(ruta)` que devuelva un dict con:
- movimientos: lista de dicts (fecha, concepto, debito, credito, descripcion, tipo)
- saldo_anterior: float
- saldo_final: float
- titular: str
