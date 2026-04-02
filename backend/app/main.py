"""
Arquivo principal da aplicação FastAPI - WhatsApp Insight Transcriber
"""
import logging
import os
import platform
import shutil
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import settings, validate_settings
from app.database import init_db
from app.dependencies import get_orchestrator, shutdown_orchestrator
from app.routers import conversations, chat, export, auth, search, templates
from app.logging_config import setup_logging, RequestLoggingMiddleware, get_logger
from app.exceptions import (
    AppBaseException,
    ParserError,
    ProcessingError,
    APIError,
    CacheError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
)

# ─── Logging estruturado ──────────────────────────────────────────────────────
setup_logging()
logger = get_logger(__name__)


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

    # Garantir admin user no banco de dados
    from app.auth import ensure_admin_user
    await ensure_admin_user()
    logger.info("✅ Usuário admin verificado/criado no banco")

    # Inicializar orquestrador com 20 agentes
    orchestrator = await get_orchestrator()
    logger.info(f"✅ Orquestrador iniciado com {settings.MAX_AGENTS} agentes de IA")

    # Inicializar cache Redis (falha silenciosa se indisponível)
    from app.services.cache_service import _get_redis, get_cache_stats, close_redis
    await _get_redis()
    cache_stats = await get_cache_stats()
    if cache_stats.get("redis_connected"):
        logger.info("✅ Cache Redis conectado")
    else:
        logger.warning("⚠️ Cache Redis indisponível — aplicação funcionará sem cache")

    yield

    # Cleanup
    logger.info("🛑 Encerrando serviços...")
    await close_redis()
    await shutdown_orchestrator()
    logger.info("✅ Aplicação encerrada")


# ─── Tags Metadata ────────────────────────────────────────────────────────────
tags_metadata = [
    {
        "name": "auth",
        "description": "Autenticação e gerenciamento de usuários. Login, registro e informações do usuário autenticado.",
    },
    {
        "name": "conversations",
        "description": "Upload, processamento e gerenciamento de conversas do WhatsApp. Inclui upload de ZIP, acompanhamento de progresso, listagem e exclusão.",
    },
    {
        "name": "chat",
        "description": "Chat RAG (Retrieval Augmented Generation) sobre conversas transcritas. Permite fazer perguntas sobre o conteúdo usando IA.",
    },
    {
        "name": "export",
        "description": "Exportação de transcrições em múltiplos formatos (PDF, DOCX, XLSX, CSV, HTML, JSON) e acesso a arquivos de mídia.",
    },
    {
        "name": "search",
        "description": "Pesquisa full-text em mensagens e conversas com filtros avançados, suporte a regex, paginação e highlighting.",
    },
    {
        "name": "templates",
        "description": "Templates de análise pré-configurados (jurídico, comercial, RH, etc.) para análise especializada de conversas com IA.",
    },
    {
        "name": "health",
        "description": "Endpoints de monitoramento e saúde da aplicação.",
    },
]

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## WhatsApp Insight Transcriber API

Plataforma avançada de transcrição e análise de conversas do WhatsApp com IA.

### 🚀 Funcionalidades Principais

| Funcionalidade | Descrição |
|---|---|
| 📤 **Upload** | Upload e processamento de arquivos ZIP exportados do WhatsApp |
| 🤖 **20 Agentes IA** | Processamento paralelo ultrarrápido com múltiplos agentes |
| 🎵 **Transcrição de Áudio** | Transcrição automática de mensagens de voz e áudio |
| 🖼️ **Visão Computacional** | Descrição de imagens + OCR (extração de texto) |
| 🎬 **Análise de Vídeo** | Extração de frames + transcrição de áudio de vídeos |
| 💬 **Chat RAG** | Chat inteligente sobre a conversa usando Retrieval Augmented Generation |
| 📊 **Analytics** | Análise de sentimento, palavras-chave, tópicos, contradições |
| 📄 **Exportação** | PDF, DOCX, Excel, CSV, HTML e JSON com formatação profissional |
| 🔍 **Pesquisa** | Full-text search com regex, filtros, paginação e highlighting |
| 📋 **Templates** | Análises pré-configuradas (jurídico, comercial, RH, etc.) |

### 🔐 Autenticação

Todos os endpoints (exceto health check) requerem autenticação via **JWT Bearer Token**.

1. Faça login em `POST /api/auth/login` com suas credenciais
2. Use o token retornado no header: `Authorization: Bearer <token>`

### 📖 Fluxo Típico

1. **Login** → `POST /api/auth/login`
2. **Upload** → `POST /api/conversations/upload` (arquivo .zip)
3. **Acompanhar** → `GET /api/conversations/progress/{session_id}`
4. **Explorar** → `GET /api/conversations/{id}`, `GET /api/chat/{id}/analytics`
5. **Chat IA** → `POST /api/chat/{id}/message`
6. **Exportar** → `POST /api/conversations/{id}/export`
""",
    contact={
        "name": "WhatsApp Insight Transcriber",
        "url": "https://github.com/whatsapp-insight-transcriber",
        "email": "suporte@whatsapp-insight.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=tags_metadata,
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
app.add_middleware(RequestLoggingMiddleware)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(templates.router, prefix="/api")


# ─── Exception Handlers ──────────────────────────────────────────────────────
@app.exception_handler(AppBaseException)
async def app_exception_handler(request: Request, exc: AppBaseException):
    """Handler para todas as exceções customizadas da aplicação."""
    logger.warning(
        f"Exceção de aplicação: {exc.__class__.__name__}",
        extra={
            "error_type": exc.__class__.__name__,
            "detail": exc.detail,
            "status_code": exc.status_code,
            "context": exc.context,
            "path": str(request.url),
            "method": request.method,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handler genérico para exceções não tratadas (500)."""
    logger.error(
        f"Exceção não tratada: {exc.__class__.__name__}: {str(exc)}",
        extra={
            "error_type": exc.__class__.__name__,
            "path": str(request.url),
            "method": request.method,
            "traceback": traceback.format_exc(),
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "detail": "Ocorreu um erro interno no servidor. Tente novamente mais tarde.",
            "status_code": 500,
            "context": {},
        },
    )


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["health"])
async def health_check():
    """
    Health check básico da aplicação.

    Retorna o status geral da aplicação, incluindo versão, modelo de IA
    configurado e estado do cache Redis.

    **Não requer autenticação.**

    **Exemplo de response (200):**
    ```json
    {
        "status": "healthy",
        "app": "WhatsApp Insight Transcriber",
        "version": "2.0.0",
        "model": "claude-sonnet-4-20250514",
        "max_agents": 20,
        "cache_connected": true
    }
    ```
    """
    from app.services.cache_service import get_cache_stats
    cache = await get_cache_stats()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "model": settings.CLAUDE_MODEL,
        "max_agents": settings.MAX_AGENTS,
        "cache_connected": cache.get("redis_connected", False),
    }


@app.get("/api/cache/stats", tags=["health"])
async def cache_stats():
    """
    Retorna estatísticas detalhadas do cache Redis.

    Inclui taxa de acerto (hit rate), número de chaves armazenadas,
    uso de memória e estado da conexão.

    **Não requer autenticação.**
    """
    from app.services.cache_service import get_cache_stats
    return await get_cache_stats()


@app.get("/api/health/detailed", tags=["health"])
async def detailed_health_check():
    """
    Health check detalhado com verificações de infraestrutura.

    Realiza verificações em todos os componentes do sistema:
    banco de dados, disco, memória, configuração, armazenamento e cache Redis.

    **Não requer autenticação.**

    **Exemplo de response (200):**
    ```json
    {
        "status": "healthy",
        "app": "WhatsApp Insight Transcriber",
        "version": "2.0.0",
        "timestamp": "2026-04-01T10:00:00Z",
        "platform": "Linux",
        "python_version": "3.12.0",
        "checks": {
            "database": {"status": "ok", "message": "Conexão ativa"},
            "disk": {"status": "ok", "free_gb": 50.5, "used_percent": 45.2},
            "memory": {"status": "ok", "process_rss_mb": 256.5},
            "config": {"status": "ok", "api_key_configured": true},
            "storage": {"upload_dir_exists": true, "media_dir_exists": true},
            "cache": {"status": "ok", "redis_connected": true}
        }
    }
    ```

    **Status possíveis:** `healthy`, `degraded`
    """
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
    if not settings.SECRET_KEY:
        config_issues.append("SECRET_KEY não configurada")
        config_ok = False

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

    # 6. Verificar Redis/Cache
    try:
        from app.services.cache_service import get_cache_stats
        cache_info = await get_cache_stats()
        checks["cache"] = {
            "status": "ok" if cache_info.get("redis_connected") else "warning",
            "redis_connected": cache_info.get("redis_connected", False),
            "hit_rate": cache_info.get("hit_rate", 0),
            "keys": cache_info.get("redis_keys", 0),
        }
    except Exception as e:
        checks["cache"] = {"status": "warning", "message": str(e)}

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
