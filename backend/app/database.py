"""
Configuração e gerenciamento do banco de dados
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool, AsyncAdaptedQueuePool
from app.config import settings
from app.models import Base

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


async def init_db():
    """Cria todas as tabelas se não existirem"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
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
