"""
Módulo de autenticación con JWT, bcrypt y soporte para SQLite/PostgreSQL.

Roles:
  admin  - puede conciliar, descargar, y gestionar usuarios
  usuario - puede conciliar y descargar
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
from mailer import enviar_verificacion, enviar_notificacion_upgrade, enviar_reset_password

# --- Config ---
SECRET_KEY = os.getenv("JWT_SECRET", "conciliador-secret-key-permanente-2024")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HORAS = int(os.getenv("TOKEN_EXPIRE_HORAS", "24"))
DB_PATH = os.getenv("AUTH_DB_PATH", "./usuarios.db")
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

# Reemplazamos passlib por bcrypt directo por compatibilidad con Python 3.14
def hash_password(password: str) -> str:
    # bcrypt no acepta más de 72 bytes, truncamos por seguridad si fuera necesario
    pwd_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8')[:72], hashed_password.encode('utf-8'))
    except Exception:
        return False
bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Lógica de placeholders: Postgres usa %s, SQLite usa ?
PL = "%s" if DATABASE_URL else "?"

# --- Límites por plan (definido acá arriba para uso en toda la app) ---
PLAN_LIMITS = {
    "Free": 5,
    "Individual": 20,
    "Estudio": 100
}

# --- Pydantic models ---
class LoginRequest(BaseModel):
    username: str
    password: str

class UsuarioCreate(BaseModel):
    username: str
    password: str
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
    rol: str
    activo: bool
    creado_en: str
    ultimo_login: Optional[str]
    vencimiento_prueba: Optional[str]
    plan: str
    limite_mensual: int
    usos_mes_actual: int
    ultimo_mes_uso: Optional[str]
    email_verificado: bool
    plan_pendiente: Optional[str]

# --- Base de datos ---
@contextmanager
def get_db():
    if DATABASE_URL:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        # En Postgres usamos RealDictCursor para tener acceso por nombre de columna
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
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

def init_db() -> None:
    """Crea la tabla de usuarios si no existe e inserta el admin por defecto."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Dialecto SQL: Postgres usa SERIAL, SQLite usa AUTOINCREMENT
        if DATABASE_URL:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id                  SERIAL PRIMARY KEY,
                    username            TEXT UNIQUE NOT NULL,
                    password_h          TEXT NOT NULL,
                    rol                 TEXT NOT NULL DEFAULT 'usuario',
                    activo              INTEGER NOT NULL DEFAULT 1,
                    creado_en           TEXT NOT NULL,
                    ultimo_login        TEXT,
                    vencimiento_prueba  TEXT,
                    plan                TEXT DEFAULT 'Free',
                    limite_mensual      INTEGER DEFAULT 5,
                    usos_mes_actual     INTEGER DEFAULT 0,
                    ultimo_mes_uso      TEXT,
                    email_verificado    INTEGER DEFAULT 0,
                    verificacion_token  TEXT,
                    reset_token         TEXT,
                    plan_pendiente      TEXT,
                    token_aprobacion_suscripcion TEXT
                )
            """)
            print("[AUTH] Tabla 'usuarios' verificada/creada en Postgres con todas las columnas.")
            
            # Asegurar columnas en Postgres
            columnas_extra = [
                ("plan", "TEXT DEFAULT 'Free'"),
                ("limite_mensual", "INTEGER DEFAULT 5"),
                ("usos_mes_actual", "INTEGER DEFAULT 0"),
                ("ultimo_mes_uso", "TEXT"),
                ("email_verificado", "INTEGER DEFAULT 0"),
                ("verificacion_token", "TEXT"),
                ("reset_token", "TEXT"),
                ("plan_pendiente", "TEXT"),
                ("token_aprobacion_suscripcion", "TEXT")
            ]
            for col, type_def in columnas_extra:
                try:
                    cursor.execute(f"ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS {col} {type_def}")
                except Exception:
                    pass
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT UNIQUE NOT NULL,
                    password_h  TEXT NOT NULL,
                    rol         TEXT NOT NULL DEFAULT 'usuario',
                    activo      INTEGER NOT NULL DEFAULT 1,
                    creado_en   TEXT NOT NULL,
                    ultimo_login TEXT,
                    vencimiento_prueba TEXT
                )
            """)
            
            # Migración: Agregar nuevas columnas si no existen (SQLite)
            for col, type_def in [
                ("vencimiento_prueba", "TEXT"),
                ("plan", "TEXT DEFAULT 'Free'"),
                ("limite_mensual", "INTEGER DEFAULT 5"),
                ("usos_mes_actual", "INTEGER DEFAULT 0"),
                ("ultimo_mes_uso", "TEXT"),
                ("email_verificado", "INTEGER DEFAULT 0"),
                ("verificacion_token", "TEXT"),
                ("reset_token", "TEXT"),
                ("plan_pendiente", "TEXT"),
                ("token_aprobacion_suscripcion", "TEXT")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {type_def}")
                    print(f"[AUTH] Columna '{col}' agregada a SQLite.")
                except Exception:
                    pass # Ya existe
            
            # Migración: Usuarios existentes pasan a plan 'Estudio'
            cursor.execute("UPDATE usuarios SET plan = 'Estudio', limite_mensual = 100 WHERE plan = 'Free' OR plan IS NULL")

        # Admin por defecto si no existe ningún usuario
        cursor.execute("SELECT 1 FROM usuarios LIMIT 1")
        existe = cursor.fetchone()
        
        if not existe:
            admin_pass = os.getenv("ADMIN_PASSWORD", "admin1234")
            q = f"INSERT INTO usuarios (username, password_h, rol, activo, creado_en) VALUES ({PL}, {PL}, 'admin', 1, {PL})"
            cursor.execute(q, ("admin", hash_password(admin_pass), datetime.utcnow().isoformat()))
            print(f"[AUTH] Usuario admin creado configurado.")

def _row_to_dict(row) -> dict:
    if DATABASE_URL:
        # En psycopg2 con RealDictCursor ya es un dict-like o usamos una conversión
        return dict(row) if hasattr(row, 'keys') else row
    return dict(row)

# --- JWT ---
def crear_token(username: str, rol: str) -> str:
    payload = {
        "sub": username,
        "rol": rol,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HORAS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- Dependencies ---
async def get_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decodificar_token(credentials.credentials)
    username = payload.get("sub")

    with get_db() as conn:
        # Adaptación para Postgres (RealDictCursor) o SQLite (Row)
        if DATABASE_URL:
            from psycopg2.extras import RealDictRow
            cursor = conn.cursor(cursor_factory=__import__('psycopg2.extras').extras.RealDictCursor)
        else:
            cursor = conn.cursor()
            
        cursor.execute(f"SELECT * FROM usuarios WHERE username = {PL}", (username,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
        )
    
    # Validar verificación de email (opcional si querés bloquear uso)
    # if not row["email_verificado"] and row["rol"] != "admin":
    #     raise HTTPException(status_code=403, detail="Debés verificar tu email para operar.")
    
    # Validar vencimiento de prueba
    if row["vencimiento_prueba"]:
        vencimiento = datetime.fromisoformat(row["vencimiento_prueba"])
        if datetime.utcnow() > vencimiento:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu período de prueba de 14 días ha vencido. Contactanos para activar tu cuenta.",
            )

    user_dict = dict(row)
    
    # Lógica de Reseteo Mensual (Lazy Reset)
    mes_actual = datetime.utcnow().strftime("%Y-%m")
    if user_dict.get("ultimo_mes_uso") != mes_actual:
        with get_db() as conn_reset:
            cursor_reset = conn_reset.cursor()
            cursor_reset.execute(
                f"UPDATE usuarios SET usos_mes_actual = 0, ultimo_mes_uso = {PL} WHERE id = {PL}",
                (mes_actual, user_dict["id"])
            )
        user_dict["usos_mes_actual"] = 0
        user_dict["ultimo_mes_uso"] = mes_actual

    return user_dict


async def require_admin(usuario: dict = Depends(get_usuario_actual)) -> dict:
    if usuario["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador.",
        )
    return usuario

# --- Endpoints de autenticación ---
@router.post("/login")
async def login(data: LoginRequest):
    with get_db() as conn:
        if DATABASE_URL:
            cursor = conn.cursor(cursor_factory=__import__('psycopg2.extras').extras.RealDictCursor)
        else:
            cursor = conn.cursor()
            
        cursor.execute(f"SELECT * FROM usuarios WHERE username = {PL}", (data.username,))
        usuario = cursor.fetchone()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )
    
    if not verify_password(data.password, usuario["password_h"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )

    if not usuario["activo"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado.",
        )

    # Validar vencimiento de prueba en el login
    if usuario["vencimiento_prueba"]:
        vencimiento = datetime.fromisoformat(usuario["vencimiento_prueba"])
        if datetime.utcnow() > vencimiento:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu período de prueba ha vencido.",
            )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE usuarios SET ultimo_login = {PL} WHERE username = {PL}",
            (datetime.utcnow().isoformat(), data.username)
        )

    token = crear_token(data.username, usuario["rol"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "username": usuario["username"],
            "rol": usuario["rol"]
        }
    }

@router.get("/me")
async def me(usuario: dict = Depends(get_usuario_actual)):
    return UsuarioOut(
        id=usuario["id"],
        username=usuario["username"],
        rol=usuario["rol"],
        activo=bool(usuario["activo"]),
        creado_en=usuario["creado_en"],
        ultimo_login=usuario.get("ultimo_login"),
        vencimiento_prueba=usuario.get("vencimiento_prueba"),
        plan=usuario.get("plan") or "Free",
        limite_mensual=usuario.get("limite_mensual") or 5,
        usos_mes_actual=usuario.get("usos_mes_actual") or 0,
        ultimo_mes_uso=usuario.get("ultimo_mes_uso"),
        email_verificado=bool(usuario.get("email_verificado", 0)),
        plan_pendiente=usuario.get("plan_pendiente")
    )

@router.get("/usuarios", dependencies=[Depends(require_admin)])
async def listar_usuarios():
    with get_db() as conn:
        if DATABASE_URL:
            cursor = conn.cursor(cursor_factory=__import__('psycopg2.extras').extras.RealDictCursor)
        else:
            cursor = conn.cursor()
        cursor.execute("SELECT id, username, rol, activo, creado_en, ultimo_login, vencimiento_prueba, plan, limite_mensual, usos_mes_actual, ultimo_mes_uso, email_verificado, plan_pendiente FROM usuarios ORDER BY id")
        rows = cursor.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d.setdefault("email_verificado", False)
        d.setdefault("plan_pendiente", None)
        d.setdefault("plan", "Free")
        d.setdefault("limite_mensual", 5)
        d.setdefault("usos_mes_actual", 0)
        d.setdefault("ultimo_mes_uso", None)
        d["email_verificado"] = bool(d["email_verificado"])
        d["activo"] = bool(d["activo"])
        result.append(UsuarioOut(**d))
    return result

@router.post("/usuarios", status_code=201)
async def crear_usuario(data: UsuarioCreate):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            limite = PLAN_LIMITS.get(data.plan, 5)
            token_verif = str(uuid.uuid4())
            
            # Si el plan no es Free, marcar como pendiente de aprobación inicial
            plan_final = 'Free'
            limite_final = 5
            plan_pend = data.plan if data.plan != 'Free' else None
            token_aprob = str(uuid.uuid4()) if plan_pend else None

            q = f"INSERT INTO usuarios (username, password_h, rol, activo, creado_en, plan, limite_mensual, email_verificado, verificacion_token, plan_pendiente, token_aprobacion_suscripcion) VALUES ({PL}, {PL}, {PL}, 1, {PL}, {PL}, {PL}, 0, {PL}, {PL}, {PL})"
            cursor.execute(q, (data.username, hash_password(data.password), data.rol, datetime.utcnow().isoformat(), plan_final, limite_final, token_verif, plan_pend, token_aprob))
            
            # Enviar mail de verificación
            enviar_verificacion(data.username, token_verif)
            
            # Si hay plan pendiente, notificar a Pablo
            if plan_pend:
                enviar_notificacion_upgrade(data.username, plan_pend, token_aprob)
                
    except Exception as e:
        # Manejo genérico de duplicados (IntegrityError en ambos)
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"El usuario '{data.username}' ya existe.")
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "username": data.username}

@router.put("/usuarios/{username}")
async def actualizar_usuario(username: str, data: UsuarioUpdate, usuario_actual: dict = Depends(get_usuario_actual)):
    # Protección de permisos
    es_admin = usuario_actual["rol"] == 'admin'
    es_mismo_usuario = usuario_actual["username"] == username
    
    if not es_admin and not es_mismo_usuario:
        raise HTTPException(status_code=403, detail="No tenés permiso para editar este usuario.")
    
    # Si no es admin, no puede cambiarse el ROL ni el estado ACTIVO
    if not es_admin:
        if data.rol is not None or data.activo is not None:
            raise HTTPException(status_code=403, detail="Solo un administrador puede cambiar el rol o el estado activo.")

    with get_db() as conn:
        if DATABASE_URL:
            cursor = conn.cursor(cursor_factory=__import__('psycopg2.extras').extras.RealDictCursor)
        else:
            cursor = conn.cursor()
            
        cursor.execute(f"SELECT * FROM usuarios WHERE username = {PL}", (username,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        sets, params = [], []
        if data.new_username:
            sets.append(f"username = {PL}")
            params.append(data.new_username)
        if data.password:
            sets.append(f"password_h = {PL}")
            params.append(hash_password(data.password))
        if data.rol:
            sets.append(f"rol = {PL}")
            params.append(data.rol)
        if data.activo is not None:
            sets.append(f"activo = {PL}")
            params.append(1 if data.activo else 0)
        if data.vencimiento_prueba is not None:
            sets.append(f"vencimiento_prueba = {PL}")
            # Si se envía string vacío, se guarda como NULL para que sea permanente
            params.append(data.vencimiento_prueba if data.vencimiento_prueba != "" else None)

        if sets:
            params.append(username)
            q = f"UPDATE usuarios SET {', '.join(sets)} WHERE username = {PL}"
            cursor.execute(q, params)
    return {"ok": True}

@router.delete("/usuarios/{username}", dependencies=[Depends(require_admin)])
async def eliminar_usuario(username: str, admin: dict = Depends(require_admin)):
    if username == admin["username"]:
        raise HTTPException(status_code=400, detail="No podés eliminarte a vos mismo.")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM usuarios WHERE username = {PL}", (username,))
    return {"ok": True}

# --- Verificación de Email ---
@router.get("/verificar")
async def verificar_email(token: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT username FROM usuarios WHERE verificacion_token = {PL}", (token,))
        row = cursor.fetchone()
        if not row:
            return HTMLResponse("<h2>Token inválido o expirado.</h2>", status_code=400)
        
        cursor.execute(f"UPDATE usuarios SET email_verificado = 1, verificacion_token = NULL WHERE verificacion_token = {PL}", (token,))
    
    return HTMLResponse("<h2>¡Email verificado con éxito! Ya podés usar ContaFlex.</h2><p><a href='/'>Ir al sitio</a></p>")

# --- Upgrade (Aprobación) ---

@router.post("/upgrade")
async def solicitar_upgrade(plan_solicitado: str, usuario: dict = Depends(get_usuario_actual)):
    if plan_solicitado not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail="Plan inválido.")
    
    if plan_solicitado == usuario["plan"]:
        raise HTTPException(status_code=400, detail="Ya tenés este plan.")

    token_aprob = str(uuid.uuid4())
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE usuarios SET plan_pendiente = {PL}, token_aprobacion_suscripcion = {PL} WHERE id = {PL}",
            (plan_solicitado, token_aprob, usuario["id"])
        )
    
    # Notificar a Pablo
    enviar_notificacion_upgrade(usuario["username"], plan_solicitado, token_aprob)
    
    return {"ok": True, "message": "Solicitud enviada. Recibirás un mail cuando sea aprobada."}

@router.get("/aprobar-suscripcion")
async def aprobar_suscripcion(token: str):
    with get_db() as conn:
        cursor = conn.cursor()
        # En Postgres necesitamos manejar el cursor para dict access si usamos la lógica de auth.py
        if DATABASE_URL:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(f"SELECT * FROM usuarios WHERE token_aprobacion_suscripcion = {PL}", (token,))
        row = cursor.fetchone()
        if not row:
            return HTMLResponse("<h2>Token de aprobación no válido.</h2>", status_code=400)
        
        nuevo_plan = row["plan_pendiente"]
        nuevo_limite = PLAN_LIMITS.get(nuevo_plan, 5)
        
        cursor.execute(
            f"UPDATE usuarios SET plan = {PL}, limite_mensual = {PL}, plan_pendiente = NULL, token_aprobacion_suscripcion = NULL WHERE id = {PL}",
            (nuevo_plan, nuevo_limite, row["id"])
        )
    
    return HTMLResponse(f"<h2>Suscripción aprobada para {row['username']} al plan {nuevo_plan}.</h2>")

# --- Password Reset ---
@router.post("/olvide-password")
async def solicitar_reset(username: str):
    token = str(uuid.uuid4())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM usuarios WHERE username = {PL}", (username,))
        if not cursor.fetchone():
            # No revelamos si el email existe o no por seguridad
            return {"ok": True, "message": "Si el email existe, recibirás instrucciones."}
        
        cursor.execute(f"UPDATE usuarios SET reset_token = {PL} WHERE username = {PL}", (token, username))
    
    enviar_reset_password(username, token)
    return {"ok": True, "message": "Email enviado."}

@router.post("/reset-password")
async def reset_password(token: str, nueva_pass: str):
    if len(nueva_pass) < 8:
        raise HTTPException(status_code=400, detail="Mínimo 8 caracteres.")
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT username FROM usuarios WHERE reset_token = {PL}", (token,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Token inválido o expirado.")
        
        cursor.execute(
            f"UPDATE usuarios SET password_h = {PL}, reset_token = NULL WHERE reset_token = {PL}",
            (hash_password(nueva_pass), token)
        )
    return {"ok": True}
