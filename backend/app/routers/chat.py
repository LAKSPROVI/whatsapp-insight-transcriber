"""
API Endpoints - Chat RAG e Análise de Conversas.

Permite fazer perguntas sobre conversas transcritas usando Retrieval Augmented Generation (RAG),
visualizar histórico de chat, limpar histórico e obter analytics detalhados.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import Conversation, Message, ChatMessage, ProcessingStatus
from app.schemas import (
    ChatRequest, ChatResponse, ChatHistoryResponse,
    ConversationAnalytics, ParticipantStats
)
from app.dependencies import get_claude_service
from app.auth import apply_owner_filter, ensure_owner_access, get_current_user, UserInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{conversation_id}/message")
async def send_chat_message(
    conversation_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    claude=Depends(get_claude_service),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Envia uma pergunta sobre a conversa transcrita usando Chat RAG.

    Utiliza Retrieval Augmented Generation (RAG) para responder perguntas
    sobre o conteúdo da conversa. A resposta é enviada via Server-Sent Events (SSE)
    para streaming em tempo real.

    O contexto da conversa (mensagens, transcrições, descrições de mídia) é
    automaticamente incluído no prompt enviado à IA.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    Content-Type: application/json
    ```

    **Exemplo de request:**
    ```json
    {
        "conversation_id": "abc-123",
        "message": "Quais foram os principais tópicos discutidos?",
        "include_context": true
    }
    ```

    **Response:** Stream SSE (text/event-stream)
    ```
    data: Os principais
    data:  tópicos discutidos
    data:  foram...
    data: [DONE]
    ```

    **Erros possíveis:**
    - **404 Not Found**: Conversa não encontrada.
    - **400 Bad Request**: Conversa ainda não foi completamente processada.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    # Verificar se conversa existe e está concluída
    stmt = apply_owner_filter(
        select(Conversation).where(Conversation.id == conversation_id),
        Conversation,
        current_user,
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    ensure_owner_access(conv, current_user)

    if conv.status != ProcessingStatus.COMPLETED:
        raise HTTPException(400, "A conversa ainda não foi completamente processada")

    # Buscar histórico do chat
    history_stmt = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
        .limit(20)
    )
    history_result = await db.execute(history_stmt)
    history = history_result.scalars().all()

    chat_history = [{"role": m.role, "content": m.content} for m in history]

    # Construir contexto da conversa
    context = await _build_context(conv, db)

    # Salvar mensagem do usuário
    user_msg = ChatMessage(
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    await db.commit()

    # Stream da resposta
    response_text = []

    async def stream_generator():
        total_tokens = 0
        async for chunk in claude.chat_with_context(
            user_message=request.message,
            conversation_context=context,
            chat_history=chat_history,
        ):
            response_text.append(chunk)
            yield f"data: {chunk}\n\n"

        # Salvar resposta completa usando uma nova sessão (a request-scoped pode estar fechada)
        full_response = "".join(response_text)
        assistant_msg = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=full_response,
        )
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as new_db:
            new_db.add(assistant_msg)
            await new_db.commit()

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{conversation_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Retorna o histórico completo do chat RAG de uma conversa.

    Lista todas as mensagens trocadas (perguntas do usuário e respostas da IA)
    ordenadas cronologicamente.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "conversation_id": "abc-123",
        "messages": [
            {
                "id": "msg-1",
                "role": "user",
                "content": "Quem participou da conversa?",
                "tokens_used": null,
                "created_at": "2026-04-01T10:00:00Z"
            },
            {
                "id": "msg-2",
                "role": "assistant",
                "content": "A conversa teve 3 participantes: João, Maria e Pedro.",
                "tokens_used": 150,
                "created_at": "2026-04-01T10:00:05Z"
            }
        ]
    }
    ```

    **Erros possíveis:**
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    conv_stmt = apply_owner_filter(
        select(Conversation).where(Conversation.id == conversation_id),
        Conversation,
        current_user,
    )
    conv_result = await db.execute(conv_stmt)
    conv = conv_result.scalar_one_or_none()
    ensure_owner_access(conv, current_user)

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    return ChatHistoryResponse(
        conversation_id=conversation_id,
        messages=messages,
    )


@router.delete("/{conversation_id}/history")
async def clear_chat_history(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Limpa todo o histórico do chat RAG de uma conversa.

    Remove todas as mensagens (perguntas e respostas) do histórico do chat.
    Não afeta os dados da conversa original nem as transcrições.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "message": "15 mensagens removidas"
    }
    ```

    **Erros possíveis:**
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    conv_stmt = apply_owner_filter(
        select(Conversation).where(Conversation.id == conversation_id),
        Conversation,
        current_user,
    )
    conv_result = await db.execute(conv_stmt)
    conv = conv_result.scalar_one_or_none()
    ensure_owner_access(conv, current_user)

    stmt = select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
    result = await db.execute(stmt)
    messages = result.scalars().all()

    for msg in messages:
        await db.delete(msg)

    await db.commit()
    return {"message": f"{len(messages)} mensagens removidas"}


@router.get("/{conversation_id}/analytics", response_model=ConversationAnalytics)
async def get_analytics(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Retorna análises detalhadas e estatísticas de uma conversa.

    Gera analytics completos incluindo:
    - Estatísticas por participante (mensagens, mídias, sentimento médio)
    - Timeline de mensagens (por dia e por hora)
    - Timeline de sentimento ao longo do tempo
    - Breakdown de tipos de mídia
    - Momentos-chave identificados pela IA
    - Contradições detectadas
    - Nuvem de palavras (top 100)
    - Tópicos identificados

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "conversation_id": "abc-123",
        "participant_stats": [
            {
                "name": "João",
                "total_messages": 150,
                "total_media": 10,
                "avg_sentiment": 0.65,
                "first_message": "2026-01-01T08:00:00Z",
                "last_message": "2026-01-15T22:30:00Z"
            }
        ],
        "message_timeline": [{"date": "2026-01-01", "count": 45}],
        "sentiment_timeline": [{"timestamp": "...", "sender": "João", "score": 0.8}],
        "media_breakdown": {"text": 500, "audio": 30, "image": 20},
        "hourly_activity": {"2026-01-01 08:00": 5},
        "key_moments": [],
        "contradictions": [],
        "word_cloud_data": [{"text": "reunião", "value": 42}],
        "topics": ["trabalho", "projeto"]
    }
    ```

    **Erros possíveis:**
    - **404 Not Found**: Conversa não encontrada.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    stmt = apply_owner_filter(
        select(Conversation).where(Conversation.id == conversation_id),
        Conversation,
        current_user,
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    ensure_owner_access(conv, current_user)

    # Buscar mensagens
    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_number)
    )
    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()

    # ─── Estatísticas por participante ───────────────────────────────
    participant_stats = {}
    for msg in messages:
        if msg.sender not in participant_stats:
            participant_stats[msg.sender] = {
                "name": msg.sender,
                "total_messages": 0,
                "total_media": 0,
                "sentiment_scores": [],
                "first_message": msg.timestamp,
                "last_message": msg.timestamp,
            }
        p = participant_stats[msg.sender]
        p["total_messages"] += 1
        if msg.media_type.value != "text":
            p["total_media"] += 1
        if msg.sentiment_score is not None:
            p["sentiment_scores"].append(msg.sentiment_score)
        p["last_message"] = msg.timestamp

    participant_list = []
    for name, stats in participant_stats.items():
        avg_sent = (
            sum(stats["sentiment_scores"]) / len(stats["sentiment_scores"])
            if stats["sentiment_scores"] else None
        )
        participant_list.append(ParticipantStats(
            name=name,
            total_messages=stats["total_messages"],
            total_media=stats["total_media"],
            avg_sentiment=avg_sent,
            first_message=stats["first_message"],
            last_message=stats["last_message"],
        ))

    # ─── Linha do tempo de mensagens (por hora) ───────────────────────
    from collections import defaultdict
    hourly = defaultdict(int)
    daily = defaultdict(int)
    for msg in messages:
        hour_key = msg.timestamp.strftime("%Y-%m-%d %H:00")
        hourly[hour_key] += 1
        day_key = msg.timestamp.strftime("%Y-%m-%d")
        daily[day_key] += 1

    # ─── Breakdown de mídias ──────────────────────────────────────────
    media_breakdown = defaultdict(int)
    for msg in messages:
        media_breakdown[msg.media_type.value] += 1

    # ─── Timeline de sentimento ───────────────────────────────────────
    sentiment_timeline = [
        {
            "timestamp": msg.timestamp.isoformat(),
            "sender": msg.sender,
            "score": msg.sentiment_score,
        }
        for msg in messages
        if msg.sentiment_score is not None
    ]

    # ─── Nuvem de palavras ────────────────────────────────────────────
    word_cloud_data = []
    if conv.word_frequency:
        for word, freq in sorted(conv.word_frequency.items(), key=lambda x: -x[1])[:100]:
            word_cloud_data.append({"text": word, "value": freq})

    return ConversationAnalytics(
        conversation_id=conversation_id,
        participant_stats=participant_list,
        message_timeline=[{"date": k, "count": v} for k, v in sorted(daily.items())],
        sentiment_timeline=sentiment_timeline,
        media_breakdown=dict(media_breakdown),
        hourly_activity=dict(hourly),
        key_moments=conv.key_moments or [],
        contradictions=conv.contradictions or [],
        word_cloud_data=word_cloud_data,
        topics=conv.topics or [],
    )


async def _build_context(conv: Conversation, db: AsyncSession) -> str:
    """Constrói o contexto textual para o RAG"""
    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.sequence_number)
        .limit(800)  # Limitar para não estourar context
    )
    result = await db.execute(msg_stmt)
    messages = result.scalars().all()

    lines = []
    lines.append(f"=== CONVERSA: {conv.conversation_name or 'Sem nome'} ===")
    lines.append(f"Participantes: {', '.join(conv.participants or [])}")
    lines.append(f"Período: {conv.date_start} a {conv.date_end}")
    lines.append("")

    for msg in messages:
        ts = msg.timestamp.strftime("%d/%m/%Y %H:%M")

        if msg.media_type.value == "text":
            lines.append(f"[{ts}] {msg.sender}: {msg.original_text or ''}")
        elif msg.transcription:
            lines.append(f"[{ts}] {msg.sender} [áudio]: {msg.transcription}")
        elif msg.description:
            lines.append(f"[{ts}] {msg.sender} [{msg.media_type.value}]: {msg.description}")
            if msg.ocr_text:
                lines.append(f"  (texto na imagem: {msg.ocr_text})")
        else:
            lines.append(f"[{ts}] {msg.sender}: [{msg.media_type.value}]")

    return "\n".join(lines)
