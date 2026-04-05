"""
Módulo de autenticação JWT para o WhatsApp Insight Transcriber
Persistência em banco de dados SQLAlchemy.
"""
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any, Tuple

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ─── Segurança ────────────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ─── Schemas de Auth ──────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1, max_length=128, repr=False)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError("Username deve conter apenas letras, números, _, . ou -")
        return v.strip()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128, repr=False)
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


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Nova senha deve conter ao menos uma letra maiúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Nova senha deve conter ao menos um número")
        return v


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Nova senha deve conter ao menos uma letra maiúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Nova senha deve conter ao menos um número")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str


class UserInfo(BaseModel):
    id: str
    username: str
    full_name: str = ""
    is_admin: bool = False
    role: str = "analyst"  # viewer, analyst, auditor, admin


class UserDetail(BaseModel):
    id: str
    username: str
    full_name: str = ""
    is_admin: bool = False
    is_active: bool = True
    created_at: str
    updated_at: str


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


# ─── Password Helpers ─────────────────────────────────────────────────────────


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# ─── JWT Helpers ──────────────────────────────────────────────────────────────


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "iat": datetime.now(timezone.utc),
    })
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


# ─── Database Operations ─────────────────────────────────────────────────────


async def get_user_by_username(session: AsyncSession, username: str):
    """Busca um usuário pelo username no banco de dados."""
    from app.models import User
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str):
    """Busca um usuário pelo ID."""
    from app.models import User
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_all_users(session: AsyncSession):
    """Retorna todos os usuários."""
    from app.models import User
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


async def create_user(
    session: AsyncSession,
    username: str,
    password: str,
    full_name: str = "",
    is_admin: bool = False,
):
    """Cria um novo usuário no banco de dados."""
    from app.models import User
    user = User(
        username=username,
        hashed_password=hash_password(password),
        full_name=full_name,
        is_admin=is_admin,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(session: AsyncSession, username: str, password: str):
    """Autentica um usuário verificando username e senha."""
    user = await get_user_by_username(session, username)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def ensure_admin_user() -> None:
    """Garante que o usuário admin existe no banco. Chamado no startup."""
    async with AsyncSessionLocal() as session:
        try:
            existing = await get_user_by_username(session, settings.ADMIN_USERNAME)
            if not existing:
                await create_user(
                    session,
                    username=settings.ADMIN_USERNAME,
                    password=settings.ADMIN_PASSWORD,
                    full_name="Administrador",
                    is_admin=True,
                )
                await session.commit()
                logger.info(f"Admin user '{settings.ADMIN_USERNAME}' criado no banco de dados")
            else:
                # Atualizar senha do admin se mudou no .env
                if not verify_password(settings.ADMIN_PASSWORD, existing.hashed_password):
                    existing.hashed_password = hash_password(settings.ADMIN_PASSWORD)
                    existing.is_admin = True
                    await session.commit()
                    logger.info(f"Senha do admin '{settings.ADMIN_USERNAME}' atualizada")
                elif not existing.is_admin:
                    existing.is_admin = True
                    await session.commit()
                    logger.info(f"User '{settings.ADMIN_USERNAME}' promovido a admin")
                else:
                    logger.info(f"Admin user '{settings.ADMIN_USERNAME}' já existe no banco")
        except Exception as e:
            await session.rollback()
            logger.error(f"Erro ao garantir admin user: {e}")
            raise


# ─── User Cache ───────────────────────────────────────────────────────────────
_user_cache: Dict[str, Tuple[UserInfo, float]] = {}
USER_CACHE_TTL = 60.0


# ─── FastAPI Dependencies ─────────────────────────────────────────────────────


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

    # Check cache first
    now = time.time()
    if username in _user_cache:
        cached_user, cached_at = _user_cache[username]
        if now - cached_at < USER_CACHE_TTL:
            return cached_user

    async with AsyncSessionLocal() as session:
        user = await get_user_by_username(session, username)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            # Remove from cache if deactivated
            _user_cache.pop(username, None)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário desativado. Contate o administrador.",
            )

        user_info = UserInfo(
            id=user.id,
            username=user.username,
            full_name=user.full_name or "",
            is_admin=user.is_admin,
            role=getattr(user, "role", "analyst") if hasattr(user, "role") else ("admin" if user.is_admin else "analyst"),
        )

    _user_cache[username] = (user_info, now)
    return user_info


async def get_current_user_from_token(token: str) -> UserInfo:
    """Resolve usuário a partir de token bearer bruto."""
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

    async with AsyncSessionLocal() as session:
        user = await get_user_by_username(session, username)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário desativado. Contate o administrador.",
            )

        return UserInfo(
            id=user.id,
            username=user.username,
            full_name=user.full_name or "",
            is_admin=user.is_admin,
            role=getattr(user, "role", "analyst") if hasattr(user, "role") else ("admin" if user.is_admin else "analyst"),
        )


async def get_current_user_or_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    token: Optional[str] = Query(default=None),
) -> UserInfo:
    """Aceita Bearer header ou token em query string para recursos de mídia."""
    raw_token = credentials.credentials if credentials is not None else token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await get_current_user_from_token(raw_token)


async def get_current_admin(
    current_user: UserInfo = Depends(get_current_user),
) -> UserInfo:
    """Dependency que verifica se o usuário é admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return current_user


def require_role(*allowed_roles: str):
    """Factory de dependency que exige role especifica.
    
    Uso: Depends(require_role("auditor", "admin"))
    """
    async def _check_role(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
        if current_user.is_admin:
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso restrito. Roles permitidas: {', '.join(allowed_roles)}",
            )
        return current_user
    return _check_role


def apply_owner_filter(stmt, model, current_user: UserInfo):
    """Aplica filtro por owner para usuários não-admin."""
    if current_user.is_admin:
        return stmt
    return stmt.where(model.owner_id == current_user.id)


def ensure_owner_access(resource, current_user: UserInfo) -> None:
    """Valida se o recurso pertence ao usuário atual quando ele não é admin."""
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado")
    owner_id = getattr(resource, "owner_id", None)
    if not current_user.is_admin and owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado")


async def log_audit_event(
    session: AsyncSession,
    *,
    action: str,
    current_user: Optional[UserInfo] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> None:
    from app.models import AuditLog
    from sqlalchemy import select, desc
    import hashlib, json

    user_agent = None
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")[:500] if request.headers else None

    # Hash-chained audit: find prev_hash from last entry
    prev_hash = "0" * 64
    try:
        last_stmt = select(AuditLog.event_hash).order_by(desc(AuditLog.created_at)).limit(1)
        last_result = await session.execute(last_stmt)
        last_hash = last_result.scalar_one_or_none()
        if last_hash:
            prev_hash = last_hash
    except Exception:
        pass  # First entry or table not migrated yet

    # Compute event hash
    event_data = json.dumps({
        "action": action,
        "user_id": current_user.id if current_user else None,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "prev_hash": prev_hash,
    }, sort_keys=True)
    event_hash = hashlib.sha256(event_data.encode()).hexdigest()

    session.add(
        AuditLog(
            user_id=current_user.id if current_user else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            prev_hash=prev_hash,
            event_hash=event_hash,
        )
    )
    await session.flush()
