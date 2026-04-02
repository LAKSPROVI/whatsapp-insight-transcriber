"""
API Endpoints - Upload e Gerenciamento de Conversas.

Permite fazer upload de arquivos ZIP exportados do WhatsApp,
acompanhar o progresso do processamento, listar conversas,
obter detalhes, mensagens e deletar conversas.
"""
import os
import uuid
import logging
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import Conversation, Message, ProcessingStatus
from app.schemas import (
    ConversationResponse, ConversationListItem, UploadResponse,
    ProcessingProgress, MessageResponse
)
from app.services.conversation_processor import ConversationProcessor
from app.dependencies import get_orchestrator
from app.auth import get_current_user, UserInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])

# ─── Estado Global de Progresso ──────────────────────────────────────────────
_progress_store: dict = {}  # session_id -> progress data

# ─── Constantes de Segurança ZIP ─────────────────────────────────────────────
ZIP_MAGIC_BYTES = b"PK\x03\x04"


def _validate_zip_file(content: bytes) -> None:
    """
    Valida segurança do arquivo ZIP:
    - Magic bytes corretos
    - Número de arquivos dentro do limite
    - Tamanho total descompactado (proteção contra zip bombs)
    - Path traversal nos nomes dos arquivos
    """
    # 1. Validar magic bytes
    if not content[:4] == ZIP_MAGIC_BYTES:
        raise HTTPException(400, "Arquivo inválido: não é um ZIP válido (magic bytes incorretos)")

    # 2. Verificar estrutura do ZIP
    import io
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
            # 3. Limitar número de arquivos
            file_count = len(zf.infolist())
            if file_count > settings.MAX_ZIP_FILES:
                raise HTTPException(
                    400,
                    f"ZIP contém {file_count} arquivos. Máximo permitido: {settings.MAX_ZIP_FILES}"
                )

            # 4. Calcular tamanho total descompactado (proteção zip bomb)
            total_uncompressed: int = 0
            for info in zf.infolist():
                total_uncompressed += info.file_size

                # 5. Verificar path traversal
                normalized = os.path.normpath(info.filename)
                if normalized.startswith("..") or normalized.startswith("/") or normalized.startswith("\\"):
                    raise HTTPException(
                        400,
                        f"ZIP contém caminho suspeito (path traversal): {info.filename}"
                    )
                # Verificar também componentes individuais do path
                for part in Path(info.filename).parts:
                    if part == "..":
                        raise HTTPException(
                            400,
                            f"ZIP contém caminho suspeito (path traversal): {info.filename}"
                        )

            if total_uncompressed > settings.MAX_ZIP_UNCOMPRESSED_SIZE:
                raise HTTPException(
                    400,
                    f"Tamanho descompactado ({total_uncompressed // (1024*1024)}MB) excede o limite "
                    f"de {settings.MAX_ZIP_UNCOMPRESSED_SIZE // (1024*1024)}MB. Possível zip bomb."
                )

            # 6. Verificar ratio de compressão (zip bomb check adicional)
            if len(content) > 0 and total_uncompressed > 0:
                ratio = total_uncompressed / len(content)
                if ratio > 100:
                    raise HTTPException(
                        400,
                        f"Ratio de compressão suspeito ({ratio:.0f}x). Possível zip bomb."
                    )

    except zipfile.BadZipFile:
        raise HTTPException(400, "Arquivo ZIP corrompido ou inválido")


@router.post("/upload", response_model=UploadResponse)
async def upload_conversation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    orchestrator=Depends(get_orchestrator),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Faz upload de um arquivo .zip de exportação do WhatsApp e inicia processamento.

    Recebe o arquivo ZIP exportado pelo WhatsApp (contendo _chat.txt e mídias),
    valida a segurança do arquivo, salva no servidor e inicia o processamento
    assíncrono em background com 20 agentes de IA paralelos.

    **Formato aceito:** Apenas arquivos `.zip` (exportação padrão do WhatsApp).

    **Limites:**
    - Tamanho máximo do ZIP: configurável (padrão 500MB)
    - Máximo de arquivos dentro do ZIP: configurável
    - Proteção contra zip bombs

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    Content-Type: multipart/form-data
    ```

    **Exemplo de response (200):**
    ```json
    {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "conversation_id": "conv-abc123",
        "message": "Upload realizado com sucesso. Processamento iniciado.",
        "status": "uploading"
    }
    ```

    **Erros possíveis:**
    - **400 Bad Request**: Arquivo não é .zip, ZIP inválido/corrompido, zip bomb detectada.
    - **401 Unauthorized**: Token ausente ou inválido.
    - **413 Request Entity Too Large**: Arquivo excede o tamanho máximo permitido.
    """
    # Validar extensão
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "Apenas arquivos .zip são aceitos")

    # Verificar tamanho (usando MAX_UPLOAD_SIZE_MB)
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            413,
            f"Arquivo muito grande ({len(content) // (1024*1024)}MB). "
            f"Máximo: {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Validar segurança do ZIP
    _validate_zip_file(content)

    # Criar session ID único
    session_id = str(uuid.uuid4())

    # Salvar arquivo
    upload_path = settings.UPLOAD_DIR / f"{session_id}.zip"
    with open(upload_path, "wb") as f:
        f.write(content)

    logger.info(
        f"Upload recebido de {current_user.username}: "
        f"{file.filename} ({len(content)} bytes) -> session: {session_id}"
    )

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
async def get_progress(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Retorna o progresso atual do processamento de uma conversa.

    Consulta o status do processamento pelo session_id retornado no upload.
    Use polling periódico (ex.: a cada 2 segundos) para acompanhar o progresso.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "processing",
        "progress": 0.45,
        "progress_message": "Transcrevendo áudios (45/100)...",
        "total_messages": 500
    }
    ```

    **Status possíveis:** `uploading`, `parsing`, `processing`, `analyzing`, `completed`, `failed`

    **Erros possíveis:**
    - **404 Not Found**: Session ID não encontrado.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
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
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Lista todas as conversas processadas com paginação.

    Retorna uma lista resumida das conversas, ordenadas da mais recente para a mais antiga.

    **Query parameters:**
    - `skip` (int, default=0): Número de itens para pular (offset).
    - `limit` (int, default=20): Número máximo de itens por página.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    [
        {
            "id": "conv-abc123",
            "session_id": "550e8400-...",
            "original_filename": "WhatsApp Chat - Grupo.zip",
            "status": "completed",
            "progress": 1.0,
            "conversation_name": "Grupo da Família",
            "total_messages": 1500,
            "total_media": 200,
            "date_start": "2026-01-01T00:00:00Z",
            "date_end": "2026-03-31T23:59:00Z",
            "created_at": "2026-04-01T10:00:00Z"
        }
    ]
    ```

    **Erros possíveis:**
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    stmt = select(Conversation).order_by(desc(Conversation.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    return conversations


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Retorna detalhes completos de uma conversa específica.

    Inclui todas as informações da conversa: metadados, resumo, sentimento,
    palavras-chave, tópicos, momentos-chave e contradições.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "id": "conv-abc123",
        "session_id": "550e8400-...",
        "original_filename": "WhatsApp Chat - Grupo.zip",
        "status": "completed",
        "progress": 1.0,
        "conversation_name": "Grupo da Família",
        "participants": ["João", "Maria", "Pedro"],
        "total_messages": 1500,
        "total_media": 200,
        "summary": "Conversa sobre planejamento de viagem em família...",
        "sentiment_overall": "positive",
        "keywords": ["viagem", "hotel", "praia"],
        "topics": ["férias", "hospedagem"],
        "created_at": "2026-04-01T10:00:00Z",
        "updated_at": "2026-04-01T10:15:00Z"
    }
    ```

    **Erros possíveis:**
    - **404 Not Found**: Conversa não encontrada.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    stmt = select(Conversation).where(Conversation.id == conversation_id).options(
        selectinload(Conversation.messages)
    )
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
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Retorna as mensagens de uma conversa com filtros e paginação.

    Permite filtrar por tipo de mídia e por remetente. As mensagens são
    retornadas ordenadas por número de sequência (ordem cronológica).

    **Query parameters:**
    - `skip` (int, default=0): Offset para paginação.
    - `limit` (int, default=100): Limite por página (máx 100).
    - `media_only` (bool, default=false): Se true, retorna apenas mensagens com mídia.
    - `sender` (str, optional): Filtrar por remetente específico.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    [
        {
            "id": "msg-001",
            "sequence_number": 1,
            "timestamp": "2026-01-01T08:00:00Z",
            "sender": "João",
            "original_text": "Bom dia pessoal!",
            "media_type": "text",
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "processing_status": "completed"
        },
        {
            "id": "msg-002",
            "sequence_number": 2,
            "timestamp": "2026-01-01T08:01:00Z",
            "sender": "Maria",
            "original_text": null,
            "media_type": "audio",
            "media_filename": "audio-001.opus",
            "transcription": "Oi João, tudo bem?",
            "processing_status": "completed"
        }
    ]
    ```

    **Erros possíveis:**
    - **401 Unauthorized**: Token ausente ou inválido.
    """
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
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Remove uma conversa e todos seus dados associados.

    Deleta permanentemente a conversa, incluindo:
    - Todas as mensagens transcritas
    - Histórico de chat RAG
    - Arquivos de mídia extraídos
    - Arquivo ZIP original

    **⚠️ Esta ação é irreversível.**

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "message": "Conversa removida com sucesso"
    }
    ```

    **Erros possíveis:**
    - **404 Not Found**: Conversa não encontrada.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
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
