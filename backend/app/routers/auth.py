"""
Router de autenticação - Login, Register, gerenciamento de usuários e admin.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.database import AsyncSessionLocal
from app.auth import (
    LoginRequest,
    RegisterRequest,
    ChangePasswordRequest,
    AdminResetPasswordRequest,
    TokenResponse,
    UserInfo,
    UserDetail,
    UserUpdateRequest,
    authenticate_user,
    create_user,
    create_access_token,
    get_current_user,
    get_current_admin,
    get_user_by_username,
    get_all_users,
    get_user_by_id,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """
    Autentica o usuário e retorna um token JWT.
    """
    async with AsyncSessionLocal() as session:
        user = await authenticate_user(session, request.username, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(data={"sub": user.username})

        return TokenResponse(
            access_token=access_token,
            expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
            username=user.username,
        )


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest) -> TokenResponse:
    """
    Registra um novo usuário no sistema.
    Requer ALLOW_REGISTRATION=true ou pode ser desabilitado.
    """
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registro de novos usuários está desabilitado",
        )

    async with AsyncSessionLocal() as session:
        existing = await get_user_by_username(session, request.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuário já existe",
            )

        user = await create_user(
            session,
            username=request.username,
            password=request.password,
            full_name=request.full_name,
        )
        await session.commit()

        access_token = create_access_token(data={"sub": user.username})

        return TokenResponse(
            access_token=access_token,
            expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
            username=user.username,
        )


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """
    Retorna informações do usuário autenticado.
    """
    return current_user


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Altera a senha do usuário autenticado.
    Requer a senha atual para confirmação.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user_by_username(session, current_user.username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        if not verify_password(request.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Senha atual incorreta",
            )

        user.hashed_password = hash_password(request.new_password)
        await session.commit()

    return {"message": "Senha alterada com sucesso"}


# ─── Admin Endpoints ──────────────────────────────────────────────────────────


@router.get("/admin/users", response_model=list[UserDetail])
async def list_users(
    current_user: UserInfo = Depends(get_current_admin),
):
    """
    Lista todos os usuários do sistema.
    Requer permissão de administrador.
    """
    async with AsyncSessionLocal() as session:
        users = await get_all_users(session)
        return [
            UserDetail(
                id=u.id,
                username=u.username,
                full_name=u.full_name or "",
                is_admin=u.is_admin,
                is_active=u.is_active,
                created_at=u.created_at.isoformat() if u.created_at else "",
                updated_at=u.updated_at.isoformat() if u.updated_at else "",
            )
            for u in users
        ]


@router.put("/admin/users/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    current_user: UserInfo = Depends(get_current_admin),
):
    """
    Atualiza dados de um usuário (ativar/desativar, promover admin, alterar nome).
    Requer permissão de administrador.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        # Impedir que admin desative a si mesmo
        if user.username == current_user.username and request.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você não pode desativar sua própria conta",
            )

        # Impedir que admin remova seu próprio papel de admin
        if user.username == current_user.username and request.is_admin is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você não pode remover seu próprio papel de administrador",
            )

        if request.full_name is not None:
            user.full_name = request.full_name
        if request.is_active is not None:
            user.is_active = request.is_active
        if request.is_admin is not None:
            user.is_admin = request.is_admin

        await session.commit()
        await session.refresh(user)

        return UserDetail(
            id=user.id,
            username=user.username,
            full_name=user.full_name or "",
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else "",
            updated_at=user.updated_at.isoformat() if user.updated_at else "",
        )


@router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    request: AdminResetPasswordRequest,
    current_user: UserInfo = Depends(get_current_admin),
):
    """
    Reseta a senha de um usuário.
    Requer permissão de administrador.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        user.hashed_password = hash_password(request.new_password)
        await session.commit()

    return {"message": f"Senha do usuário '{user.username}' resetada com sucesso"}


@router.post("/admin/users/create", response_model=UserDetail)
async def admin_create_user(
    request: RegisterRequest,
    current_user: UserInfo = Depends(get_current_admin),
):
    """
    Cria um novo usuário (admin pode criar mesmo com registro desabilitado).
    Requer permissão de administrador.
    """
    async with AsyncSessionLocal() as session:
        existing = await get_user_by_username(session, request.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuário já existe",
            )

        user = await create_user(
            session,
            username=request.username,
            password=request.password,
            full_name=request.full_name,
        )
        await session.commit()
        await session.refresh(user)

        return UserDetail(
            id=user.id,
            username=user.username,
            full_name=user.full_name or "",
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else "",
            updated_at=user.updated_at.isoformat() if user.updated_at else "",
        )


@router.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    current_user: UserInfo = Depends(get_current_admin),
):
    """
    Remove um usuário do sistema.
    Requer permissão de administrador.
    Não permite excluir a si mesmo.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        if user.username == current_user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você não pode excluir sua própria conta",
            )

        await session.delete(user)
        await session.commit()

    return {"message": f"Usuário '{user.username}' removido com sucesso"}
