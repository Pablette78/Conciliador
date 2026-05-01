"""
Módulo de pagos — Mercado Pago suscripciones recurrentes (preapproval_plan).

Flujo:
  1. Los planes Individual y Estudio se crean UNA SOLA VEZ en MP via preapproval_plan.
     Sus IDs se guardan como variables de entorno (MP_PLAN_ID_INDIVIDUAL / MP_PLAN_ID_ESTUDIO).
  2. Cuando un usuario quiere suscribirse, se crea un preapproval POR USUARIO via POST /preapproval,
     con external_reference=str(usuario_id) para identificarlo en el webhook.
  3. El usuario paga en el checkout de MP.
  4. MP llama a POST /webhooks/mp (webhook) → activa el plan en DB.
  5. MP también redirige al back_url → frontend llama a POST /auth/mp-confirm como confirmación.

Variables de entorno requeridas:
  MP_ACCESS_TOKEN       — token activo (TEST-... o APP_USR-...)
  MP_PLAN_ID_INDIVIDUAL — ID del plan Individual en MP (preapproval_plan)
  MP_PLAN_ID_ESTUDIO    — ID del plan Estudio en MP (preapproval_plan)

Variables opcionales:
  MP_WEBHOOK_SECRET     — secret para validar firmas HMAC-SHA256 del webhook
  FRONTEND_URL          — URL del frontend (default: https://contaflex.ar)
"""

import os
import hmac
import hashlib
import logging
import requests

from fastapi import APIRouter, Depends, HTTPException, Request, Header

from auth import get_usuario_actual, get_db, _cursor, PL, PLAN_LIMITS

log = logging.getLogger("payments")

MP_ACCESS_TOKEN   = os.getenv("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
FRONTEND_URL      = os.getenv("FRONTEND_URL", "https://contaflex.ar")

PLAN_IDS = {
    "Individual": os.getenv("MP_PLAN_ID_INDIVIDUAL", ""),
    "Estudio":    os.getenv("MP_PLAN_ID_ESTUDIO",    ""),
}

PLAN_PRECIOS = {
    "Individual": 14900,
    "Estudio":    32500,
}

MP_API = "https://api.mercadopago.com"

payments_router = APIRouter(tags=["Pagos"])


async def _handle_authorized_payment(invoice_id: str) -> dict:
    """
    Maneja subscription_authorized_payment: cobro mensual de una suscripción.
    Consulta el pago a MP, obtiene el preapproval_id y confirma que el plan
    sigue activo en DB. Si el pago fue rechazado, baja el usuario a Free.
    """
    if not invoice_id:
        return {"ok": True, "skipped": True}

    try:
        resp = requests.get(
            f"{MP_API}/authorized_payments/{invoice_id}",
            headers=_headers(),
            timeout=15,
        )
        if resp.status_code != 200:
            log.error(f"[MP Webhook] Error consultando authorized_payment {invoice_id}: "
                      f"{resp.status_code}")
            return {"ok": True, "skipped": True}
        pago = resp.json()
    except Exception as e:
        log.error(f"[MP Webhook] Error consultando authorized_payment {invoice_id}: {e}")
        return {"ok": True, "skipped": True}

    preapproval_id = pago.get("preapproval_id", "")
    status         = pago.get("status", "")

    log.info(f"[MP Webhook] authorized_payment invoice_id={invoice_id} "
             f"preapproval_id={preapproval_id} status={status}")

    if not preapproval_id:
        return {"ok": True, "skipped": True}

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(f"SELECT id, plan FROM usuarios WHERE mp_preapproval_id={PL}",
                    (preapproval_id,))
        row = cur.fetchone()
        if not row:
            log.warning(f"[MP Webhook] authorized_payment: no se encontró usuario "
                        f"con preapproval_id={preapproval_id}")
            return {"ok": True, "skipped": True}

        usuario_id = row["id"] if isinstance(row, dict) else row[0]

        if status == "authorized":
            log.info(f"[MP Webhook] Cobro mensual OK para usuario_id={usuario_id}")
        elif status in ("cancelled", "refunded", "charged_back"):
            _bajar_a_free_en_db(cur, usuario_id, f"cobro mensual status={status}")

    return {"ok": True}


# ---------------------------------------------------------------------------
# Funciones MP (puras, sin FastAPI)
# ---------------------------------------------------------------------------

def _headers(idempotency_key: str = "") -> dict:
    h = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        h["X-Idempotency-Key"] = idempotency_key
    return h


def get_init_point(usuario_id: int, plan: str) -> dict:
    """
    Obtiene el init_point del plan MP para redirigir al usuario al checkout.
    El usuario ingresa su tarjeta directamente en el checkout de MP.
    MP redirige al back_url con ?preapproval_id=XXX al finalizar.

    Retorna: { "init_point": str }
    Lanza ValueError si el plan no tiene MP_PLAN_ID configurado.
    Lanza RuntimeError si MP devuelve un error.
    """
    plan_id = PLAN_IDS.get(plan, "")
    if not plan_id:
        raise ValueError(
            f"Plan '{plan}' no tiene MP_PLAN_ID configurado. "
            "Creá el plan en MP y configurá la variable de entorno."
        )

    resp = requests.get(
        f"{MP_API}/preapproval_plan/{plan_id}",
        headers=_headers(),
        timeout=15,
    )
    if resp.status_code != 200:
        log.error(f"[MP] Error consultando plan {plan_id}: {resp.status_code} {resp.text}")
        raise RuntimeError(f"Mercado Pago respondió {resp.status_code}: {resp.text}")

    data       = resp.json()
    init_point = data.get("init_point")
    if not init_point:
        raise RuntimeError(f"MP no devolvió init_point para el plan {plan_id}")

    log.info(f"[MP] init_point obtenido para usuario_id={usuario_id} plan={plan}")
    return {"init_point": init_point}


def verificar_preapproval(preapproval_id: str) -> dict | None:
    """
    Consulta un preapproval en MP y lo retorna solo si está autorizado.
    Retorna None si no existe o el pago no está confirmado.
    """
    resp = requests.get(
        f"{MP_API}/preapproval/{preapproval_id}",
        headers=_headers(),
        timeout=15,
    )
    if resp.status_code != 200:
        log.error(f"[MP] Error consultando preapproval {preapproval_id}: {resp.status_code}")
        return None

    data = resp.json()
    if data.get("status") != "authorized":
        log.info(f"[MP] preapproval {preapproval_id} estado={data.get('status')} — no autorizado")
        return None

    return data


def cancelar_suscripcion(preapproval_id: str) -> bool:
    """Cancela una suscripción activa en MP. Devuelve True si fue exitoso."""
    resp = requests.patch(
        f"{MP_API}/preapproval/{preapproval_id}",
        json={"status": "cancelled"},
        headers=_headers(),
        timeout=15,
    )
    ok = resp.status_code in (200, 201)
    if not ok:
        log.error(f"[MP] Error cancelar preapproval {preapproval_id}: {resp.status_code} {resp.text}")
    return ok


def obtener_suscripcion(preapproval_id: str) -> dict:
    """Consulta el estado completo de un preapproval en MP. Lanza si falla."""
    resp = requests.get(
        f"{MP_API}/preapproval/{preapproval_id}",
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def validar_firma_webhook(x_signature: str, x_request_id: str, data_id: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 del webhook de MP.
    Header: "ts=<timestamp>,v1=<hex_digest>"
    Retorna True si no hay MP_WEBHOOK_SECRET configurado (modo dev sin secret).
    """
    if not MP_WEBHOOK_SECRET:
        log.warning("[MP] MP_WEBHOOK_SECRET no configurado — firma NO verificada.")
        return True

    try:
        parts    = dict(p.split("=", 1) for p in x_signature.split(","))
        ts       = parts.get("ts", "")
        v1       = parts.get("v1", "")
        template = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        digest   = hmac.new(
            MP_WEBHOOK_SECRET.encode(), template.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(digest, v1)
    except Exception as e:
        log.error(f"[MP] Error validando firma: {e}")
        return False


def _activar_plan_en_db(cur, usuario_id: int, plan: str, preapproval_id: str) -> None:
    nuevo_limite = PLAN_LIMITS.get(plan, 5)
    cur.execute(
        f"UPDATE usuarios SET plan={PL}, limite_mensual={PL}, activo=1, "
        f"plan_pendiente=NULL, mp_preapproval_id={PL} WHERE id={PL}",
        (plan, nuevo_limite, preapproval_id, usuario_id),
    )
    log.info(f"[MP] Plan {plan} activado para usuario_id={usuario_id}")


def _bajar_a_free_en_db(cur, usuario_id: int, razon: str) -> None:
    cur.execute(
        f"UPDATE usuarios SET plan='Free', limite_mensual=5, mp_preapproval_id=NULL WHERE id={PL}",
        (usuario_id,),
    )
    log.info(f"[MP] Plan revertido a Free para usuario_id={usuario_id} ({razon})")


# ---------------------------------------------------------------------------
# Rutas de pagos (mismo prefijo que antes para no romper el frontend)
# ---------------------------------------------------------------------------

@payments_router.post("/auth/subscribe")
async def iniciar_suscripcion(plan: str, usuario: dict = Depends(get_usuario_actual)):
    """
    Crea un preapproval individual en MP y devuelve { init_point, preapproval_id }.
    El preapproval_id se guarda en DB como pending para que el webhook pueda identificar al usuario.
    """
    if plan not in PLAN_PRECIOS:
        raise HTTPException(status_code=400, detail=f"Plan '{plan}' no válido para suscripción.")
    if plan == usuario.get("plan"):
        raise HTTPException(status_code=400, detail="Ya tenés este plan activo.")

    try:
        result = get_init_point(usuario["id"], plan)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=502, detail=str(e))

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            f"UPDATE usuarios SET plan_pendiente={PL} WHERE id={PL}",
            (plan, usuario["id"]),
        )

    return result


@payments_router.post("/auth/mp-confirm")
async def mp_confirm(preapproval_id: str, usuario: dict = Depends(get_usuario_actual)):
    """
    El frontend llama este endpoint cuando MP redirige con ?preapproval_id=XXX.
    Verifica el estado del pago con MP y activa el plan del usuario autenticado.
    """
    sub = verificar_preapproval(preapproval_id)
    if not sub:
        raise HTTPException(status_code=400,
                            detail="La suscripción no está activa en Mercado Pago.")

    plan_id_mp = sub.get("preapproval_plan_id", "")
    plan       = next((k for k, v in PLAN_IDS.items() if v == plan_id_mp), None)
    if not plan:
        raise HTTPException(status_code=400,
                            detail="No se reconoce el plan de la suscripción.")

    with get_db() as conn:
        cur = _cursor(conn)
        _activar_plan_en_db(cur, usuario["id"], plan, preapproval_id)

    return {"ok": True, "plan": plan}


@payments_router.post("/auth/cancel-subscription")
async def cancelar_suscripcion_usuario(usuario: dict = Depends(get_usuario_actual)):
    """Cancela la suscripción activa del usuario en MP y lo baja a Free."""
    preapproval_id = usuario.get("mp_preapproval_id")
    if not preapproval_id:
        raise HTTPException(status_code=400,
                            detail="No tenés una suscripción activa en MP.")

    cancelar_suscripcion(preapproval_id)

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            f"UPDATE usuarios SET plan='Free', limite_mensual=5, "
            f"mp_preapproval_id=NULL, plan_pendiente=NULL WHERE id={PL}",
            (usuario["id"],),
        )
    return {"ok": True, "message": "Suscripción cancelada. Tu plan volvió a Free."}


@payments_router.post("/webhooks/mp")
async def webhook_mp(
    request:      Request,
    x_signature:  str = Header(default="", alias="x-signature"),
    x_request_id: str = Header(default="", alias="x-request-id"),
):
    """
    Webhook de MP para suscripciones (preapproval).
    Identifica al usuario con esta prioridad:
      1. external_reference (usuario_id guardado al crear el preapproval)
      2. mp_preapproval_id  (guardado en DB cuando el usuario inició la suscripción)
      3. payer_email        (fallback final, requiere que el email coincida)
    """
    body    = await request.json()
    data_id = (body.get("data") or {}).get("id", "")

    log.info(f"[MP Webhook] type={body.get('type')} action={body.get('action')} "
             f"data_id={data_id}")

    if x_signature and not validar_firma_webhook(x_signature, x_request_id, data_id):
        log.warning(f"[MP Webhook] Firma inválida — descartado. data_id={data_id}")
        raise HTTPException(status_code=401, detail="Firma inválida.")

    tipo = body.get("type")

    # subscription_authorized_payment: cobro mensual procesado
    if tipo == "subscription_authorized_payment":
        return await _handle_authorized_payment(data_id)

    if tipo != "subscription_preapproval":
        return {"ok": True, "skipped": True}

    if not data_id:
        return {"ok": True, "skipped": True}

    try:
        sub = obtener_suscripcion(data_id)
    except Exception as e:
        log.error(f"[MP Webhook] Error consultando suscripcion {data_id}: {e}")
        raise HTTPException(status_code=502,
                            detail="No se pudo consultar la suscripción en MP.")

    estado         = sub.get("status")
    preapproval_id = sub.get("id", data_id)
    plan_id_mp     = sub.get("preapproval_plan_id", "")
    external_ref   = sub.get("external_reference", "")
    payer_email    = (sub.get("payer") or {}).get("email", "")

    log.info(f"[MP Webhook] preapproval_id={preapproval_id} estado={estado} "
             f"external_ref={external_ref!r} payer={payer_email} plan_id={plan_id_mp}")

    plan = next((k for k, v in PLAN_IDS.items() if v == plan_id_mp), None)
    if not plan:
        log.error(f"[MP Webhook] plan_id={plan_id_mp} no reconocido — ignorado.")
        return {"ok": True, "skipped": True}

    with get_db() as conn:
        cur = _cursor(conn)

        # 1. Identificar por external_reference (más confiable)
        usuario_id = None
        if external_ref and external_ref.isdigit():
            cur.execute(f"SELECT id FROM usuarios WHERE id={PL}", (int(external_ref),))
            row = cur.fetchone()
            if row:
                usuario_id = int(external_ref)
                log.info(f"[MP Webhook] Usuario encontrado por external_reference={external_ref}")

        # 2. Por mp_preapproval_id pending (guardado al llamar /auth/subscribe)
        if not usuario_id:
            cur.execute(f"SELECT id FROM usuarios WHERE mp_preapproval_id={PL}", (preapproval_id,))
            row = cur.fetchone()
            if row:
                usuario_id = row["id"] if isinstance(row, dict) else row[0]
                log.info(f"[MP Webhook] Usuario encontrado por mp_preapproval_id={preapproval_id}")

        # 3. Por email del pagador (fallback — requiere que emails coincidan)
        if not usuario_id and payer_email:
            cur.execute(f"SELECT id FROM usuarios WHERE email={PL}", (payer_email,))
            row = cur.fetchone()
            if row:
                usuario_id = row["id"] if isinstance(row, dict) else row[0]
                log.info(f"[MP Webhook] Usuario encontrado por payer_email={payer_email}")

        if not usuario_id:
            log.error(f"[MP Webhook] No se pudo identificar usuario para "
                      f"preapproval_id={preapproval_id} — ignorado.")
            return {"ok": True, "skipped": True}

        if estado == "authorized":
            _activar_plan_en_db(cur, usuario_id, plan, preapproval_id)

        elif estado in ("cancelled", "paused"):
            _bajar_a_free_en_db(cur, usuario_id, f"MP estado={estado}")

        else:
            log.info(f"[MP Webhook] Estado {estado!r} para usuario_id={usuario_id} — sin acción.")

    return {"ok": True}
