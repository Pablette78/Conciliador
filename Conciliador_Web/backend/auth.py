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

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

# --- Config ---
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
TOKEN_EXPIRE_HORAS = int(os.getenv("TOKEN_EXPIRE_HORAS", "8"))
DB_PATH = os.getenv("AUTH_DB_PATH", "./usuarios.db")
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Lógica de placeholders: Postgres usa %s, SQLite usa ?
PL = "%s" if DATABASE_URL else "?"

# --- Pydantic models ---
class LoginRequest(BaseModel):
    username: str
    password: str

class UsuarioCreate(BaseModel):
    username: str
    password: str
    rol: str = "usuario"

class UsuarioUpdate(BaseModel):
    new_username: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None

class UsuarioOut(BaseModel):
    id: int
    username: str
    rol: str
    activo: bool
    creado_en: str
    ultimo_login: Optional[str]

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
                    id          SERIAL PRIMARY KEY,
                    username    TEXT UNIQUE NOT NULL,
                    password_h  TEXT NOT NULL,
                    rol         TEXT NOT NULL DEFAULT 'usuario',
                    activo      INTEGER NOT NULL DEFAULT 1,
                    creado_en   TEXT NOT NULL,
                    ultimo_login TEXT
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT UNIQUE NOT NULL,
                    password_h  TEXT NOT NULL,
                    rol         TEXT NOT NULL DEFAULT 'usuario',
                    activo      INTEGER NOT NULL DEFAULT 1,
                    creado_en   TEXT NOT NULL,
                    ultimo_login TEXT
                )
            """)

        # Admin por defecto si no existe ningún usuario
        cursor.execute("SELECT 1 FROM usuarios LIMIT 1")
        existe = cursor.fetchone()
        
        if not existe:
            admin_pass = os.getenv("ADMIN_PASSWORD", "admin1234")
            q = f"INSERT INTO usuarios (username, password_h, rol, activo, creado_en) VALUES ({PL}, {PL}, 'admin', 1, {PL})"
            cursor.execute(q, ("admin", pwd_ctx.hash(admin_pass), datetime.utcnow().isoformat()))
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
            
        cursor.execute(f"SELECT * FROM usuarios WHERE username = {PL} AND activo = 1", (username,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
        )
    return dict(row)

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
        row = cursor.fetchone()

    if not row or not pwd_ctx.verify(data.password, row["password_h"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )

    if not row["activo"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado.",
        )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE usuarios SET ultimo_login = {PL} WHERE username = {PL}",
            (datetime.utcnow().isoformat(), data.username)
        )

    token = crear_token(data.username, row["rol"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {"username": row["username"], "rol": row["rol"]}
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
    )

@router.get("/usuarios", dependencies=[Depends(require_admin)])
async def listar_usuarios():
    with get_db() as conn:
        if DATABASE_URL:
            cursor = conn.cursor(cursor_factory=__import__('psycopg2.extras').extras.RealDictCursor)
        else:
            cursor = conn.cursor()
        cursor.execute("SELECT id, username, rol, activo, creado_en, ultimo_login FROM usuarios ORDER BY id")
        rows = cursor.fetchall()
    return [UsuarioOut(**dict(r)) for r in rows]

@router.post("/usuarios", dependencies=[Depends(require_admin)], status_code=201)
async def crear_usuario(data: UsuarioCreate):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            q = f"INSERT INTO usuarios (username, password_h, rol, activo, creado_en) VALUES ({PL}, {PL}, {PL}, 1, {PL})"
            cursor.execute(q, (data.username, pwd_ctx.hash(data.password), data.rol, datetime.utcnow().isoformat()))
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
            params.append(pwd_ctx.hash(data.password))
        if data.rol:
            sets.append(f"rol = {PL}")
            params.append(data.rol)
        if data.activo is not None:
            sets.append(f"activo = {PL}")
            params.append(1 if data.activo else 0)

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
