import os
import sys
import shutil
import tempfile
import io
import uuid
from typing import List, Optional, Dict
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# --- Entornos e Importaciones ---
sys.path.append(os.path.abspath("../../Conciliador_v10"))
sys.path.append(os.path.abspath("./Conciliador_v10")) # Para el contenedor Docker

# Intentar importaciones robustas para local y docker
try:
    from core.models import DatosExtracto, Movimiento, ItemConciliado
    from core.factory import FabricaParsers
    from core.engine import MotorConciliacion
    from core.utils import combinar_extractos, combinar_mayores
    from parser_excel import parsear_excel
    from generador_excel import generar_excel
    from detector_banco import detectar_banco_con_confianza
except ImportError:
    # Si falla, intentar rutas alternativas de contenedor
    from backend.parser_excel import parsear_excel
    from backend.generador_excel import generar_excel
    from backend.detector_banco import detectar_banco_con_confianza

app = FastAPI(title="Conciliador Bancario API")

# --- Seguridad ---
# Se espera esta clave en el header X-API-KEY
API_KEY = os.getenv("API_KEY", "conciliador_secret_123")

async def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Clave de acceso no válida o inexistente.")
    return x_api_key

# --- Configurar CORS ---
# Permitir específicamente el dominio de Vercel y locales para desarrollo
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://conciliador-virid.vercel.app",
    os.getenv("FRONTEND_URL", "https://conciliador-virid.vercel.app")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacenamiento temporal persistent
RESULTS_DIR = tempfile.mkdtemp(prefix="conciliador_results_")

def mov_to_dict(m: Movimiento) -> dict:
    return {
        "fecha": m.fecha.strftime("%d/%m/%Y") if m.fecha else "—",
        "concepto": m.concepto,
        "debito": m.debito,
        "credito": m.credito,
        "descripcion": m.descripcion,
        "tipo": m.tipo,
        "referencia": m.referencia,
        "monto": m.monto
    }

@app.get("/")
async def root():
    return {"status": "online", "message": "Conciliador Bancario API v10 Cloud"}

@app.post("/api/conciliar", dependencies=[Depends(verify_api_key)])
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
                    break
            if banco_final == "— auto —":
                raise HTTPException(status_code=400, detail="No se pudo detectar el banco automáticamente.")

        # 3. Procesar
        lista_datos = []
        for ruta in ruta_extractos:
            parser = FabricaParsers.obtener_parser(banco_final)
            if not parser: continue
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

        # 4. Generar Excel
        file_id = str(uuid.uuid4())
        filename = f"Conciliacion_{banco_final.replace(' ', '_')}.xlsx"
        ruta_resultado = os.path.join(RESULTS_DIR, f"{file_id}_{filename}")
        generar_excel(resultado, datos_comb, ruta_resultado, "Web", movimientos_sistema=movs_sis)

        # 5. Respuesta JSON
        solo_banco_ui = [mov_to_dict(m) for m in resultado.solo_banco[:100]]
        solo_sist_ui = [mov_to_dict(m) for m in resultado.solo_sistema[:100]]
        
        pre_gastos = []
        for cat, d in resultado.gastos_por_categoria.items():
            pre_gastos.append({
                "categoria": cat,
                "total": d["total"],
                "color": "#3B82F6" if "IMP" in cat else "#10B981"
            })

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
                "total_gastos": sum(d["total"] for d in resultado.gastos_por_categoria.values()),
                "titular": datos_comb.titular or banco_final,
                "solo_banco": solo_banco_ui,
                "solo_sistema": solo_sist_ui,
                "gastos": pre_gastos
            }
        }

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(proc_dir, ignore_errors=True)

@app.get("/api/download/{file_id}", dependencies=[Depends(verify_api_key)])
async def download_file(file_id: str):
    for f in os.listdir(RESULTS_DIR):
        if f.startswith(file_id):
            filepath = os.path.join(RESULTS_DIR, f)
            display_name = f.split("_", 1)[1] if "_" in f else f
            return FileResponse(
                filepath, 
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=display_name
            )
    raise HTTPException(status_code=404, detail="Archivo no encontrado.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
