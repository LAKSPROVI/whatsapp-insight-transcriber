"""
API Endpoints - Upload e Gerenciamento de Conversas
"""
import os
import uuid
import logging
import asyncio
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.config import settings
from app.database import get_db
from app.models import Conversation, Message, ProcessingStatus
from app.schemas import (
    ConversationResponse, ConversationListItem, UploadResponse,
    ProcessingProgress, MessageResponse
)
from app.services.conversation_processor import ConversationProcessor
from app.dependencies import get_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])

# ─── Estado Global de Progresso ──────────────────────────────────────────────
_progress_store: dict = {}  # session_id -> progress data


@router.post("/upload", response_model=UploadResponse)
async def upload_conversation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    orchestrator=Depends(get_orchestrator),
):
    """
    Recebe um arquivo .zip de exportação do WhatsApp.
    Inicia o processamento assíncrono em background.
    """
    # Validar arquivo
    if not file.filename.endswith(".zip"):
        raise HTTPException(400, "Apenas arquivos .zip são aceitos")

    # Verificar tamanho
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"Arquivo muito grande. Máximo: {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB")

    # Criar session ID único
    session_id = str(uuid.uuid4())

    # Salvar arquivo
    upload_path = settings.UPLOAD_DIR / f"{session_id}.zip"
    with open(upload_path, "wb") as f:
        f.write(content)

    logger.info(f"Upload recebido: {file.filename} ({len(content)} bytes) -> session: {session_id}")

    # Criar conversa preliminar no DB
    conversation = Conversation(
        session_id=session_id,
        original_filename=file.filename,
        upload_path=str(upload_path),
        extract_path=str(settings.MEDIA_DIR / session_id),
        status=ProcessingStatus.UPLOADING,
        progress=0.02,
        progress_message="Upload concluído, iniciando processamento...",
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    # Inicializar progresso
    _progress_store[session_id] = {
        "status": ProcessingStatus.UPLOADING,
        "progress": 0.02,
        "message": "Upload concluído",
    }

    # Processar em background
    background_tasks.add_task(
        _process_in_background,
        session_id=session_id,
        zip_path=str(upload_path),
        original_filename=file.filename,
        orchestrator=orchestrator,
    )

    return UploadResponse(
        session_id=session_id,
        conversation_id=str(conversation.id),
        message="Upload realizado com sucesso. Processamento iniciado.",
        status=ProcessingStatus.UPLOADING,
    )


async def _process_in_background(
    session_id: str,
    zip_path: str,
    original_filename: str,
    orchestrator,
):
    """Função executada em background para processar a conversa"""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        processor = ConversationProcessor(db, orchestrator)

        async def on_progress(conv: Conversation):
            _progress_store[session_id] = {
                "status": conv.status,
                "progress": conv.progress,
                "message": conv.progress_message,
                "total_messages": conv.total_messages,
            }

        try:
            await processor.process_upload(
                zip_path=zip_path,
                original_filename=original_filename,
                session_id=session_id,
                progress_callback=on_progress,
            )
        except Exception as e:
            logger.error(f"Erro no processamento background de {session_id}: {e}", exc_info=True)
            _progress_store[session_id] = {
                "status": ProcessingStatus.FAILED,
                "progress": 0,
                "message": f"Erro: {str(e)}",
            }


@router.get("/progress/{session_id}", response_model=ProcessingProgress)
async def get_progress(session_id: str, db: AsyncSession = Depends(get_db)):
    """Retorna o progresso atual do processamento"""
    # Buscar no banco para dados mais precisos
    stmt = select(Conversation).where(Conversation.session_id == session_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if not conv:
        # Verificar store em memória
        progress = _progress_store.get(session_id)
        if not progress:
            raise HTTPException(404, "Sessão não encontrada")
        return ProcessingProgress(
            session_id=session_id,
            status=progress["status"],
            progress=progress["progress"],
            progress_message=progress.get("message"),
        )

    return ProcessingProgress(
        session_id=session_id,
        status=conv.status,
        progress=conv.progress,
        progress_message=conv.progress_message,
        total_messages=conv.total_messages,
    )


@router.get("/", response_model=List[ConversationListItem])
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Lista todas as conversas processadas"""
    stmt = select(Conversation).order_by(desc(Conversation.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    return conversations


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retorna detalhes completos de uma conversa"""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(404, "Conversa não encontrada")

    return conv


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: str,
    skip: int = 0,
    limit: int = 100,
    media_only: bool = False,
    sender: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Retorna as mensagens de uma conversa com paginação"""
    from app.models import MediaType
    stmt = select(Message).where(Message.conversation_id == conversation_id)

    if media_only:
        stmt = stmt.where(Message.media_type != MediaType.TEXT)

    if sender:
        stmt = stmt.where(Message.sender == sender)

    stmt = stmt.order_by(Message.sequence_number).offset(skip).limit(limit)
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return messages


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove uma conversa e todos seus dados"""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(404, "Conversa não encontrada")

    # Limpar arquivos
    import shutil
    if conv.extract_path and os.path.exists(conv.extract_path):
        shutil.rmtree(conv.extract_path, ignore_errors=True)
    if conv.upload_path and os.path.exists(conv.upload_path):
        os.remove(conv.upload_path)

    await db.delete(conv)
    await db.commit()

    return {"message": "Conversa removida com sucesso"}
