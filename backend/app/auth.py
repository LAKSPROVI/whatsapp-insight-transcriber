"""
Módulo de autenticação JWT para o WhatsApp Insight Transcriber
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator

from app.config import settings

logger = logging.getLogger(__name__)

# ─── Segurança ────────────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ─── Schemas de Auth ──────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError("Username deve conter apenas letras, números, _, . ou -")
        return v.strip()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError("Username deve conter apenas letras, números, _, . ou -")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Senha deve conter ao menos uma letra maiúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha deve conter ao menos um número")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str


class UserInfo(BaseModel):
    username: str
    full_name: str = ""
    is_admin: bool = False


# ─── Store de Usuários em Memória ─────────────────────────────────────────────
# Em produção, usar banco de dados. Aqui usamos dict em memória + admin via env.
_users_store: dict[str, dict] = {}


def _ensure_admin_user() -> None:
    """Garante que o usuário admin existe no store."""
    admin_user = settings.ADMIN_USERNAME
    if admin_user not in _users_store:
        _users_store[admin_user] = {
            "username": admin_user,
            "hashed_password": pwd_context.hash(settings.ADMIN_PASSWORD),
            "full_name": "Administrador",
            "is_admin": True,
        }


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt: str = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    try:
        payload: dict = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


# ─── Dependency para FastAPI ──────────────────────────────────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserInfo:
    """Dependency que extrai e valida o usuário do token JWT."""
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: Optional[str] = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: sem identificação de usuário",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _ensure_admin_user()
    user = _users_store.get(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserInfo(
        username=user["username"],
        full_name=user.get("full_name", ""),
        is_admin=user.get("is_admin", False),
    )


# ─── Funções de Login/Register ────────────────────────────────────────────────


def authenticate_user(username: str, password: str) -> Optional[dict]:
    _ensure_admin_user()
    user = _users_store.get(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def register_user(username: str, password: str, full_name: str = "") -> dict:
    _ensure_admin_user()
    if username in _users_store:
        raise ValueError("Usuário já existe")
    user = {
        "username": username,
        "hashed_password": hash_password(password),
        "full_name": full_name,
        "is_admin": False,
    }
    _users_store[username] = user
    return user
