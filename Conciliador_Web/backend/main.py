import os
import sys
import shutil
import tempfile
import uuid
import logging
import re
from typing import List
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("conciliador")

# --- Entornos e Importaciones ---
sys.path.append(os.path.abspath("../../Conciliador_v10"))
sys.path.append(os.path.abspath("./Conciliador_v10"))  # Para el contenedor Docker

try:
    from core.models import DatosExtracto, Movimiento, ItemConciliado
    from core.factory import FabricaParsers
    from core.engine import MotorConciliacion
    from core.utils import combinar_extractos, combinar_mayores
    from parser_excel import parsear_excel
    from generador_excel import generar_excel
    from detector_banco import detectar_banco_con_confianza
except ImportError:
    from backend.parser_excel import parsear_excel
    from backend.generador_excel import generar_excel
    from backend.detector_banco import detectar_banco_con_confianza

app = FastAPI(title="Conciliador Bancario API")

# --- Seguridad ---
# REQUERIDO: definir API_KEY como variable de entorno en producción.
# Sin ella, el servidor levanta pero todas las rutas protegidas devuelven 403.
API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    logger.warning(
        "API_KEY no configurada. Define la variable de entorno API_KEY antes de exponer el servidor."
    )

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

async def verify_api_key(x_api_key: str = Header(None)):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Clave de acceso no válida o inexistente.")
    return x_api_key

# --- CORS ---
allowed_origins = list({
    "http://localhost:5173",
    "http://localhost:3000",
    "https://conciliador-virid.vercel.app",
    os.getenv("FRONTEND_URL", "https://conciliador-virid.vercel.app"),
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-KEY"],
)

# Directorio persistente para resultados descargables
RESULTS_DIR = tempfile.mkdtemp(prefix="conciliador_results_")
logger.info(f"Directorio de resultados: {RESULTS_DIR}")


def _validar_archivo(file: UploadFile) -> None:
    """Valida extensión y nombre de archivo. Lanza HTTPException si no es válido."""
    nombre = file.filename or ""
    ext = os.path.splitext(nombre)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: '{nombre}'. Solo se aceptan PDF, XLSX y XLS."
        )
    # Sanitizar nombre: solo caracteres seguros
    nombre_seguro = re.sub(r'[^\w.\-]', '_', nombre)
    if nombre_seguro != nombre:
        logger.warning(f"Nombre de archivo sanitizado: '{nombre}' -> '{nombre_seguro}'")


async def _guardar_archivo(file: UploadFile, destino: str) -> None:
    """Lee el archivo en chunks, valida el tamaño y lo guarda en destino."""
    tamanio = 0
    with open(destino, "wb") as buf:
        while chunk := await file.read(1024 * 1024):  # leer en bloques de 1MB
            tamanio += len(chunk)
            if tamanio > MAX_FILE_SIZE_BYTES:
                buf.close()
                os.remove(destino)
                raise HTTPException(
                    status_code=413,
                    detail=f"Archivo demasiado grande. Máximo permitido: {MAX_FILE_SIZE_MB} MB."
                )
            buf.write(chunk)


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
        # 1. Validar y guardar extractos
        for file in extractos:
            _validar_archivo(file)
        for file in mayores:
            _validar_archivo(file)

        ruta_extractos = []
        for file in extractos:
            nombre_seguro = re.sub(r'[^\w.\-]', '_', file.filename or "extracto")
            ruta = os.path.join(proc_dir, f"ext_{nombre_seguro}")
            await _guardar_archivo(file, ruta)
            ruta_extractos.append(ruta)

        ruta_mayores = []
        for file in mayores:
            nombre_seguro = re.sub(r'[^\w.\-]', '_', file.filename or "mayor")
            ruta = os.path.join(proc_dir, f"may_{nombre_seguro}")
            await _guardar_archivo(file, ruta)
            ruta_mayores.append(ruta)

        # 2. Detectar banco
        banco_final = banco
        if banco == "— auto —":
            for r in ruta_extractos:
                b_det, conf = detectar_banco_con_confianza(r)
                if b_det:
                    banco_final = b_det
                    logger.info(f"Banco detectado automáticamente: {banco_final} (confianza: {conf})")
                    break
            if banco_final == "— auto —":
                raise HTTPException(status_code=400, detail="No se pudo detectar el banco automáticamente.")

        # 3. Parsear extractos
        lista_datos = []
        for ruta in ruta_extractos:
            parser = FabricaParsers.obtener_parser(banco_final)
            if not parser:
                logger.warning(f"No se encontró parser para banco: {banco_final}")
                continue
            datos = parser.parse(ruta)
            lista_datos.append(datos)

        if not lista_datos:
            raise HTTPException(
                status_code=400,
                detail=f"No se pudo parsear el extracto para el banco '{banco_final}'."
            )

        datos_comb = combinar_extractos(lista_datos)

        # 4. Parsear mayores
        lista_sistema = []
        for ruta in ruta_mayores:
            movs = parsear_excel(ruta)
            lista_sistema.append(movs)
        movs_sis = combinar_mayores(lista_sistema)

        # 5. Conciliar
        motor = MotorConciliacion()
        resultado = motor.conciliar(datos_comb, movs_sis)

        # 6. Generar Excel de resultado
        file_id = str(uuid.uuid4())
        nombre_banco_seguro = re.sub(r'[^\w]', '_', banco_final)
        filename = f"Conciliacion_{nombre_banco_seguro}.xlsx"
        ruta_resultado = os.path.join(RESULTS_DIR, f"{file_id}_{filename}")
        generar_excel(resultado, datos_comb, ruta_resultado, "Web", movimientos_sistema=movs_sis)
        logger.info(f"Excel generado: {ruta_resultado}")

        # 7. Respuesta
        COLORES_CATEGORIA = ["#3B82F6", "#F59E0B", "#10B981", "#6366F1", "#EC4899"]
        pre_gastos = [
            {
                "categoria": cat,
                "total": d["total"],
                "color": COLORES_CATEGORIA[i % len(COLORES_CATEGORIA)]
            }
            for i, (cat, d) in enumerate(resultado.gastos_por_categoria.items())
        ]

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
                "solo_banco": [mov_to_dict(m) for m in resultado.solo_banco[:100]],
                "solo_sistema": [mov_to_dict(m) for m in resultado.solo_sistema[:100]],
                "gastos": pre_gastos
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error inesperado en /api/conciliar")
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
    finally:
        shutil.rmtree(proc_dir, ignore_errors=True)


@app.get("/api/download/{file_id}", dependencies=[Depends(verify_api_key)])
async def download_file(file_id: str):
    # Validar que file_id sea un UUID válido (evita path traversal)
    if not UUID_RE.match(file_id):
        raise HTTPException(status_code=400, detail="Identificador de archivo inválido.")

    for f in os.listdir(RESULTS_DIR):
        if f.startswith(file_id):
            filepath = os.path.join(RESULTS_DIR, f)
            # Verificar que el path resuelto esté dentro de RESULTS_DIR
            if not os.path.realpath(filepath).startswith(os.path.realpath(RESULTS_DIR)):
                raise HTTPException(status_code=400, detail="Acceso no permitido.")
            display_name = f[len(file_id) + 1:]  # quitar "uuid_" del inicio
            return FileResponse(
                filepath,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=display_name
            )
    raise HTTPException(status_code=404, detail="Archivo no encontrado.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
