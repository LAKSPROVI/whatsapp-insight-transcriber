"""
Arquivo principal da aplicação FastAPI - WhatsApp Insight Transcriber
"""
import logging
import os
import platform
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings, validate_settings
from app.database import init_db
from app.dependencies import get_orchestrator, shutdown_orchestrator
from app.routers import conversations, chat, export, auth

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialização e cleanup da aplicação"""
    logger.info(f"🚀 Iniciando {settings.APP_NAME} v{settings.APP_VERSION}")

    # Validar configurações críticas
    validate_settings(settings)
    logger.info("✅ Configurações validadas")

    # Inicializar banco de dados
    await init_db()
    logger.info("✅ Banco de dados inicializado")

    # Inicializar orquestrador com 20 agentes
    orchestrator = await get_orchestrator()
    logger.info(f"✅ Orquestrador iniciado com {settings.MAX_AGENTS} agentes de IA")

    yield

    # Cleanup
    logger.info("🛑 Encerrando serviços...")
    await shutdown_orchestrator()
    logger.info("✅ Aplicação encerrada")


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## WhatsApp Insight Transcriber API
    
    Plataforma avançada de transcrição e análise de conversas do WhatsApp.
    
    ### Funcionalidades:
    - 📤 Upload e processamento de arquivos ZIP do WhatsApp
    - 🤖 20 agentes de IA paralelos para transcrição ultrarrápida
    - 🎵 Transcrição de áudios
    - 🖼️ Visão computacional para imagens (descrição + OCR)
    - 🎬 Análise de vídeos (frames + áudio)
    - 💬 Chat RAG sobre a conversa transcrita
    - 📊 Análise de sentimento, palavras-chave, contradições
    - 📄 Exportação profissional para PDF e DOCX
    """,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ─── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["Content-Disposition", "Content-Length"],
    max_age=600,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(export.router, prefix="/api")


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "model": settings.CLAUDE_MODEL,
        "max_agents": settings.MAX_AGENTS,
    }


@app.get("/api/health/detailed")
async def detailed_health_check():
    """Health check detalhado com verificações de infraestrutura."""
    checks: dict = {}
    overall_status = "healthy"

    # 1. Verificar banco de dados
    try:
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "message": "Conexão ativa"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}
        overall_status = "degraded"

    # 2. Verificar disponibilidade de disco
    try:
        disk_usage = shutil.disk_usage("/")
        free_gb = disk_usage.free / (1024 ** 3)
        total_gb = disk_usage.total / (1024 ** 3)
        used_percent = ((disk_usage.total - disk_usage.free) / disk_usage.total) * 100
        checks["disk"] = {
            "status": "ok" if free_gb > 1.0 else "warning",
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "used_percent": round(used_percent, 1),
        }
        if free_gb < 0.5:
            checks["disk"]["status"] = "critical"
            overall_status = "degraded"
    except Exception as e:
        checks["disk"] = {"status": "error", "message": str(e)}

    # 3. Verificar uso de memória
    try:
        import resource
        mem_usage_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        checks["memory"] = {
            "status": "ok",
            "process_rss_mb": round(mem_usage_mb, 2),
        }
    except (ImportError, Exception):
        # resource não disponível no Windows; usar psutil se existir
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / (1024 * 1024)
            checks["memory"] = {
                "status": "ok" if mem_mb < 2048 else "warning",
                "process_rss_mb": round(mem_mb, 2),
            }
        except (ImportError, Exception):
            checks["memory"] = {
                "status": "unknown",
                "message": "psutil não disponível",
            }

    # 4. Verificar configuração
    config_ok = True
    config_issues: list[str] = []

    if not settings.ANTHROPIC_API_KEY:
        config_issues.append("ANTHROPIC_API_KEY não configurada")
        config_ok = False
    if not settings.JWT_SECRET_KEY:
        config_issues.append("JWT_SECRET_KEY não configurada")
        config_ok = False
    if settings.SECRET_KEY == "change-me-in-production-super-secret-key":
        config_issues.append("SECRET_KEY usando valor padrão")

    checks["config"] = {
        "status": "ok" if config_ok else "warning",
        "api_key_configured": bool(settings.ANTHROPIC_API_KEY),
        "jwt_configured": bool(settings.JWT_SECRET_KEY),
        "issues": config_issues if config_issues else None,
    }

    if not config_ok:
        overall_status = "degraded"

    # 5. Verificar diretórios
    checks["storage"] = {
        "upload_dir_exists": settings.UPLOAD_DIR.exists(),
        "media_dir_exists": settings.MEDIA_DIR.exists(),
    }

    return {
        "status": overall_status,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "checks": checks,
    }


@app.get("/")
async def root():
    return {
        "message": f"Bem-vindo ao {settings.APP_NAME}",
        "docs": "/api/docs",
        "health": "/api/health",
    }
