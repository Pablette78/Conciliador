"""
Integración Mercado Pago — suscripciones recurrentes (preapproval_plan).

Flujo:
  1. Los planes Individual y Estudio se crean UNA SOLA VEZ en MP via preapproval_plan.
  2. Sus IDs se guardan como variables de entorno (MP_PLAN_ID_INDIVIDUAL / MP_PLAN_ID_ESTUDIO).
  3. Cuando un usuario quiere suscribirse, se lo redirige al init_point del plan.
  4. MP crea un preapproval (suscripción) para ese usuario y dispara webhook.
  5. El webhook activa el plan en la DB usando external_reference = "usuario_id:plan".

Variables de entorno requeridas:
  MP_ACCESS_TOKEN       — token activo (TEST-... o APP_USR-...)
  MP_WEBHOOK_SECRET     — secret para validar firmas de webhooks (generado por MP)
  MP_PLAN_ID_INDIVIDUAL — ID del plan Individual en MP (preapproval_plan)
  MP_PLAN_ID_ESTUDIO    — ID del plan Estudio en MP (preapproval_plan)

Variables opcionales:
  FRONTEND_URL          — URL del frontend (default: https://contaflex.ar)
"""

import os
import hmac
import hashlib
import logging
import requests

log = logging.getLogger("payments")

MP_ACCESS_TOKEN   = os.getenv("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
FRONTEND_URL      = os.getenv("FRONTEND_URL", "https://contaflex.ar")

# IDs de planes creados en MP (preapproval_plan)
PLAN_IDS = {
    "Individual": os.getenv("MP_PLAN_ID_INDIVIDUAL", ""),
    "Estudio":    os.getenv("MP_PLAN_ID_ESTUDIO",    ""),
}

# Para referencia de precios (usado en el frontend)
PLAN_PRECIOS = {
    "Individual": 14900,
    "Estudio":    32500,
}

MP_API = "https://api.mercadopago.com"


def _headers(idempotency_key: str = "") -> dict:
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": idempotency_key,
    }


def get_init_point(usuario_id: int, plan: str) -> dict:
    """
    Devuelve el init_point del plan MP para redirigir al usuario al checkout.
    Usa preapproval_plan — el plan ya existe en MP, no se crea por usuario.

    Retorna: { "init_point": str }
    Lanza ValueError si el plan no tiene ID configurado.
    """
    plan_id = PLAN_IDS.get(plan, "")
    if not plan_id:
        raise ValueError(
            f"Plan '{plan}' no tiene MP_PLAN_ID configurado. "
            f"Creá el plan en MP y configurá la variable de entorno."
        )

    # El init_point del plan ya incluye el link de checkout.
    # Agregamos external_reference como query param para identificar al usuario en el webhook.
    init_point = (
        f"https://www.mercadopago.com.ar/subscriptions/checkout"
        f"?preapproval_plan_id={plan_id}"
        f"&external_reference={usuario_id}:{plan}"
    )

    log.info(f"[MP] init_point generado para usuario_id={usuario_id} plan={plan}")
    return {"init_point": init_point}


def cancelar_suscripcion(preapproval_id: str) -> bool:
    """Cancela una suscripción activa en MP."""
    resp = requests.patch(
        f"{MP_API}/preapproval/{preapproval_id}",
        json={"status": "cancelled"},
        headers=_headers(),
        timeout=15,
    )
    ok = resp.status_code in (200, 201)
    if not ok:
        log.error(f"[MP] Error cancelar suscripcion {preapproval_id}: {resp.status_code} {resp.text}")
    return ok


def obtener_suscripcion(preapproval_id: str) -> dict:
    """Consulta el estado de una suscripción de usuario en MP."""
    resp = requests.get(
        f"{MP_API}/preapproval/{preapproval_id}",
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def validar_firma_webhook(x_signature: str, x_request_id: str, data_id: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 que MP envía en el header x-signature.
    Formato del header: "ts=...,v1=..."
    """
    if not MP_WEBHOOK_SECRET:
        log.warning("[MP] MP_WEBHOOK_SECRET no configurado — firma NO verificada.")
        return True  # en dev sin secret, aceptamos

    try:
        parts = dict(p.split("=", 1) for p in x_signature.split(","))
        ts = parts.get("ts", "")
        v1 = parts.get("v1", "")
        template = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        digest = hmac.new(MP_WEBHOOK_SECRET.encode(), template.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, v1)
    except Exception as e:
        log.error(f"[MP] Error validando firma: {e}")
        return False
