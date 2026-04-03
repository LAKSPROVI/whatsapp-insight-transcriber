"""
API Endpoints - Exportação PDF/DOCX/XLSX/CSV/HTML/JSON e Servir Mídias.

Permite exportar conversas transcritas em múltiplos formatos profissionais,
servir arquivos de mídia originais e consultar status dos agentes de IA.
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
from app.services.export_service import (
    PDFExporter, DOCXExporter, ExcelExporter, CSVExporter, HTMLExporter, JSONExporter
)
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
    Exporta a transcrição completa de uma conversa em múltiplos formatos.

    Gera um arquivo para download contendo a transcrição formatada profissionalmente.
    Opções configuráveis para incluir descrições de mídia, análise de sentimento,
    resumo e estatísticas.

    **Formatos suportados:** `pdf`, `docx`, `xlsx`, `csv`, `html`, `json`

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    Content-Type: application/json
    ```

    **Exemplo de request:**
    ```json
    {
        "format": "pdf",
        "include_media_descriptions": true,
        "include_sentiment_analysis": true,
        "include_summary": true,
        "include_statistics": true
    }
    ```

    **Response:** Arquivo binário com headers de download.
    ```
    Content-Type: application/pdf
    Content-Disposition: attachment; filename="transcricao_Grupo_20260101.pdf"
    ```

    **Erros possíveis:**
    - **404 Not Found**: Conversa não encontrada.
    - **400 Bad Request**: Conversa ainda está sendo processada.
    - **422 Unprocessable Entity**: Formato não suportado.
    - **500 Internal Server Error**: Erro ao gerar o arquivo de exportação.
    - **401 Unauthorized**: Token ausente ou inválido.
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

    date_suffix = conv.date_start.strftime('%Y%m%d') if conv.date_start else 'sem_data'
    base_name = conv.conversation_name or conv.id

    # Mapa de formatos
    FORMAT_MAP = {
        "pdf": {
            "exporter": PDFExporter,
            "ext": "pdf",
            "content_type": "application/pdf",
        },
        "docx": {
            "exporter": DOCXExporter,
            "ext": "docx",
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        "xlsx": {
            "exporter": ExcelExporter,
            "ext": "xlsx",
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
        "csv": {
            "exporter": CSVExporter,
            "ext": "csv",
            "content_type": "text/csv; charset=utf-8",
        },
        "html": {
            "exporter": HTMLExporter,
            "ext": "html",
            "content_type": "text/html; charset=utf-8",
        },
        "json": {
            "exporter": JSONExporter,
            "ext": "json",
            "content_type": "application/json; charset=utf-8",
        },
    }

    fmt_config = FORMAT_MAP.get(request.format)
    if not fmt_config:
        raise HTTPException(422, f"Formato não suportado: {request.format}")

    # Gerar arquivo
    try:
        exporter = fmt_config["exporter"]()
        file_bytes = exporter.generate(conv, messages, options)
        filename = f"transcricao_{base_name}_{date_suffix}.{fmt_config['ext']}"
        content_type = fmt_config["content_type"]

        # Sanitizar nome do arquivo
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
        filename = filename.replace(" ", "_")

    except Exception as e:
        logger.error(f"Erro ao gerar exportação ({request.format}): {e}", exc_info=True)
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
    Serve arquivos de mídia originais de uma conversa.

    Retorna o arquivo de mídia (imagem, áudio, vídeo, documento) associado
    a uma mensagem. Utilizado pelos botões 'Visualizar' e 'Baixar' na interface.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Response:** Arquivo binário com Content-Type apropriado ao tipo de mídia.

    **Erros possíveis:**
    - **400 Bad Request**: Nome de arquivo inválido (tentativa de path traversal).
    - **404 Not Found**: Arquivo de mídia não encontrado.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    from app.config import settings

    # Validar filename contra path traversal (inclui URL-encoded)
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Nome de arquivo inválido")

    # Validar conversation_id contra path traversal
    if not conversation_id or ".." in conversation_id or "/" in conversation_id or "\\" in conversation_id:
        raise HTTPException(400, "ID de conversa inválido")

    # Resolver e validar que o caminho fica dentro de MEDIA_DIR
    media_base = settings.MEDIA_DIR.resolve()

    def _safe_resolve(candidate: Path) -> Optional[Path]:
        """Resolve o path e garante que está sob MEDIA_DIR."""
        resolved = candidate.resolve()
        try:
            resolved.relative_to(media_base)
        except ValueError:
            return None
        if resolved.is_symlink():
            return None
        return resolved if resolved.is_file() else None

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
        direct_path = settings.MEDIA_DIR / conversation_id / filename
        safe = _safe_resolve(direct_path)
        if not safe:
            raise HTTPException(404, "Arquivo de mídia não encontrado")
        return FileResponse(str(safe), filename=filename)

    # Validar que media_path resolva para dentro de MEDIA_DIR
    safe = _safe_resolve(Path(msg.media_path))
    if not safe:
        raise HTTPException(404, "Arquivo de mídia não encontrado no servidor")

    return FileResponse(
        str(safe),
        filename=filename,
    )


@router.get("/media/{conversation_id}/{filename}/info")
async def get_media_info(
    conversation_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Retorna metadados de um arquivo de mídia específico.

    Inclui informações como tipo de mídia, transcrição (para áudios),
    descrição (para imagens/vídeos), texto OCR e metadados técnicos.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "filename": "audio-001.opus",
        "media_type": "audio",
        "metadata": {"duration": 15.5, "format": "opus"},
        "transcription": "Olá, tudo bem com vocês?",
        "description": null,
        "ocr_text": null,
        "url": "/api/media/conv-123/audio-001.opus"
    }
    ```

    **Erros possíveis:**
    - **404 Not Found**: Mídia não encontrada.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
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
    """
    Retorna o status atual de todos os agentes de IA do orquestrador.

    Mostra informações sobre cada agente: se está ocupado, qual job está
    executando, quantos jobs completou e tempo médio de processamento.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "total_agents": 20,
        "active_agents": 5,
        "idle_agents": 15,
        "queue_size": 10,
        "agents": [
            {
                "agent_id": "agent-01",
                "is_busy": true,
                "current_job": "transcribe_audio",
                "jobs_completed": 42,
                "avg_processing_time": 3.5
            }
        ]
    }
    ```

    **Erros possíveis:**
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    try:
        from app.dependencies import get_orchestrator_instance
        orch = get_orchestrator_instance()
        if orch:
            return orch.get_status()
    except Exception:
        pass
    return {"message": "Orquestrador não disponível"}
