"""
Módulo de autenticación con JWT, bcrypt y SQLite.

Roles:
  admin  - puede conciliar, descargar, y gestionar usuarios
  usuario - puede conciliar y descargar

Uso en rutas:
    from auth import get_usuario_actual, require_admin, router as auth_router

    # Ruta protegida (cualquier usuario autenticado)
    @app.get("/ruta", dependencies=[Depends(get_usuario_actual)])

    # Ruta solo admin
    @app.get("/admin", dependencies=[Depends(require_admin)])
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

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/auth", tags=["Autenticación"])


# --- Pydantic models ---
class LoginRequest(BaseModel):
    username: str
    password: str

class UsuarioCreate(BaseModel):
    username: str
    password: str
    rol: str = "usuario"   # "admin" o "usuario"

class UsuarioUpdate(BaseModel):
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
        conn.execute("""
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
        existe = conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone()
        if not existe:
            admin_pass = os.getenv("ADMIN_PASSWORD", "admin1234")
            conn.execute(
                """INSERT INTO usuarios (username, password_h, rol, activo, creado_en)
                   VALUES (?, ?, 'admin', 1, ?)""",
                ("admin", pwd_ctx.hash(admin_pass), datetime.utcnow().isoformat())
            )
            print(f"[AUTH] Usuario admin creado. Cambiá la contraseña después del primer login.")


def _row_to_dict(row) -> dict:
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
        row = conn.execute(
            "SELECT * FROM usuarios WHERE username = ? AND activo = 1", (username,)
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
        )
    return _row_to_dict(row)


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
        row = conn.execute(
            "SELECT * FROM usuarios WHERE username = ?", (data.username,)
        ).fetchone()

    if not row or not pwd_ctx.verify(data.password, row["password_h"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )

    if not row["activo"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado. Contactá al administrador.",
        )

    # Actualizar último login
    with get_db() as conn:
        conn.execute(
            "UPDATE usuarios SET ultimo_login = ? WHERE username = ?",
            (datetime.utcnow().isoformat(), data.username)
        )

    token = crear_token(data.username, row["rol"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRE_HORAS * 3600,
        "usuario": {
            "username": row["username"],
            "rol": row["rol"],
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
    )


# --- Gestión de usuarios (solo admin) ---
@router.get("/usuarios", dependencies=[Depends(require_admin)])
async def listar_usuarios():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, rol, activo, creado_en, ultimo_login FROM usuarios ORDER BY id"
        ).fetchall()
    return [UsuarioOut(**dict(r)) for r in rows]


@router.post("/usuarios", dependencies=[Depends(require_admin)], status_code=201)
async def crear_usuario(data: UsuarioCreate):
    if data.rol not in ("admin", "usuario"):
        raise HTTPException(status_code=400, detail="Rol inválido. Usar 'admin' o 'usuario'.")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")

    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO usuarios (username, password_h, rol, activo, creado_en)
                   VALUES (?, ?, ?, 1, ?)""",
                (data.username, pwd_ctx.hash(data.password), data.rol, datetime.utcnow().isoformat())
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"El usuario '{data.username}' ya existe.")

    return {"ok": True, "username": data.username, "rol": data.rol}


@router.put("/usuarios/{username}", dependencies=[Depends(require_admin)])
async def actualizar_usuario(username: str, data: UsuarioUpdate, admin: dict = Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        # No se puede desactivar al único admin
        if data.activo is False and row["rol"] == "admin":
            admins_activos = conn.execute(
                "SELECT COUNT(*) FROM usuarios WHERE rol='admin' AND activo=1"
            ).fetchone()[0]
            if admins_activos <= 1:
                raise HTTPException(status_code=400, detail="No podés desactivar al único administrador.")

        sets, params = [], []
        if data.password is not None:
            if len(data.password) < 6:
                raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")
            sets.append("password_h = ?")
            params.append(pwd_ctx.hash(data.password))
        if data.rol is not None:
            if data.rol not in ("admin", "usuario"):
                raise HTTPException(status_code=400, detail="Rol inválido.")
            sets.append("rol = ?")
            params.append(data.rol)
        if data.activo is not None:
            sets.append("activo = ?")
            params.append(1 if data.activo else 0)

        if sets:
            params.append(username)
            conn.execute(f"UPDATE usuarios SET {', '.join(sets)} WHERE username = ?", params)

    return {"ok": True, "username": username}


@router.delete("/usuarios/{username}", dependencies=[Depends(require_admin)])
async def eliminar_usuario(username: str, admin: dict = Depends(require_admin)):
    if username == admin["username"]:
        raise HTTPException(status_code=400, detail="No podés eliminar tu propio usuario.")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        conn.execute("DELETE FROM usuarios WHERE username = ?", (username,))

    return {"ok": True, "eliminado": username}
