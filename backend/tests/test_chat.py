"""
Testes para o router de chat (RAG, histórico, analytics).
"""
import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from app.models import (
    Conversation, Message, ChatMessage,
    ProcessingStatus, MediaType,
)
from app.dependencies import get_claude_service
from app.auth import get_current_user


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _create_test_conversation(db_session, *, status=ProcessingStatus.COMPLETED):
    """Insere uma Conversation com 2 Messages no banco de teste."""
    conv = Conversation(
        session_id="chat-test-session",
        original_filename="test.zip",
        upload_path="/tmp/test.zip",
        extract_path="/tmp/media/test",
        status=status,
        progress=1.0 if status == ProcessingStatus.COMPLETED else 0.5,
        conversation_name="Test Chat Conv",
        participants=["João", "Maria"],
        total_messages=2,
        total_media=0,
        summary="Test summary",
        topics=["topic1"],
        word_frequency={"hello": 5, "world": 3},
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    for i, (sender, text) in enumerate([("João", "Olá!"), ("Maria", "Oi!")]):
        msg = Message(
            conversation_id=conv.id,
            sequence_number=i + 1,
            timestamp=datetime(2026, 1, 1, 8, i, tzinfo=timezone.utc),
            sender=sender,
            original_text=text,
            media_type=MediaType.TEXT,
        )
        db_session.add(msg)
    await db_session.commit()
    return conv


async def _add_chat_messages(db_session, conversation_id: str, count: int = 2):
    """Insere ChatMessages (histórico RAG) no banco de teste."""
    msgs = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        cm = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=f"msg-{i}",
        )
        db_session.add(cm)
        msgs.append(cm)
    await db_session.commit()
    return msgs


def _run(coro):
    """Executa coroutine no event loop corrente."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Chat History
# ═══════════════════════════════════════════════════════════════════════════════


class TestChatHistory:
    """GET /api/chat/{id}/history"""

    def test_returns_history(self, client, auth_headers, db_session, app):
        """Deve retornar o histórico de chat de uma conversa."""
        conv = _run(_create_test_conversation(db_session))
        _run(_add_chat_messages(db_session, conv.id, count=4))

        resp = client.get(f"/api/chat/{conv.id}/history", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == conv.id
        assert len(data["messages"]) == 4
        for msg in data["messages"]:
            assert "id" in msg
            assert "role" in msg
            assert "content" in msg
            assert "created_at" in msg

    def test_empty_history(self, client, auth_headers, db_session, app):
        """Conversa sem histórico RAG retorna lista vazia."""
        conv = _run(_create_test_conversation(db_session))

        resp = client.get(f"/api/chat/{conv.id}/history", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []

    def test_nonexistent_conversation_returns_empty(self, client, auth_headers, app):
        """Conversa inexistente retorna histórico vazio (endpoint não faz 404)."""
        resp = client.get("/api/chat/nonexistent-id-123/history", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    def test_unauthorized_returns_401_or_403(self, client, app):
        """Requisição sem token retorna 401 ou 403."""
        # Remover o override de get_current_user para testar auth real
        app.dependency_overrides.pop(get_current_user, None)
        resp = client.get("/api/chat/fake-id/history")
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Clear History
# ═══════════════════════════════════════════════════════════════════════════════


class TestClearHistory:
    """DELETE /api/chat/{id}/history"""

    def test_clears_messages(self, client, auth_headers, db_session, app):
        """Deve apagar todas as ChatMessages da conversa."""
        conv = _run(_create_test_conversation(db_session))
        _run(_add_chat_messages(db_session, conv.id, count=3))

        resp = client.delete(f"/api/chat/{conv.id}/history", headers=auth_headers)
        assert resp.status_code == 200
        assert "3" in resp.json()["message"]

        # Confirmar que o histórico está vazio
        resp2 = client.get(f"/api/chat/{conv.id}/history", headers=auth_headers)
        assert resp2.json()["messages"] == []

    def test_returns_deleted_count(self, client, auth_headers, db_session, app):
        """Retorna a quantidade exata de mensagens removidas."""
        conv = _run(_create_test_conversation(db_session))
        _run(_add_chat_messages(db_session, conv.id, count=5))

        resp = client.delete(f"/api/chat/{conv.id}/history", headers=auth_headers)
        assert resp.json()["message"] == "5 mensagens removidas"

    def test_clear_empty_history(self, client, auth_headers, db_session, app):
        """Limpar histórico vazio retorna 0 mensagens."""
        conv = _run(_create_test_conversation(db_session))

        resp = client.delete(f"/api/chat/{conv.id}/history", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "0 mensagens removidas"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Analytics
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnalytics:
    """GET /api/chat/{id}/analytics"""

    def test_returns_analytics(self, client, auth_headers, db_session, app):
        """Deve retornar analytics para conversa completa."""
        conv = _run(_create_test_conversation(db_session))

        resp = client.get(f"/api/chat/{conv.id}/analytics", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == conv.id
        assert "participant_stats" in data
        assert "message_timeline" in data
        assert "media_breakdown" in data
        assert "topics" in data

    def test_participant_stats_structure(self, client, auth_headers, db_session, app):
        """Cada participant_stat deve ter os campos corretos."""
        conv = _run(_create_test_conversation(db_session))

        resp = client.get(f"/api/chat/{conv.id}/analytics", headers=auth_headers)
        data = resp.json()

        stats = data["participant_stats"]
        assert len(stats) == 2

        names = {s["name"] for s in stats}
        assert names == {"João", "Maria"}

        for s in stats:
            assert "total_messages" in s
            assert "total_media" in s
            assert "avg_sentiment" in s
            assert "first_message" in s
            assert "last_message" in s
            assert s["total_messages"] == 1

    def test_media_breakdown(self, client, auth_headers, db_session, app):
        """media_breakdown deve refletir os tipos de mídia das mensagens."""
        conv = _run(_create_test_conversation(db_session))

        resp = client.get(f"/api/chat/{conv.id}/analytics", headers=auth_headers)
        data = resp.json()

        breakdown = data["media_breakdown"]
        assert breakdown.get("text", 0) == 2

    def test_word_cloud_data(self, client, auth_headers, db_session, app):
        """word_cloud_data deve ser derivado de word_frequency da conversa."""
        conv = _run(_create_test_conversation(db_session))

        resp = client.get(f"/api/chat/{conv.id}/analytics", headers=auth_headers)
        data = resp.json()

        wc = data["word_cloud_data"]
        assert len(wc) == 2
        texts = {item["text"] for item in wc}
        assert texts == {"hello", "world"}

    def test_topics(self, client, auth_headers, db_session, app):
        """topics deve conter os tópicos da conversa."""
        conv = _run(_create_test_conversation(db_session))

        resp = client.get(f"/api/chat/{conv.id}/analytics", headers=auth_headers)
        assert resp.json()["topics"] == ["topic1"]

    def test_nonexistent_conversation_returns_404(self, client, auth_headers, app):
        """Conversa inexistente retorna 404."""
        resp = client.get(
            "/api/chat/nonexistent-id-12345/analytics", headers=auth_headers
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Send Message (SSE stream)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSendMessage:
    """POST /api/chat/{id}/message"""

    def _override_claude(self, app, mock_claude_service):
        app.dependency_overrides[get_claude_service] = lambda: mock_claude_service

    def test_returns_sse_stream(
        self, client, auth_headers, db_session, app, mock_claude_service
    ):
        """Deve retornar um stream SSE para conversa válida."""
        conv = _run(_create_test_conversation(db_session))
        self._override_claude(app, mock_claude_service)

        # Patch AsyncSessionLocal usado dentro do stream_generator
        with patch("app.routers.chat.AsyncSessionLocal") as mock_session_local:
            mock_ctx = AsyncMock()
            mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                f"/api/chat/{conv.id}/message",
                json={
                    "conversation_id": conv.id,
                    "message": "Quais foram os topicos",
                    "include_context": True,
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "data:" in body
        assert "[DONE]" in body

    def test_nonexistent_conversation_returns_404(
        self, client, auth_headers, app, mock_claude_service
    ):
        """Conversa inexistente retorna 404."""
        self._override_claude(app, mock_claude_service)

        resp = client.post(
            "/api/chat/nonexistent-conv-999/message",
            json={
                "conversation_id": "nonexistent-conv-999",
                "message": "Teste",
                "include_context": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_non_completed_conversation_returns_400(
        self, client, auth_headers, db_session, app, mock_claude_service
    ):
        """Conversa não completa retorna 400."""
        conv = _run(
            _create_test_conversation(db_session, status=ProcessingStatus.PROCESSING)
        )
        self._override_claude(app, mock_claude_service)

        resp = client.post(
            f"/api/chat/{conv.id}/message",
            json={
                "conversation_id": conv.id,
                "message": "Teste",
                "include_context": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
