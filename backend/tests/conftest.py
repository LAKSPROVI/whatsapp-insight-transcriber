"""
Fixtures compartilhadas para testes do backend.
"""
import os
import sys
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

# Configurar variáveis de ambiente ANTES de importar qualquer módulo da app
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-fake-12345")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-only")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "TestAdmin123")
os.environ.setdefault("ALLOW_REGISTRATION", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-minimum-32-chars!!")

# Agora importar módulos da app
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.auth import create_access_token, hash_password, UserInfo, get_current_user, get_current_user_or_token


# ─── Fixture: Engine e DB ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine():
    """Cria um engine SQLite in-memory para testes."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Sessão de banco de dados de teste (SQLite in-memory)."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


# ─── Fixture: App e Client ───────────────────────────────────────────────────

@pytest_asyncio.fixture
async def app(db_engine):
    """Instância FastAPI isolada para testes, com DB override e lifespan simplificado."""
    from app.main import create_app
    from app.database import get_db

    # Substituir lifespan para evitar startup pesado (ensure_admin_user, orchestrator, redis)
    @asynccontextmanager
    async def _test_lifespan(_app):
        yield

    _app = create_app(lifespan_override=_test_lifespan)

    async def _override_get_db():
        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _override_get_current_user():
        return UserInfo(id="test-admin-id", username="admin", full_name="Admin", is_admin=True)

    _app.dependency_overrides[get_db] = _override_get_db
    _app.dependency_overrides[get_current_user] = _override_get_current_user
    _app.dependency_overrides[get_current_user_or_token] = _override_get_current_user
    yield _app
    _app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    """AsyncClient para testes de integração com app ASGI isolada."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ─── Fixture: Auth Token ─────────────────────────────────────────────────────

@pytest.fixture
def auth_token():
    """Token JWT válido para testes."""
    token = create_access_token(data={"sub": "admin"})
    return token


@pytest.fixture
def auth_headers(auth_token):
    """Headers de autenticação prontos para uso."""
    return {"Authorization": f"Bearer {auth_token}"}


# ─── Fixture: Dados de Exemplo ───────────────────────────────────────────────

@pytest.fixture
def sample_conversation_data():
    """Dados de uma conversa de exemplo."""
    return {
        "session_id": "test-session-001",
        "original_filename": "WhatsApp Chat - Grupo Teste.zip",
        "upload_path": "/tmp/test-session-001.zip",
        "extract_path": "/tmp/media/test-session-001",
        "conversation_name": "Grupo Teste",
        "participants": ["João", "Maria", "Pedro"],
        "total_messages": 100,
        "total_media": 15,
    }


@pytest.fixture
def sample_messages_data():
    """Mensagens de exemplo."""
    return [
        {
            "sequence_number": 1,
            "timestamp": datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc),
            "sender": "João",
            "original_text": "Bom dia pessoal!",
            "media_type": "text",
        },
        {
            "sequence_number": 2,
            "timestamp": datetime(2026, 1, 1, 8, 1, tzinfo=timezone.utc),
            "sender": "Maria",
            "original_text": "Bom dia João!",
            "media_type": "text",
        },
        {
            "sequence_number": 3,
            "timestamp": datetime(2026, 1, 1, 8, 5, tzinfo=timezone.utc),
            "sender": "Pedro",
            "original_text": None,
            "media_type": "audio",
            "media_filename": "audio-001.opus",
            "transcription": "Olá pessoal, tudo bem?",
        },
    ]


# ─── Fixture: Mock Claude Service ────────────────────────────────────────────

@pytest.fixture
def mock_claude_service():
    """Mock do ClaudeService para testes sem chamar API externa."""
    mock = MagicMock()

    async def _fake_chat_with_context(*args, **kwargs):
        for chunk in ["Resposta ", "de teste"]:
            yield chunk

    mock.chat_with_context = _fake_chat_with_context
    mock._call_claude_with_retry = AsyncMock()
    mock.model = "claude-test"
    return mock


# ─── Fixture: Mock Redis ─────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Mock do Redis para testes sem Redis real."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    return mock
