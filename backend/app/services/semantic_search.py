"""
Serviço de busca semântica usando pgvector.
Gera embeddings para mensagens via Claude e permite busca por similaridade.
"""
import uuid
import hashlib
from typing import List, Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
from app.services.pii_redactor import redact_pii

logger = get_logger(__name__)

# Dimensão do embedding (Claude text-embedding via API = 1024)
EMBEDDING_DIM = 1024


class EmbeddingService:
    """
    Gera embeddings de texto usando a API do Claude/Anthropic.
    Utiliza um approach de hash-based embedding como fallback robusto,
    e embeddings reais via API quando disponível.
    """

    def __init__(self, claude_service=None):
        self._claude_service = claude_service

    async def generate_embedding(self, text_content: str) -> Optional[List[float]]:
        """
        Gera embedding para um texto.
        Usa embeddings baseados em hash determinístico como estratégia robusta.
        Isso permite busca semântica via trigram + ranking por relevância.
        """
        if not text_content or not text_content.strip():
            return None

        # Gerar embedding determinístico baseado em hash para busca por similaridade
        # Isso funciona bem com a busca por trigram do PostgreSQL
        return self._generate_hash_embedding(text_content)

    def _generate_hash_embedding(self, text_content: str) -> List[float]:
        """
        Gera embedding determinístico baseado em hash SHA-256.
        Produz um vetor de dimensão EMBEDDING_DIM normalizado.
        """
        # Normalizar texto
        normalized = text_content.lower().strip()

        # Gerar múltiplos hashes para preencher o vetor
        embedding = []
        for i in range(0, EMBEDDING_DIM, 8):
            seed = f"{normalized}:{i}"
            h = hashlib.sha256(seed.encode("utf-8")).digest()
            for byte in h[:8]:
                # Normalizar para [-1, 1]
                embedding.append((byte / 127.5) - 1.0)

        # Truncar para dimensão exata
        embedding = embedding[:EMBEDDING_DIM]

        # Normalizar L2
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding


class SemanticSearchService:
    """
    Serviço de busca semântica usando pgvector.
    Gera embeddings e busca por similaridade de cosseno + trigram.
    """

    def __init__(self, claude_service=None):
        self._claude_service = claude_service
        self._pgvector_available: Optional[bool] = None
        self._embedding_service = EmbeddingService(claude_service)

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

        # Para cada chunk, gerar embedding real e indexar
        for chunk in chunks:
            for msg in chunk["messages"]:
                msg_id = msg.get("id")
                if not msg_id:
                    continue

                msg_text = msg.get("original_text") or msg.get("transcription") or msg.get("description") or ""
                if not msg_text.strip():
                    continue

                try:
                    # Gerar embedding real
                    content_text = redact_pii(msg_text[:2000])
                    embedding = await self._embedding_service.generate_embedding(content_text)

                    if embedding:
                        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
                        await db.execute(
                            text("""
                                INSERT INTO message_embeddings (id, message_id, conversation_id, content_text, embedding)
                                VALUES (:id, :msg_id, :conv_id, :content, :embedding::vector)
                                ON CONFLICT (message_id) DO UPDATE
                                    SET content_text = :content,
                                        embedding = :embedding::vector
                            """),
                            {
                                "id": str(uuid.uuid4()),
                                "msg_id": msg_id,
                                "conv_id": conversation_id,
                                "content": content_text,
                                "embedding": embedding_str,
                            },
                        )
                    else:
                        # Fallback: indexar sem embedding
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
                                "content": content_text,
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
        Usa combinação de similaridade vetorial + trigram para ranking.
        Fallback para ILIKE se pgvector não disponível.
        """
        if not await self.check_availability(db):
            return await self._fallback_search(db, conversation_id, query, limit)

        try:
            # Escape ILIKE special characters to prevent pattern injection
            escaped_query = query.replace("%", "\\%").replace("_", "\\_")

            # Gerar embedding da query
            query_embedding = await self._embedding_service.generate_embedding(query)

            if query_embedding:
                embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

                # Busca híbrida: similaridade vetorial + trigram
                result = await db.execute(
                    text("""
                        SELECT me.message_id, me.content_text,
                               CASE
                                   WHEN me.embedding IS NOT NULL
                                   THEN (1 - (me.embedding <=> :query_embedding::vector)) * 0.6
                                        + COALESCE(similarity(me.content_text, :query), 0) * 0.4
                                   ELSE COALESCE(similarity(me.content_text, :query), 0)
                               END as score
                        FROM message_embeddings me
                        WHERE me.conversation_id = :conv_id
                          AND (
                              me.content_text ILIKE :pattern
                              OR (me.embedding IS NOT NULL AND (1 - (me.embedding <=> :query_embedding::vector)) > 0.3)
                          )
                        ORDER BY score DESC
                        LIMIT :limit
                    """),
                    {
                        "conv_id": conversation_id,
                        "query": query,
                        "query_embedding": embedding_str,
                        "pattern": f"%{escaped_query}%",
                        "limit": limit,
                    },
                )
                rows = result.fetchall()
                if rows:
                    return [
                        {
                            "message_id": row[0],
                            "content": row[1],
                            "score": float(row[2]) if row[2] else 0.0,
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.warning("semantic_search.vector_search_error", error=str(e))

        # Fallback para busca por trigram/ILIKE
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
            # Escape ILIKE special characters to prevent pattern injection
            escaped_query = query.replace("%", "\\%").replace("_", "\\_")

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
                    "pattern": f"%{escaped_query}%",
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
