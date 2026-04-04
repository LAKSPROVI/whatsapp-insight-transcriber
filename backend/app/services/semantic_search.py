"""
Serviço de busca semântica usando pgvector.
Gera embeddings para mensagens e permite busca por similaridade.
"""
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
from app.services.pii_redactor import redact_pii

logger = get_logger(__name__)

# Dimensão do embedding (OpenAI text-embedding-3-small = 1536)
EMBEDDING_DIM = 1536


class SemanticSearchService:
    """
    Serviço de busca semântica usando pgvector.
    Gera embeddings via API e busca por similaridade de cosseno.
    """

    def __init__(self, claude_service=None):
        self._claude_service = claude_service
        self._pgvector_available: Optional[bool] = None

    async def check_availability(self, db: AsyncSession) -> bool:
        """Verifica se pgvector está disponível no banco."""
        if self._pgvector_available is not None:
            return self._pgvector_available

        try:
            result = await db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            self._pgvector_available = result.scalar() is not None
        except Exception:
            self._pgvector_available = False

        if not self._pgvector_available:
            logger.warning("semantic_search.pgvector_unavailable")
        else:
            logger.info("semantic_search.pgvector_available")

        return self._pgvector_available

    async def index_conversation(
        self,
        db: AsyncSession,
        conversation_id: str,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Indexa mensagens de uma conversação gerando embeddings.
        Agrupa mensagens em chunks para eficiência.
        """
        if not await self.check_availability(db):
            return {"indexed": 0, "status": "pgvector_unavailable"}

        indexed = 0
        chunk_size = 5  # Agrupar 5 mensagens por chunk
        chunks = []

        # Preparar chunks de texto
        current_chunk = []
        current_text = ""

        for msg in messages:
            text_content = msg.get("original_text") or msg.get("transcription") or msg.get("description") or ""
            if not text_content.strip():
                continue

            sender = msg.get("sender", "")
            msg_text = f"[{sender}]: {text_content}"
            current_chunk.append(msg)
            current_text += msg_text + "\n"

            if len(current_chunk) >= chunk_size:
                chunks.append({
                    "messages": current_chunk,
                    "text": redact_pii(current_text.strip()),
                })
                current_chunk = []
                current_text = ""

        if current_chunk:
            chunks.append({
                "messages": current_chunk,
                "text": redact_pii(current_text.strip()),
            })

        # Para cada chunk, gerar embedding placeholder
        # (Em produção, usar API de embeddings real)
        for chunk in chunks:
            for msg in chunk["messages"]:
                msg_id = msg.get("id")
                if not msg_id:
                    continue

                msg_text = msg.get("original_text") or msg.get("transcription") or msg.get("description") or ""
                if not msg_text.strip():
                    continue

                try:
                    # Inserir com embedding NULL por enquanto
                    # Quando API de embeddings for integrada, gerar embedding real
                    await db.execute(
                        text("""
                            INSERT INTO message_embeddings (id, message_id, conversation_id, content_text)
                            VALUES (:id, :msg_id, :conv_id, :content)
                            ON CONFLICT (message_id) DO UPDATE SET content_text = :content
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "msg_id": msg_id,
                            "conv_id": conversation_id,
                            "content": redact_pii(msg_text[:2000]),
                        },
                    )
                    indexed += 1
                except Exception as e:
                    logger.error("semantic_search.index_error", message_id=msg_id, error=str(e))

        await db.commit()

        logger.info(
            "semantic_search.indexed",
            conversation_id=conversation_id,
            indexed=indexed,
            total_chunks=len(chunks),
        )
        return {"indexed": indexed, "status": "indexed", "chunks": len(chunks)}

    async def search(
        self,
        db: AsyncSession,
        conversation_id: str,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Busca semântica por similaridade.
        Fallback para ILIKE se pgvector não disponível ou embeddings não gerados.
        """
        if not await self.check_availability(db):
            return await self._fallback_search(db, conversation_id, query, limit)

        # Tentar busca por similaridade de texto (sem embeddings por enquanto)
        # Quando embeddings estiverem disponíveis, usar:
        # SELECT *, 1 - (embedding <=> :query_embedding) as similarity
        # FROM message_embeddings WHERE conversation_id = :conv_id
        # ORDER BY embedding <=> :query_embedding LIMIT :limit

        return await self._fallback_search(db, conversation_id, query, limit)

    async def _fallback_search(
        self,
        db: AsyncSession,
        conversation_id: str,
        query: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Busca por texto usando trigram/ILIKE como fallback."""
        try:
            result = await db.execute(
                text("""
                    SELECT me.message_id, me.content_text,
                           similarity(me.content_text, :query) as score
                    FROM message_embeddings me
                    WHERE me.conversation_id = :conv_id
                      AND me.content_text ILIKE :pattern
                    ORDER BY score DESC
                    LIMIT :limit
                """),
                {
                    "conv_id": conversation_id,
                    "query": query,
                    "pattern": f"%{query}%",
                    "limit": limit,
                },
            )
            rows = result.fetchall()
            return [
                {
                    "message_id": row[0],
                    "content": row[1],
                    "score": float(row[2]) if row[2] else 0.0,
                }
                for row in rows
            ]
        except Exception as e:
            logger.error("semantic_search.fallback_error", error=str(e))
            return []


# Instância global
_semantic_service: Optional[SemanticSearchService] = None


def get_semantic_search_service() -> SemanticSearchService:
    global _semantic_service
    if _semantic_service is None:
        _semantic_service = SemanticSearchService()
    return _semantic_service
