import os
import sys
import shutil
import tempfile
import io
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# Añadir el path de la versión v10 para importar el núcleo
sys.path.append(os.path.abspath("../../conciliador v10"))

try:
    from core.models import DatosExtracto
    from core.factory import FabricaParsers
    from core.engine import MotorConciliacion
    from core.utils import combinar_extractos, combinar_mayores
    from parser_excel import parsear_excel
    from generador_excel import generar_excel
    from detector_banco import detectar_banco_con_confianza
except ImportError as e:
    print(f"Error de importación: {e}")

app = FastAPI(title="Conciliador Bancario API")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacenamiento temporal persistente para resultados (durante la sesión)
RESULTS_DIR = tempfile.mkdtemp(prefix="conciliador_results_")

@app.get("/")
async def root():
    return {"status": "online", "message": "Conciliador Bancario API v10"}

@app.post("/api/conciliar")
async def conciliar(
    banco: str = Form(...),
    extractos: List[UploadFile] = File(...),
    mayores: List[UploadFile] = File(...)
):
    proc_dir = tempfile.mkdtemp()
    try:
        # 1. Guardar archivos de entrada
        ruta_extractos = []
        for file in extractos:
            ruta = os.path.join(proc_dir, f"ext_{file.filename}")
            with open(ruta, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            ruta_extractos.append(ruta)

        ruta_mayores = []
        for file in mayores:
            ruta = os.path.join(proc_dir, f"may_{file.filename}")
            with open(ruta, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            ruta_mayores.append(ruta)

        # 2. Detectar Banco
        banco_final = banco
        if banco == "— auto —":
            for r in ruta_extractos:
                b_det, conf = detectar_banco_con_confianza(r)
                if b_det:
                    banco_final = b_det
                    print(f"Detección automática: {b_det} (confianza: {conf})")
                    break
            
            if banco_final == "— auto —":
                raise HTTPException(status_code=400, detail="No se pudo detectar el banco automáticamente. Selecciónalo manualmente.")

        # 3. Procesar
        lista_datos = []
        for ruta in ruta_extractos:
            parser = FabricaParsers.obtener_parser(banco_final)
            if not parser:
                continue
            datos = parser.parse(ruta)
            lista_datos.append(datos)

        if not lista_datos:
             raise HTTPException(status_code=400, detail=f"No se pudo parsear el extracto para el banco {banco_final}.")

        datos_comb = combinar_extractos(lista_datos)
        
        lista_sistema = []
        for ruta in ruta_mayores:
            movs = parsear_excel(ruta)
            lista_sistema.append(movs)
        movs_sis = combinar_mayores(lista_sistema)

        motor = MotorConciliacion()
        resultado = motor.conciliar(datos_comb, movs_sis)

        # 4. Generar Excel y guardarlo con un ID único
        file_id = str(uuid.uuid4())
        filename = f"Conciliacion_{banco_final.replace(' ', '_')}.xlsx"
        ruta_resultado = os.path.join(RESULTS_DIR, f"{file_id}_{filename}")
        
        generar_excel(resultado, datos_comb, ruta_resultado, "Web", movimientos_sistema=movs_sis)

        # 5. Respuesta JSON robusta
        return {
            "success": True,
            "banco": banco_final,
            "fileId": file_id,
            "filename": filename,
            "summary": {
                "n_conc": len(resultado.conciliados),
                "n_diff": sum(1 for c in resultado.conciliados if c.diferencia != 0),
                "n_banco": len(resultado.solo_banco),
                "n_sist": len(resultado.solo_sistema),
                "n_gastos": len(resultado.gastos_por_categoria),
                "titular": datos_comb.titular or banco_final,
                "gastos": {cat: d["total"] for cat, d in resultado.gastos_por_categoria.items()}
            }
        }

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Los archivos de entrada se pueden borrar ya
        # shutil.rmtree(proc_dir)
        pass

@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    # Buscar el archivo que empiece por este ID
    for f in os.listdir(RESULTS_DIR):
        if f.startswith(file_id):
            filepath = os.path.join(RESULTS_DIR, f)
            display_name = f.split("_", 1)[1] if "_" in f else f
            return FileResponse(
                filepath, 
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=display_name
            )
    
    raise HTTPException(status_code=404, detail="Archivo no encontrado o expirado.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
