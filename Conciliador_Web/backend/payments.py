"""
Integración Mercado Pago — suscripciones recurrentes (preapproval).

Variables de entorno requeridas:
  MP_ACCESS_TOKEN      — token activo (TEST-... o APP_USR-...)
  MP_WEBHOOK_SECRET    — secret para validar notificaciones (lo generás vos)

Variables opcionales:
  MP_PRECIO_INDIVIDUAL — precio ARS mensual plan Individual (default: 14900)
  MP_PRECIO_ESTUDIO    — precio ARS mensual plan Estudio    (default: 32500)
  API_URL              — URL pública del backend (para el back_url del checkout)
  FRONTEND_URL         — URL del frontend (para redirigir al usuario)
"""

import os
import hmac
import hashlib
import logging
import requests

log = logging.getLogger("payments")

MP_ACCESS_TOKEN   = os.getenv("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
API_URL           = os.getenv("API_URL", "https://conciliador-production-5319.up.railway.app")
FRONTEND_URL      = os.getenv("FRONTEND_URL", "https://contaflex.ar")

PLAN_PRECIOS = {
    "Individual": int(os.getenv("MP_PRECIO_INDIVIDUAL", "14900")),
    "Estudio":    int(os.getenv("MP_PRECIO_ESTUDIO",    "32500")),
}

MP_API = "https://api.mercadopago.com"

HEADERS = lambda: {
    "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "X-Idempotency-Key": "",  # se sobreescribe por llamada
}


def _headers(idempotency_key: str = "") -> dict:
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": idempotency_key,
    }


def crear_suscripcion(usuario_id: int, username: str, email: str, plan: str) -> dict:
    """
    Crea una suscripción preapproval en MP y devuelve:
      { "init_point": str, "preapproval_id": str }

    Lanza ValueError si el plan no tiene precio configurado.
    Lanza RuntimeError si MP responde con error.
    """
    if plan not in PLAN_PRECIOS:
        raise ValueError(f"Plan '{plan}' no tiene precio configurado para MP.")

    precio = PLAN_PRECIOS[plan]
    import uuid
    idempotency = str(uuid.uuid4())

    payload = {
        "reason": f"ContaFlex — Plan {plan}",
        "auto_recurring": {
            "frequency":      1,
            "frequency_type": "months",
            "transaction_amount": precio,
            "currency_id": "ARS",
        },
        "back_url": f"{FRONTEND_URL}/planes?suscripcion=ok",
        "payer_email": email,
        "external_reference": f"{usuario_id}:{plan}",
        "status": "pending",
    }

    resp = requests.post(
        f"{MP_API}/preapproval",
        json=payload,
        headers=_headers(idempotency),
        timeout=15,
    )

    if resp.status_code not in (200, 201):
        log.error(f"[MP] Error crear suscripcion: {resp.status_code} {resp.text}")
        raise RuntimeError(f"Mercado Pago error {resp.status_code}: {resp.text}")

    data = resp.json()
    log.info(f"[MP] Suscripcion creada: {data.get('id')} para usuario {username} plan {plan}")
    return {
        "init_point":    data["init_point"],
        "preapproval_id": data["id"],
    }


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
    """Consulta el estado de una suscripción en MP."""
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
    Retorna True si la firma es válida.

    Formato esperado del header: "ts=....,v1=...."
    """
    if not MP_WEBHOOK_SECRET:
        log.warning("[MP] MP_WEBHOOK_SECRET no configurado — firma NO verificada.")
        return True  # en dev sin secret, aceptamos

    try:
        parts = dict(p.split("=", 1) for p in x_signature.split(","))
        ts   = parts.get("ts", "")
        v1   = parts.get("v1", "")
        template = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        digest = hmac.new(MP_WEBHOOK_SECRET.encode(), template.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, v1)
    except Exception as e:
        log.error(f"[MP] Error validando firma: {e}")
        return False
