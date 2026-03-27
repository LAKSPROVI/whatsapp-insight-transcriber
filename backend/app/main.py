"""
Arquivo principal da aplicação FastAPI - WhatsApp Insight Transcriber
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.dependencies import get_orchestrator, shutdown_orchestrator
from app.routers import conversations, chat, export

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
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ─── Routers ──────────────────────────────────────────────────────────────────
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


@app.get("/")
async def root():
    return {
        "message": f"Bem-vindo ao {settings.APP_NAME}",
        "docs": "/api/docs",
        "health": "/api/health",
    }
