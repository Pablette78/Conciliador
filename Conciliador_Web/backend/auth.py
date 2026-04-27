"""
Modulo de autenticacion con JWT, bcrypt y soporte SQLite/PostgreSQL.

Roles:
  admin   - acceso total
  usuario - conciliar y descargar
"""

import os
import sqlite3
import secrets
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel
from mailer import (enviar_verificacion, enviar_notificacion_upgrade,
                    enviar_reset_password, enviar_aprobacion_usuario)

# --- Config ---
SECRET_KEY         = os.getenv("JWT_SECRET", "conciliador-secret-key-permanente-2024")
ALGORITHM          = "HS256"
TOKEN_EXPIRE_HORAS = int(os.getenv("TOKEN_EXPIRE_HORAS", "24"))
DB_PATH            = os.getenv("AUTH_DB_PATH", "./usuarios.db")
DATABASE_URL       = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
FRONTEND_URL       = os.getenv("FRONTEND_URL", "https://contaflex.ar")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False

bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/auth", tags=["Autenticacion"])

PL = "%s" if DATABASE_URL else "?"

# --- Limites por plan ---
PLAN_LIMITS = {"Free": 5, "Individual": 20, "Estudio": 100}

# --- Modelos Pydantic ---
class LoginRequest(BaseModel):
    username: str
    password: str

class UsuarioCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    rol: str = "usuario"
    plan: str = "Free"

class UsuarioUpdate(BaseModel):
    new_username: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None
    vencimiento_prueba: Optional[str] = None
    plan: Optional[str] = None
    limite_mensual: Optional[int] = None
    email_verificado: Optional[bool] = None

class UsuarioOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    rol: str
    activo: bool
    creado_en: str
    ultimo_login: Optional[str] = None
    vencimiento_prueba: Optional[str] = None
    plan: str
    limite_mensual: int
    usos_mes_actual: int
    ultimo_mes_uso: Optional[str] = None
    email_verificado: bool
    plan_pendiente: Optional[str] = None

# --- Base de datos ---
@contextmanager
def get_db():
    if DATABASE_URL:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

def _cursor(conn):
    """Devuelve cursor con acceso por nombre de columna en ambos motores."""
    if DATABASE_URL:
        from psycopg2.extras import RealDictCursor
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()

def init_db() -> None:
    from logger import get_logger
    l = get_logger("auth")
    if DATABASE_URL:
        l.info("[DATABASE] Configurada: POSTGRES")
    else:
        l.error("[DATABASE] ADVERTENCIA: DATABASE_URL no detectada. Usando SQLITE.")

    with get_db() as conn:
        cur = _cursor(conn)

        if DATABASE_URL:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id                           SERIAL PRIMARY KEY,
                    username                     TEXT UNIQUE NOT NULL,
                    password_h                   TEXT NOT NULL,
                    email                        TEXT,
                    rol                          TEXT NOT NULL DEFAULT 'usuario',
                    activo                       INTEGER NOT NULL DEFAULT 1,
                    creado_en                    TEXT NOT NULL,
                    ultimo_login                 TEXT,
                    vencimiento_prueba           TEXT,
                    plan                         TEXT DEFAULT 'Free',
                    limite_mensual               INTEGER DEFAULT 5,
                    usos_mes_actual              INTEGER DEFAULT 0,
                    ultimo_mes_uso               TEXT,
                    email_verificado             INTEGER DEFAULT 0,
                    verificacion_token           TEXT,
                    reset_token                  TEXT,
                    plan_pendiente               TEXT,
                    token_aprobacion_suscripcion TEXT
                )
            """)
            for col, typedef in [
                ("email",                        "TEXT"),
                ("plan",                         "TEXT DEFAULT 'Free'"),
                ("limite_mensual",               "INTEGER DEFAULT 5"),
                ("usos_mes_actual",              "INTEGER DEFAULT 0"),
                ("ultimo_mes_uso",               "TEXT"),
                ("email_verificado",             "INTEGER DEFAULT 0"),
                ("verificacion_token",           "TEXT"),
                ("reset_token",                  "TEXT"),
                ("plan_pendiente",               "TEXT"),
                ("token_aprobacion_suscripcion", "TEXT"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS {col} {typedef}")
                except Exception:
                    pass
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    username           TEXT UNIQUE NOT NULL,
                    password_h         TEXT NOT NULL,
                    email              TEXT,
                    rol                TEXT NOT NULL DEFAULT 'usuario',
                    activo             INTEGER NOT NULL DEFAULT 1,
                    creado_en          TEXT NOT NULL,
                    ultimo_login       TEXT,
                    vencimiento_prueba TEXT
                )
            """)
            for col, typedef in [
                ("email",                        "TEXT"),
                ("vencimiento_prueba",           "TEXT"),
                ("plan",                         "TEXT DEFAULT 'Free'"),
                ("limite_mensual",               "INTEGER DEFAULT 5"),
                ("usos_mes_actual",              "INTEGER DEFAULT 0"),
                ("ultimo_mes_uso",               "TEXT"),
                ("email_verificado",             "INTEGER DEFAULT 0"),
                ("verificacion_token",           "TEXT"),
                ("reset_token",                  "TEXT"),
                ("plan_pendiente",               "TEXT"),
                ("token_aprobacion_suscripcion", "TEXT"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {typedef}")
                except Exception:
                    pass
            cur.execute("UPDATE usuarios SET plan='Estudio', limite_mensual=100 WHERE plan='Free' OR plan IS NULL")

        cur.execute("SELECT 1 FROM usuarios LIMIT 1")
        if not cur.fetchone():
            admin_pass = os.getenv("ADMIN_PASSWORD", "admin1234")
            cur.execute(
                f"INSERT INTO usuarios (username, password_h, rol, activo, creado_en, email_verificado) VALUES ({PL},{PL},'admin',1,{PL},1)",
                ("admin", hash_password(admin_pass), datetime.utcnow().isoformat())
            )
            print("[AUTH] Usuario admin creado.")

# --- JWT ---
def crear_token(username: str, rol: str) -> str:
    payload = {
        "sub": username, "rol": rol,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HORAS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token invalido o expirado.",
                            headers={"WWW-Authenticate": "Bearer"})

# --- Dependencias ---
async def get_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Se requiere autenticacion.",
                            headers={"WWW-Authenticate": "Bearer"})
    payload  = decodificar_token(credentials.credentials)
    username = payload.get("sub")

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(f"SELECT * FROM usuarios WHERE username = {PL}", (username,))
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Usuario no encontrado.")

    # Bloquear si el email no fue verificado (solo usuarios con email registrado)
    if row.get("email") and not row["email_verificado"] and row["rol"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Debes verificar tu email antes de operar. Revisa tu casilla.")

    # Vencimiento de prueba
    if row.get("vencimiento_prueba"):
        vencimiento = datetime.fromisoformat(row["vencimiento_prueba"])
        if datetime.utcnow() > vencimiento:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Tu periodo de prueba de 14 dias ha vencido.")

    user_dict = dict(row)

    # Reseteo mensual (lazy)
    mes_actual = datetime.utcnow().strftime("%Y-%m")
    if user_dict.get("ultimo_mes_uso") != mes_actual:
        with get_db() as conn_reset:
            cur2 = _cursor(conn_reset)
            cur2.execute(
                f"UPDATE usuarios SET usos_mes_actual=0, ultimo_mes_uso={PL} WHERE id={PL}",
                (mes_actual, user_dict["id"])
            )
        user_dict["usos_mes_actual"] = 0
        user_dict["ultimo_mes_uso"]  = mes_actual

    return user_dict


async def require_admin(usuario: dict = Depends(get_usuario_actual)) -> dict:
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Se requieren permisos de administrador.")
    return usuario

# --- Endpoints ---

@router.post("/login")
async def login(data: LoginRequest):
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(f"SELECT * FROM usuarios WHERE username = {PL}", (data.username,))
        usuario = cur.fetchone()

    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Usuario o contrasena incorrectos.")

    if not verify_password(data.password, usuario["password_h"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Usuario o contrasena incorrectos.")

    is_activo = usuario.get("activo")
    if is_activo is not None and not is_activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Usuario desactivado.")

    # Bloquear login si email no verificado
    if usuario.get("email") and not usuario["email_verificado"] and usuario["rol"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Debes verificar tu email antes de ingresar. Revisa tu casilla.")

    if usuario.get("vencimiento_prueba"):
        vencimiento = datetime.fromisoformat(usuario["vencimiento_prueba"])
        if datetime.utcnow() > vencimiento:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Tu periodo de prueba ha vencido.")

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(f"UPDATE usuarios SET ultimo_login={PL} WHERE username={PL}",
                    (datetime.utcnow().isoformat(), data.username))

    token = crear_token(data.username, usuario["rol"])
    return {"access_token": token, "token_type": "bearer",
            "usuario": {"username": usuario["username"], "rol": usuario["rol"]}}


@router.get("/me")
async def me(usuario: dict = Depends(get_usuario_actual)):
    return UsuarioOut(
        id=usuario["id"],
        username=usuario["username"],
        email=usuario.get("email"),
        rol=usuario["rol"],
        activo=bool(usuario["activo"]) if usuario.get("activo") is not None else True,
        creado_en=usuario["creado_en"],
        ultimo_login=usuario.get("ultimo_login"),
        vencimiento_prueba=usuario.get("vencimiento_prueba"),
        plan=usuario.get("plan") or "Free",
        limite_mensual=usuario.get("limite_mensual") or 5,
        usos_mes_actual=usuario.get("usos_mes_actual") or 0,
        ultimo_mes_uso=usuario.get("ultimo_mes_uso"),
        email_verificado=bool(usuario.get("email_verificado", 0)),
        plan_pendiente=usuario.get("plan_pendiente"),
    )


@router.get("/usuarios", dependencies=[Depends(require_admin)])
async def listar_usuarios():
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            "SELECT id, username, email, rol, activo, creado_en, ultimo_login, "
            "vencimiento_prueba, plan, limite_mensual, usos_mes_actual, ultimo_mes_uso, "
            "email_verificado, plan_pendiente FROM usuarios ORDER BY id"
        )
        rows = cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d.setdefault("email", None)
        d.setdefault("email_verificado", False)
        d.setdefault("plan_pendiente", None)
        d.setdefault("plan", "Free")
        d.setdefault("limite_mensual", 5)
        d.setdefault("usos_mes_actual", 0)
        d.setdefault("ultimo_mes_uso", None)
        d["email_verificado"] = bool(d["email_verificado"])
        d["activo"] = bool(d["activo"]) if d.get("activo") is not None else True
        result.append(UsuarioOut(**d))
    return result


@router.post("/usuarios", status_code=201)
async def crear_usuario(data: UsuarioCreate):
    """
    Registro publico. Si hay email → crea activo=0 y manda verificacion.
    Si no hay email (creado por admin) → activo=1, email_verificado=1.
    """
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            token_verif  = str(uuid.uuid4())
            plan_pend    = data.plan if data.plan != "Free" else None
            token_aprob  = str(uuid.uuid4()) if plan_pend else None
            tiene_email  = bool(data.email and data.email.strip())
            activo_val   = 0 if tiene_email else 1
            verif_val    = 0 if tiene_email else 1

            cur.execute(
                f"INSERT INTO usuarios "
                f"(username, password_h, email, rol, activo, creado_en, plan, limite_mensual, "
                f"email_verificado, verificacion_token, plan_pendiente, token_aprobacion_suscripcion) "
                f"VALUES ({PL},{PL},{PL},{PL},{PL},{PL},{PL},{PL},{PL},{PL},{PL},{PL})",
                (data.username, hash_password(data.password), data.email or None,
                 data.rol, activo_val, datetime.utcnow().isoformat(),
                 "Free", 5, verif_val, token_verif, plan_pend, token_aprob)
            )

        if tiene_email:
            enviar_verificacion(data.email.strip(), token_verif)

    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409,
                                detail=f"El usuario '{data.username}' ya existe.")
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "username": data.username,
            "pending_verification": bool(data.email)}


@router.put("/usuarios/{username}")
async def actualizar_usuario(username: str, data: UsuarioUpdate,
                              usuario_actual: dict = Depends(get_usuario_actual)):
    es_admin        = usuario_actual["rol"] == "admin"
    es_mismo_usuario = usuario_actual["username"] == username
    if not es_admin and not es_mismo_usuario:
        raise HTTPException(status_code=403, detail="Sin permiso para editar este usuario.")
    if not es_admin and (data.rol is not None or data.activo is not None):
        raise HTTPException(status_code=403, detail="Solo un admin puede cambiar rol o estado.")

    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(f"SELECT * FROM usuarios WHERE username={PL}", (username,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        sets, params = [], []
        if data.new_username:
            sets.append(f"username={PL}"); params.append(data.new_username)
        if data.password:
            sets.append(f"password_h={PL}"); params.append(hash_password(data.password))
        if data.rol:
            sets.append(f"rol={PL}"); params.append(data.rol)
        if data.activo is not None:
            sets.append(f"activo={PL}"); params.append(1 if data.activo else 0)
        if data.vencimiento_prueba is not None:
            sets.append(f"vencimiento_prueba={PL}")
            params.append(data.vencimiento_prueba if data.vencimiento_prueba != "" else None)
        if data.plan is not None:
            limite = PLAN_LIMITS.get(data.plan, 5)
            sets.append(f"plan={PL}"); params.append(data.plan)
            sets.append(f"limite_mensual={PL}"); params.append(limite)
        if data.email_verificado is not None:
            sets.append(f"email_verificado={PL}"); params.append(1 if data.email_verificado else 0)

        if sets:
            params.append(username)
            cur.execute(f"UPDATE usuarios SET {', '.join(sets)} WHERE username={PL}", params)
    return {"ok": True}


@router.delete("/usuarios/{username}", dependencies=[Depends(require_admin)])
async def eliminar_usuario(username: str, admin: dict = Depends(require_admin)):
    if username == admin["username"]:
        raise HTTPException(status_code=400, detail="No podes eliminarte a vos mismo.")
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(f"DELETE FROM usuarios WHERE username={PL}", (username,))
    return {"ok": True}


# --- Verificacion de Email ---
@router.get("/verificar")
async def verificar_email(token: str):
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(f"SELECT * FROM usuarios WHERE verificacion_token={PL}", (token,))
        row = cur.fetchone()
        if not row:
            return HTMLResponse("<h2>Token invalido o expirado.</h2>", status_code=400)

        plan_pendiente = row.get("plan_pendiente")

        # Marcar email como verificado
        cur.execute(
            f"UPDATE usuarios SET email_verificado=1, verificacion_token=NULL WHERE verificacion_token={PL}",
            (token,)
        )

        # Si plan Free → activar directamente
        if not plan_pendiente:
            cur.execute(f"UPDATE usuarios SET activo=1 WHERE id={PL}", (row["id"],))
            msg_extra = "Ya podes iniciar sesion."
            is_free = True
        else:
            # Plan pago → notificar a Pablo, mantener activo=0
            email_usuario = row.get("email") or row["username"]
            enviar_notificacion_upgrade(
                row["username"], email_usuario,
                plan_pendiente, row["token_aprobacion_suscripcion"]
            )
            msg_extra = f"Tu solicitud de plan <b>{plan_pendiente}</b> esta siendo procesada. Te avisaremos por email cuando este lista."
            is_free = False

    color  = "#10b981" if is_free else "#f59e0b"
    titulo = "Email verificado!" if is_free else "Email verificado — Pendiente de aprobacion"
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>ContaFlex</title>
    <style>body{{font-family:Arial,sans-serif;background:#0a0e1a;color:#f1f5f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
    .box{{background:#141c2e;border:1px solid #1e293b;border-radius:12px;padding:48px;max-width:480px;text-align:center;}}
    h2{{color:{color};}}a{{color:#60a5fa;}}
    .btn{{display:inline-block;margin-top:24px;padding:14px 28px;background:#3b82f6;color:white;text-decoration:none;border-radius:8px;font-weight:bold;}}</style>
    </head>
    <body><div class="box">
      <h2>{titulo}</h2>
      <p>{msg_extra}</p>
      <a href="{FRONTEND_URL}" class="btn">Ir a ContaFlex</a>
    </div></body></html>
    """)


# --- Upgrade de plan (usuarios ya activos) ---
@router.post("/upgrade")
async def solicitar_upgrade(plan_solicitado: str, usuario: dict = Depends(get_usuario_actual)):
    if plan_solicitado not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail="Plan invalido.")
    if plan_solicitado == usuario["plan"]:
        raise HTTPException(status_code=400, detail="Ya tenes este plan.")

    token_aprob = str(uuid.uuid4())
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            f"UPDATE usuarios SET plan_pendiente={PL}, token_aprobacion_suscripcion={PL} WHERE id={PL}",
            (plan_solicitado, token_aprob, usuario["id"])
        )

    email_usuario = usuario.get("email") or usuario["username"]
    enviar_notificacion_upgrade(usuario["username"], email_usuario, plan_solicitado, token_aprob)
    return {"ok": True, "message": "Solicitud enviada. Recibirás un mail cuando sea aprobada."}


# --- Aprobacion de suscripcion ---
@router.get("/aprobar-suscripcion")
async def aprobar_suscripcion(token: str):
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(f"SELECT * FROM usuarios WHERE token_aprobacion_suscripcion={PL}", (token,))
        row = cur.fetchone()
        if not row:
            return HTMLResponse("<h2>Token de aprobacion no valido.</h2>", status_code=400)

        nuevo_plan   = row["plan_pendiente"]
        nuevo_limite = PLAN_LIMITS.get(nuevo_plan, 5)

        cur.execute(
            f"UPDATE usuarios SET plan={PL}, limite_mensual={PL}, activo=1, "
            f"plan_pendiente=NULL, token_aprobacion_suscripcion=NULL WHERE id={PL}",
            (nuevo_plan, nuevo_limite, row["id"])
        )

    # Notificar al usuario
    email_dest = row.get("email") or row["username"]
    enviar_aprobacion_usuario(email_dest, row["username"], nuevo_plan)

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>ContaFlex — Aprobacion</title>
    <style>body{{font-family:Arial,sans-serif;background:#0a0e1a;color:#f1f5f9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
    .box{{background:#141c2e;border:1px solid #1e293b;border-radius:12px;padding:48px;max-width:480px;text-align:center;}}
    h2{{color:#10b981;}}</style>
    </head>
    <body><div class="box">
      <h2>Suscripcion aprobada</h2>
      <p>El usuario <b>{row['username']}</b> fue activado con el plan <b>{nuevo_plan}</b>.</p>
      <p>Se le envio un email de confirmacion a {email_dest}.</p>
    </div></body></html>
    """)


# --- Recuperacion de contrasena ---
@router.post("/olvide-password")
async def solicitar_reset(username: str):
    """Acepta username O email."""
    token = str(uuid.uuid4())
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            f"SELECT username, email FROM usuarios WHERE username={PL} OR email={PL}",
            (username, username)
        )
        row = cur.fetchone()
        if not row:
            return {"ok": True, "message": "Si el usuario existe, recibirás instrucciones."}

        cur.execute(f"UPDATE usuarios SET reset_token={PL} WHERE username={PL}",
                    (token, row["username"]))

    dest = row.get("email") or row["username"]
    enviar_reset_password(dest, token)
    return {"ok": True, "message": "Email enviado."}


@router.post("/reset-password")
async def reset_password(token: str, nueva_pass: str):
    if len(nueva_pass) < 8:
        raise HTTPException(status_code=400, detail="Minimo 8 caracteres.")
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(f"SELECT username FROM usuarios WHERE reset_token={PL}", (token,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Token invalido o expirado.")
        cur.execute(
            f"UPDATE usuarios SET password_h={PL}, reset_token=NULL WHERE reset_token={PL}",
            (hash_password(nueva_pass), token)
        )
    return {"ok": True}
