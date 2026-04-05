"""
Configuração e gerenciamento do banco de dados
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from app.config import settings
from app.models import Base

logger = logging.getLogger(__name__)

_is_sqlite = "sqlite" in settings.DATABASE_URL

# ─── Engine Assíncrono ────────────────────────────────────────────────────────
_engine_kwargs: dict = {
    "echo": settings.DEBUG,
}

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool
else:
    # PostgreSQL: pool configurado para produção
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20
    _engine_kwargs["pool_timeout"] = 30
    _engine_kwargs["pool_recycle"] = 1800  # Reciclar conexões a cada 30 min
    _engine_kwargs["pool_pre_ping"] = True  # Detectar conexões mortas

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# ─── Session Factory ──────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Cria todas as tabelas se não existirem.
    
    NOTE: This is for development only. In production, use run_migrations()
    which applies Alembic migrations for proper schema versioning.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _get_sync_database_url(database_url: str) -> str:
    from sqlalchemy.engine import make_url
    url = make_url(database_url)
    driver = url.drivername.split("+")[0]
    return str(url.set(drivername=driver))


def _should_run_migrations_on_startup() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False

    raw_value = os.getenv("RUN_DB_MIGRATIONS_ON_STARTUP", "true").strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def run_migrations() -> None:
    """Run Alembic migrations programmatically for production deployments.
    
    This ensures the database schema is up-to-date using versioned migrations
    instead of create_all(), which doesn't handle schema changes.
    """
    from alembic.config import Config
    from alembic import command

    try:
        backend_dir = Path(__file__).resolve().parent.parent
        alembic_ini_path = backend_dir / "alembic.ini"
        alembic_script_path = backend_dir / "alembic"

        if not alembic_ini_path.exists() or not alembic_script_path.exists():
            raise FileNotFoundError("Alembic não configurado no diretório backend/")

        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(alembic_script_path))
        alembic_cfg.set_main_option("sqlalchemy.url", _get_sync_database_url(settings.DATABASE_URL))
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        logger.warning("Could not run migrations: %s", e)
        raise


async def bootstrap_db() -> str:
    """Inicializa o schema preferindo migrações versionadas quando habilitadas."""
    if _should_run_migrations_on_startup():
        await asyncio.to_thread(run_migrations)
        return "migrations"

    await init_db()
    return "create_all"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection para sessão de banco de dados"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
