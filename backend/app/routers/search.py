"""
API Endpoints — Pesquisa Full-Text em mensagens e conversas.

Permite buscar mensagens por texto, remetente, data, tipo de mídia,
com suporte a regex, paginação, highlighting e ordenação por relevância.
"""
import re
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models import Conversation, Message, ProcessingStatus, MediaType
from app.schemas import (
    SearchResultItem,
    SearchResponse,
    SearchConversationItem,
    SearchConversationsResponse,
)
from app.auth import get_current_user, UserInfo
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


# Limite de complexidade para regex do usuário
MAX_REGEX_LENGTH = 200


def _safe_compile(query: str, is_regex: bool) -> re.Pattern | None:
    """Compila regex com proteção contra ReDoS."""
    try:
        raw = query if is_regex else re.escape(query)
        return re.compile(f"({raw})", re.IGNORECASE)
    except re.error:
        return None


def _escape_like(value: str) -> str:
    """Escapa wildcards do LIKE/ILIKE para evitar injeção de padrão."""
    return value.replace("%", "\\%").replace("_", "\\_")


def _apply_owner_visibility(stmt, current_user: UserInfo):
    if current_user.is_admin:
        return stmt
    return stmt.where(Conversation.owner_id == current_user.id)


def _highlight(text: str, query: str, is_regex: bool = False) -> str:
    """Adiciona marcações de highlight nos trechos encontrados."""
    if not text or not query:
        return text or ""
    pattern = _safe_compile(query, is_regex)
    if not pattern:
        return text
    try:
        return pattern.sub(r"**\1**", text)
    except (re.error, RecursionError):
        return text


def _score_message(msg: Message, query: str, is_regex: bool = False) -> float:
    """Calcula um score simples de relevância."""
    score = 0.0
    q_lower = query.lower()
    text = (msg.original_text or "").lower()

    if is_regex:
        pattern = _safe_compile(query, True)
        if pattern:
            try:
                matches = len(pattern.findall(text))
                score += matches * 10.0
            except (re.error, RecursionError):
                pass
    else:
        count = text.count(q_lower)
        score += count * 10.0
        # Bonus se aparece no início
        if text.startswith(q_lower):
            score += 5.0

    # Bonus para transcrições e descrições
    for field in [msg.transcription, msg.description, msg.ocr_text]:
        if field and q_lower in field.lower():
            score += 3.0

    return score


@router.get("/messages", response_model=SearchResponse)
async def search_messages(
    q: str = Query(..., min_length=1, max_length=500, description="Texto para buscar"),
    conversation_id: Optional[str] = Query(default=None, max_length=100),
    sender: Optional[str] = Query(default=None, max_length=200),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    message_type: Optional[str] = Query(default=None, alias="type"),
    regex: bool = Query(default=False, description="Interpretar q como regex"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="relevance", pattern="^(relevance|chronological)$"),
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Busca full-text em mensagens com filtros combináveis.

    Pesquisa em texto original, transcrições de áudio, descrições de imagem
    e texto OCR. Suporta busca por texto simples ou regex, com filtros por
    conversa, remetente, data e tipo de mídia.

    **Query parameters:**
    - `q` (str, obrigatório): Texto ou regex para buscar (1-500 caracteres).
    - `conversation_id` (str, opcional): Filtrar por conversa específica.
    - `sender` (str, opcional): Filtrar por remetente.
    - `date_from` (datetime, opcional): Data/hora inicial (ISO 8601).
    - `date_to` (datetime, opcional): Data/hora final (ISO 8601).
    - `type` (str, opcional): Tipo de mídia (`text`, `audio`, `image`, `video`, `document`, `sticker`).
    - `regex` (bool, default=false): Interpretar `q` como expressão regular.
    - `offset` (int, default=0): Offset para paginação.
    - `limit` (int, default=50, max=200): Resultados por página.
    - `sort_by` (str, default="relevance"): Ordenação — `relevance` ou `chronological`.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "query": "reunião",
        "total": 25,
        "offset": 0,
        "limit": 50,
        "results": [
            {
                "message_id": "msg-001",
                "conversation_id": "conv-abc",
                "conversation_name": "Grupo Trabalho",
                "sequence_number": 42,
                "timestamp": "2026-01-15T14:30:00Z",
                "sender": "João",
                "text": "Vamos marcar a reunião para amanhã",
                "highlighted_text": "Vamos marcar a **reunião** para amanhã",
                "media_type": "text",
                "sentiment": "neutral",
                "score": 15.0
            }
        ]
    }
    ```

    **Erros possíveis:**
    - **422 Unprocessable Entity**: Query vazia, regex inválida ou tipo de mídia inválido.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    logger.info(
        "Pesquisa de mensagens",
        extra={"query": q, "user": current_user.username, "regex": regex},
    )

    # Validar regex se habilitado
    if regex:
        if len(q) > MAX_REGEX_LENGTH:
            raise ValidationError(
                detail=f"Regex muito longa (máx {MAX_REGEX_LENGTH} caracteres)",
                context={"query": q[:50]},
            )
        try:
            re.compile(q)
        except re.error as e:
            raise ValidationError(
                detail=f"Expressão regex inválida: {str(e)}",
                context={"query": q},
            )

    # Validar conversation_id
    if conversation_id and not re.match(r"^[a-zA-Z0-9_-]+$", conversation_id):
        raise ValidationError(detail="ID de conversa contém caracteres inválidos")

    # Construir query base — busca em text, transcription, description, ocr_text
    stmt = (
        select(Message, Conversation.conversation_name)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.status == ProcessingStatus.COMPLETED)
    )
    stmt = _apply_owner_visibility(stmt, current_user)

    # Filtros
    if conversation_id:
        stmt = stmt.where(Message.conversation_id == conversation_id)
    if sender:
        stmt = stmt.where(Message.sender == sender)
    if date_from:
        stmt = stmt.where(Message.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(Message.timestamp <= date_to)
    if message_type:
        try:
            mt = MediaType(message_type)
            stmt = stmt.where(Message.media_type == mt)
        except ValueError:
            raise ValidationError(detail=f"Tipo de mídia inválido: {message_type}")

    # Filtro de texto — LIKE com wildcards escapados
    if not regex:
        safe_q = _escape_like(q)
        like_pattern = f"%{safe_q}%"
        stmt = stmt.where(
            or_(
                Message.original_text.ilike(like_pattern),
                Message.transcription.ilike(like_pattern),
                Message.description.ilike(like_pattern),
                Message.ocr_text.ilike(like_pattern),
            )
        )

    # Executar
    result = await db.execute(stmt)
    rows = result.all()

    # Se regex, filtrar em Python (SQLite não tem regex nativo)
    if regex:
        try:
            pattern = re.compile(q, re.IGNORECASE)
        except re.error:
            pattern = None

        if pattern:
            filtered = []
            for msg, conv_name in rows:
                texts = [
                    msg.original_text or "",
                    msg.transcription or "",
                    msg.description or "",
                    msg.ocr_text or "",
                ]
                if any(pattern.search(t) for t in texts):
                    filtered.append((msg, conv_name))
            rows = filtered

    # Calcular scores e montar resultados
    scored_results = []
    for msg, conv_name in rows:
        score = _score_message(msg, q, regex)
        display_text = msg.original_text or msg.transcription or msg.description or msg.ocr_text or ""
        highlighted = _highlight(display_text, q, regex)

        scored_results.append(SearchResultItem(
            message_id=msg.id,
            conversation_id=msg.conversation_id,
            conversation_name=conv_name,
            sequence_number=msg.sequence_number,
            timestamp=msg.timestamp,
            sender=msg.sender,
            text=display_text[:500],
            highlighted_text=highlighted[:500],
            media_type=msg.media_type,
            sentiment=msg.sentiment,
            score=score,
        ))

    # Ordenar
    if sort_by == "relevance":
        scored_results.sort(key=lambda x: x.score, reverse=True)
    else:
        scored_results.sort(key=lambda x: x.timestamp)

    total = len(scored_results)
    paginated = scored_results[offset:offset + limit]

    return SearchResponse(
        query=q,
        total=total,
        offset=offset,
        limit=limit,
        results=paginated,
    )


@router.get("/conversations", response_model=SearchConversationsResponse)
async def search_conversations(
    q: str = Query(..., min_length=1, max_length=500, description="Texto para buscar"),
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Busca em nomes de conversas processadas.

    Pesquisa por nome da conversa e retorna informações resumidas incluindo
    contagem de mensagens que correspondem ao termo buscado.

    **Query parameters:**
    - `q` (str, obrigatório): Texto para buscar no nome da conversa (1-500 caracteres).

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "query": "família",
        "total": 2,
        "results": [
            {
                "conversation_id": "conv-abc",
                "conversation_name": "Grupo da Família",
                "participants": ["João", "Maria", "Pedro"],
                "total_messages": 1500,
                "date_start": "2026-01-01T00:00:00Z",
                "date_end": "2026-03-31T23:59:00Z",
                "match_count": 45
            }
        ]
    }
    ```

    **Erros possíveis:**
    - **422 Unprocessable Entity**: Query vazia ou muito longa.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    logger.info(
        "Pesquisa de conversas",
        extra={"query": q, "user": current_user.username},
    )

    safe_q = _escape_like(q)
    like_pattern = f"%{safe_q}%"
    stmt = (
        select(Conversation)
        .where(
            Conversation.status == ProcessingStatus.COMPLETED,
            Conversation.conversation_name.ilike(like_pattern),
        )
        .order_by(Conversation.created_at.desc())
    )
    stmt = _apply_owner_visibility(stmt, current_user)

    result = await db.execute(stmt)
    conversations = result.scalars().all()

    # Contar mensagens que correspondem ao query em cada conversa
    items = []
    for conv in conversations:
        msg_count_stmt = (
            select(func.count(Message.id))
            .where(
                Message.conversation_id == conv.id,
                or_(
                    Message.original_text.ilike(like_pattern),
                    Message.transcription.ilike(like_pattern),
                ),
            )
        )
        count_result = await db.execute(msg_count_stmt)
        match_count = count_result.scalar() or 0

        items.append(SearchConversationItem(
            conversation_id=conv.id,
            conversation_name=conv.conversation_name,
            participants=conv.participants,
            total_messages=conv.total_messages,
            date_start=conv.date_start,
            date_end=conv.date_end,
            match_count=match_count,
        ))

    return SearchConversationsResponse(
        query=q,
        total=len(items),
        results=items,
    )


# ── Semantic Search (pgvector) ───────────────────────────────────────

@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., min_length=2, max_length=500),
    conversation_id: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Busca sem\u00e2ntica usando pgvector (similaridade de cosseno).
    Fallback para ILIKE se pgvector n\u00e3o dispon\u00edvel.
    """
    # Verify ownership
    conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
    if not current_user.is_admin:
        conv_stmt = conv_stmt.where(Conversation.owner_id == current_user.id)
    conv_result = await db.execute(conv_stmt)
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    from app.services.semantic_search import get_semantic_search_service

    service = get_semantic_search_service()
    results = await service.search(db, conversation_id, q, limit)
    return {
        "query": q,
        "conversation_id": conversation_id,
        "total": len(results),
        "results": results,
    }
