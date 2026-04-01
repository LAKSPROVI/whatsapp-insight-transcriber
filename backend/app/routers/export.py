"""
API Endpoints - Exportação PDF/DOCX e Servir Mídias
"""
import os
import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Conversation, Message, ProcessingStatus
from app.schemas import ExportRequest
from app.services.export_service import PDFExporter, DOCXExporter
from app.auth import get_current_user, UserInfo

logger = logging.getLogger(__name__)
router = APIRouter(tags=["export"])


@router.post("/conversations/{conversation_id}/export")
async def export_conversation(
    conversation_id: str,
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Exporta a transcrição completa para PDF ou DOCX.
    Retorna URL para download do arquivo gerado.
    """
    # Buscar conversa
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(404, "Conversa não encontrada")

    if conv.status != ProcessingStatus.COMPLETED:
        raise HTTPException(400, "A conversa ainda está sendo processada")

    # Buscar mensagens
    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_number)
    )
    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()

    options = {
        "include_media_descriptions": request.include_media_descriptions,
        "include_sentiment_analysis": request.include_sentiment_analysis,
        "include_summary": request.include_summary,
        "include_statistics": request.include_statistics,
    }

    # Gerar arquivo
    try:
        if request.format == "pdf":
            exporter = PDFExporter()
            file_bytes = exporter.generate(conv, messages, options)
            filename = f"transcricao_{conv.conversation_name or conv.id}_{conv.date_start.strftime('%Y%m%d') if conv.date_start else 'sem_data'}.pdf"
            content_type = "application/pdf"
        else:  # docx
            exporter = DOCXExporter()
            file_bytes = exporter.generate(conv, messages, options)
            filename = f"transcricao_{conv.conversation_name or conv.id}_{conv.date_start.strftime('%Y%m%d') if conv.date_start else 'sem_data'}.docx"
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        # Sanitizar nome do arquivo
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
        filename = filename.replace(" ", "_")

    except Exception as e:
        logger.error(f"Erro ao gerar exportação: {e}", exc_info=True)
        raise HTTPException(500, f"Erro ao gerar arquivo: {str(e)}")

    # Retornar diretamente o arquivo
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(file_bytes)),
        },
    )


@router.get("/media/{conversation_id}/{filename}")
async def serve_media(
    conversation_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Serve arquivos de mídia originais.
    Utilizado pelos botões 'Visualizar' e 'Baixar' na interface.
    """
    # Validar filename contra path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Nome de arquivo inválido")

    # Buscar mensagem com este arquivo
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.media_filename == filename,
        )
    )
    result = await db.execute(stmt)
    msg = result.scalar_one_or_none()

    if not msg or not msg.media_path:
        # Tentar localizar diretamente no diretório de mídia
        from app.config import settings
        direct_path = settings.MEDIA_DIR / conversation_id / filename
        if not direct_path.exists():
            # Busca recursiva
            media_dir = settings.MEDIA_DIR / conversation_id
            if media_dir.exists():
                for f in media_dir.rglob(filename):
                    if f.is_file():
                        return FileResponse(
                            str(f),
                            filename=filename,
                        )
            raise HTTPException(404, "Arquivo de mídia não encontrado")

        return FileResponse(str(direct_path), filename=filename)

    if not os.path.exists(msg.media_path):
        raise HTTPException(404, "Arquivo de mídia não encontrado no servidor")

    return FileResponse(
        msg.media_path,
        filename=filename,
    )


@router.get("/media/{conversation_id}/{filename}/info")
async def get_media_info(
    conversation_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Retorna metadados de um arquivo de mídia específico"""
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.media_filename == filename,
        )
    )
    result = await db.execute(stmt)
    msg = result.scalar_one_or_none()

    if not msg:
        raise HTTPException(404, "Mídia não encontrada")

    return {
        "filename": filename,
        "media_type": msg.media_type.value,
        "metadata": msg.media_metadata,
        "transcription": msg.transcription,
        "description": msg.description,
        "ocr_text": msg.ocr_text,
        "url": msg.media_url,
    }


@router.get("/agents/status")
async def get_agents_status(
    current_user: UserInfo = Depends(get_current_user),
):
    """Retorna status de todos os agentes de IA"""
    try:
        from app.dependencies import get_orchestrator_instance
        orch = get_orchestrator_instance()
        if orch:
            return orch.get_status()
    except Exception:
        pass
    return {"message": "Orquestrador não disponível"}
