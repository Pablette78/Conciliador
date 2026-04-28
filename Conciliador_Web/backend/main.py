import os
import sys
import shutil
import tempfile
import uuid
import re
from typing import List
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from logger import get_logger
from auth import init_db, get_usuario_actual, require_admin, get_db, PL, PLAN_LIMITS, _cursor, router as auth_router

logger = get_logger("conciliador.main")

from core.models import Movimiento
from core.factory import FabricaParsers
from core.engine import MotorConciliacion
from core.utils import combinar_extractos, combinar_mayores
from parser_excel import parsear_excel
from generador_excel import generar_excel
from detector_banco import detectar_banco_con_confianza

# --- App ---
app = FastAPI(title="Conciliador Bancario API", version="2.0")

# Inicializar base de datos de usuarios al arrancar
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Base de datos de usuarios inicializada.")

# Registrar rutas de autenticación
app.include_router(auth_router)

# --- CORS ---
# FRONTEND_URL puede ser una lista separada por comas para múltiples dominios
_frontend_url_env = os.getenv("FRONTEND_URL", "https://contaflex.ar")
_extra_origins = [u.strip() for u in _frontend_url_env.split(",") if u.strip()]

allowed_origins = list({
    "http://localhost:5173",
    "http://localhost:3000",
    "https://conciliador-virid.vercel.app",
    "https://www.contaflex.ar",
    "https://contaflex.ar",
    *_extra_origins,
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Constantes ---
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
RESULTS_DIR = tempfile.mkdtemp(prefix="conciliador_results_")
COLORES_CATEGORIA = ["#3B82F6", "#F59E0B", "#10B981", "#6366F1", "#EC4899"]


# --- Helpers ---
def _validar_archivo(file: UploadFile) -> None:
    nombre = file.filename or ""
    ext = os.path.splitext(nombre)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: '{nombre}'. Solo PDF, XLSX y XLS."
        )


async def _guardar_archivo(file: UploadFile, destino: str) -> None:
    tamanio = 0
    with open(destino, "wb") as buf:
        while chunk := await file.read(1024 * 1024):
            tamanio += len(chunk)
            if tamanio > MAX_FILE_SIZE_BYTES:
                buf.close()
                os.remove(destino)
                raise HTTPException(
                    status_code=413,
                    detail=f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE_MB} MB."
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
        "monto": m.monto,
    }


# --- Endpoints ---
@app.get("/")
async def root():
    return {"status": "online", "version": "2.0"}


@app.post("/api/conciliar")
async def conciliar(
    banco: str = Form(...),
    extractos: List[UploadFile] = File(...),
    mayores: List[UploadFile] = File(...),
    usuario: dict = Depends(get_usuario_actual),
):
    logger.info(f"Conciliación iniciada por '{usuario['username']}' | banco={banco}")
    
    # Validar Límite Mensual
    if usuario["rol"] != "admin":
        if usuario["usos_mes_actual"] >= usuario["limite_mensual"]:
            raise HTTPException(
                status_code=403, 
                detail=f"Has alcanzado tu límite mensual de {usuario['limite_mensual']} conciliaciones. Actualizá tu plan para seguir."
            )

    proc_dir = tempfile.mkdtemp()
    try:
        # Validar archivos
        for f in extractos + mayores:
            _validar_archivo(f)

        # Guardar extractos
        ruta_extractos = []
        for file in extractos:
            nombre = re.sub(r'[^\w.\-]', '_', file.filename or "extracto")
            ruta = os.path.join(proc_dir, f"ext_{nombre}")
            await _guardar_archivo(file, ruta)
            ruta_extractos.append(ruta)

        # Guardar mayores
        ruta_mayores = []
        for file in mayores:
            nombre = re.sub(r'[^\w.\-]', '_', file.filename or "mayor")
            ruta = os.path.join(proc_dir, f"may_{nombre}")
            await _guardar_archivo(file, ruta)
            ruta_mayores.append(ruta)

        # Detectar banco
        banco_final = banco
        if banco == "— auto —":
            for r in ruta_extractos:
                b_det, conf = detectar_banco_con_confianza(r)
                if b_det:
                    banco_final = b_det
                    logger.info(f"Banco detectado: {banco_final} (confianza: {conf})")
                    break
            if banco_final == "— auto —":
                raise HTTPException(status_code=400, detail="No se pudo detectar el banco automáticamente.")

        # Parsear extractos
        lista_datos = []
        for ruta in ruta_extractos:
            parser = FabricaParsers.obtener_parser(banco_final)
            if not parser:
                logger.warning(f"Sin parser para banco: {banco_final}")
                continue
            lista_datos.append(parser.parse(ruta))

        if not lista_datos:
            raise HTTPException(status_code=400, detail=f"No se pudo parsear el extracto para '{banco_final}'.")

        datos_comb = combinar_extractos(lista_datos)

        # Parsear mayores
        movs_sis = combinar_mayores([parsear_excel(r) for r in ruta_mayores])

        # Conciliar
        resultado = MotorConciliacion().conciliar(datos_comb, movs_sis)

        # Generar Excel
        file_id = str(uuid.uuid4())
        nombre_banco = re.sub(r'[^\w]', '_', banco_final)
        filename = f"Conciliacion_{nombre_banco}.xlsx"
        ruta_resultado = os.path.join(RESULTS_DIR, f"{file_id}_{filename}")
        generar_excel(resultado, datos_comb, ruta_resultado, "Web", movs_sist=movs_sis)
        logger.info(f"Excel generado: {filename} por '{usuario['username']}'")

        # Incrementar contador de uso
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE usuarios SET usos_mes_actual = usos_mes_actual + 1 WHERE id = {PL}",
                (usuario["id"],)
            )

        pre_gastos = [
            {"categoria": cat, "total": d["total"], "color": COLORES_CATEGORIA[i % len(COLORES_CATEGORIA)]}
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
                "gastos": pre_gastos,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error inesperado en /api/conciliar")
        raise HTTPException(status_code=500, detail=f"Error interno: {type(e).__name__}: {str(e)}")
    finally:
        shutil.rmtree(proc_dir, ignore_errors=True)


@app.get("/api/download/{file_id}")
async def download_file(file_id: str, usuario: dict = Depends(get_usuario_actual)):
    if not UUID_RE.match(file_id):
        raise HTTPException(status_code=400, detail="Identificador inválido.")

    for f in os.listdir(RESULTS_DIR):
        if f.startswith(file_id):
            filepath = os.path.join(RESULTS_DIR, f)
            if not os.path.realpath(filepath).startswith(os.path.realpath(RESULTS_DIR)):
                raise HTTPException(status_code=400, detail="Acceso no permitido.")
            display_name = f[len(file_id) + 1:]
            logger.info(f"Descarga: {display_name} por '{usuario['username']}'")
            return FileResponse(
                filepath,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=display_name,
            )
    raise HTTPException(status_code=404, detail="Archivo no encontrado.")


# --- Webhook Mercado Pago ---

@app.post("/webhooks/mp")
async def webhook_mp(
    request: Request,
    x_signature:  str = Header(default="", alias="x-signature"),
    x_request_id: str = Header(default="", alias="x-request-id"),
):
    """
    Recibe notificaciones de MP para suscripciones (preapproval).
    MP envía: { type, action, data: { id } }
    Documentación: https://www.mercadopago.com.ar/developers/es/docs/subscriptions/additional-content/notifications/webhooks
    """
    from payments import obtener_suscripcion, validar_firma_webhook

    body = await request.json()
    logger.info(f"[MP Webhook] {body.get('type')} action={body.get('action')} data={body.get('data')}")

    data_id = (body.get("data") or {}).get("id", "")

    # Validar firma solo cuando hay secret configurado
    if x_signature and not validar_firma_webhook(x_signature, x_request_id, data_id):
        logger.warning(f"[MP Webhook] Firma inválida — descartado. data_id={data_id}")
        raise HTTPException(status_code=401, detail="Firma inválida.")

    # Solo procesar eventos de suscripción
    if body.get("type") != "subscription_preapproval":
        return {"ok": True, "skipped": True}

    if not data_id:
        return {"ok": True, "skipped": True}

    try:
        sub = obtener_suscripcion(data_id)
    except Exception as e:
        logger.error(f"[MP Webhook] Error consultando suscripcion {data_id}: {e}")
        raise HTTPException(status_code=502, detail="No se pudo consultar la suscripción en MP.")

    estado         = sub.get("status")        # authorized | paused | cancelled | pending
    preapproval_id = sub.get("id", data_id)
    payer_email    = (sub.get("payer") or {}).get("email", "")
    plan_id_mp     = sub.get("preapproval_plan_id", "")

    logger.info(f"[MP Webhook] preapproval_id={preapproval_id} estado={estado} payer={payer_email} plan_id={plan_id_mp}")

    # Identificar el plan por el plan_id de MP
    from payments import PLAN_IDS
    plan = next((k for k, v in PLAN_IDS.items() if v == plan_id_mp), None)
    if not plan:
        logger.error(f"[MP Webhook] No se reconoce plan_id={plan_id_mp}")
        return {"ok": True, "skipped": True}

    # Identificar al usuario por email (el email que usó en MP debe coincidir con el de ContaFlex)
    if not payer_email:
        logger.error(f"[MP Webhook] Sin payer_email en la suscripción {preapproval_id}")
        return {"ok": True, "skipped": True}

    with get_db() as conn:
        cur = _cursor(conn)

        # Buscar usuario por email o por plan_pendiente + mp_preapproval_id
        cur.execute(f"SELECT id FROM usuarios WHERE email={PL}", (payer_email,))
        row = cur.fetchone()
        if not row:
            logger.error(f"[MP Webhook] No se encontró usuario con email={payer_email}")
            return {"ok": True, "skipped": True}
        usuario_id = row["id"] if isinstance(row, dict) else row[0]

        if estado == "authorized":
            # Pago confirmado → activar plan
            nuevo_limite = PLAN_LIMITS.get(plan, 5)
            cur.execute(
                f"UPDATE usuarios SET plan={PL}, limite_mensual={PL}, activo=1, "
                f"plan_pendiente=NULL, mp_preapproval_id={PL} WHERE id={PL}",
                (plan, nuevo_limite, preapproval_id, usuario_id)
            )
            logger.info(f"[MP Webhook] Plan {plan} activado para usuario_id={usuario_id} ({payer_email})")

        elif estado in ("cancelled", "paused"):
            # Pago fallido o cancelado → bajar a Free
            cur.execute(
                f"UPDATE usuarios SET plan='Free', limite_mensual=5, mp_preapproval_id=NULL WHERE id={PL}",
                (usuario_id,)
            )
            logger.info(f"[MP Webhook] Plan revertido a Free para usuario_id={usuario_id} (estado MP: {estado})")

    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
