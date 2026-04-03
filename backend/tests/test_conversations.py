"""
Testes para o router de conversas (upload, listagem, detalhes, mensagens, delete, progresso).
"""
import io
import uuid
import zipfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models import Conversation, Message, ProcessingStatus, MediaType
from app.dependencies import get_orchestrator
from app.auth import get_current_user


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_test_zip(chat_content: str = "26/03/2025, 08:00 - João: Olá\n") -> io.BytesIO:
    """Cria um ZIP válido em memória contendo _chat.txt."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("_chat.txt", chat_content)
    buf.seek(0)
    return buf


def _make_conversation(session_id: str | None = None, **overrides) -> Conversation:
    """Cria uma instância de Conversation com defaults razoáveis."""
    defaults = dict(
        session_id=session_id or str(uuid.uuid4()),
        original_filename="chat.zip",
        upload_path="/tmp/chat.zip",
        extract_path="/tmp/media/chat",
        status=ProcessingStatus.COMPLETED,
        progress=1.0,
        progress_message="Concluído",
        total_messages=10,
        total_media=2,
    )
    defaults.update(overrides)
    return Conversation(**defaults)


def _make_message(conversation_id: str, seq: int, **overrides) -> Message:
    """Cria uma instância de Message com defaults razoáveis."""
    defaults = dict(
        conversation_id=conversation_id,
        sequence_number=seq,
        timestamp=datetime(2026, 1, 1, 8, seq, tzinfo=timezone.utc),
        sender="João",
        original_text=f"Mensagem {seq}",
        media_type=MediaType.TEXT,
        processing_status=ProcessingStatus.COMPLETED,
    )
    defaults.update(overrides)
    return Message(**defaults)


def _seed_sync(db_session, *objs):
    """Insere objetos no DB usando o loop de eventos atual."""
    import asyncio

    async def _do():
        for obj in objs:
            db_session.add(obj)
        await db_session.commit()

    asyncio.get_event_loop().run_until_complete(_do())


# ─── Fixture: mock orchestrator ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def override_orchestrator(app):
    """Substitui o orchestrator real por um mock em todos os testes."""
    mock_orch = AsyncMock()
    app.dependency_overrides[get_orchestrator] = lambda: mock_orch
    yield mock_orch
    app.dependency_overrides.pop(get_orchestrator, None)


# ─── Fixture: client sem auth (para testes de 401/403) ───────────────────────

@pytest.fixture
def unauth_client(app):
    """Client que simula usuário não autenticado (get_current_user levanta 403)."""
    from fastapi.testclient import TestClient

    async def _deny():
        raise HTTPException(status_code=403, detail="Not authenticated")

    app.dependency_overrides[get_current_user] = _deny
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ═════════════════════════════════════════════════════════════════════════════
# 1. Upload Endpoint  POST /api/conversations/upload
# ═════════════════════════════════════════════════════════════════════════════

class TestUpload:
    """Testes para o endpoint de upload."""

    def test_upload_valid_zip(self, client, auth_headers, tmp_path):
        """Upload de ZIP válido retorna 200 com session_id."""
        zip_buf = make_test_zip()
        with patch("app.routers.conversations.settings") as mock_settings:
            mock_settings.MAX_UPLOAD_SIZE_MB = 100
            mock_settings.MAX_ZIP_FILES = 5000
            mock_settings.MAX_ZIP_UNCOMPRESSED_SIZE = 1024 * 1024 * 1024
            mock_settings.UPLOAD_DIR = tmp_path
            mock_settings.MEDIA_DIR = tmp_path / "media"

            resp = client.post(
                "/api/conversations/upload",
                headers=auth_headers,
                files={"file": ("chat.zip", zip_buf, "application/zip")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "conversation_id" in data
        assert data["status"] == "uploading"
        assert "Upload realizado" in data["message"]

    def test_upload_non_zip_file(self, client, auth_headers):
        """Upload de arquivo não-ZIP retorna 400."""
        fake_file = io.BytesIO(b"plain text content")
        resp = client.post(
            "/api/conversations/upload",
            headers=auth_headers,
            files={"file": ("notes.txt", fake_file, "text/plain")},
        )
        assert resp.status_code == 400
        assert "zip" in resp.json()["detail"].lower()

    def test_upload_without_auth(self, unauth_client):
        """Upload sem token de autenticação retorna 403."""
        zip_buf = make_test_zip()
        resp = unauth_client.post(
            "/api/conversations/upload",
            files={"file": ("chat.zip", zip_buf, "application/zip")},
        )
        assert resp.status_code == 403

    def test_upload_oversized_file(self, client, auth_headers):
        """Upload de arquivo maior que o limite retorna 413."""
        zip_buf = make_test_zip()
        with patch("app.routers.conversations.settings") as mock_settings:
            # Limitar a 0 MB para forçar 413
            mock_settings.MAX_UPLOAD_SIZE_MB = 0
            resp = client.post(
                "/api/conversations/upload",
                headers=auth_headers,
                files={"file": ("chat.zip", zip_buf, "application/zip")},
            )
        assert resp.status_code == 413

    def test_upload_zip_with_path_traversal(self, client, auth_headers, tmp_path):
        """Upload de ZIP com path traversal retorna 400."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../etc/passwd", "root:x:0:0")
        buf.seek(0)

        with patch("app.routers.conversations.settings") as mock_settings:
            mock_settings.MAX_UPLOAD_SIZE_MB = 100
            mock_settings.MAX_ZIP_FILES = 5000
            mock_settings.MAX_ZIP_UNCOMPRESSED_SIZE = 1024 * 1024 * 1024
            mock_settings.UPLOAD_DIR = tmp_path
            mock_settings.MEDIA_DIR = tmp_path / "media"

            resp = client.post(
                "/api/conversations/upload",
                headers=auth_headers,
                files={"file": ("evil.zip", buf, "application/zip")},
            )
        assert resp.status_code == 400
        assert "path traversal" in resp.json()["detail"].lower()

    def test_upload_invalid_magic_bytes(self, client, auth_headers):
        """Upload de arquivo .zip com conteúdo não-ZIP (magic bytes errados) retorna 400."""
        fake_zip = io.BytesIO(b"this is not a zip at all")
        resp = client.post(
            "/api/conversations/upload",
            headers=auth_headers,
            files={"file": ("fake.zip", fake_zip, "application/zip")},
        )
        assert resp.status_code == 400


# ═════════════════════════════════════════════════════════════════════════════
# 2. List Conversations  GET /api/conversations/
# ═════════════════════════════════════════════════════════════════════════════

class TestListConversations:
    """Testes para o endpoint de listagem de conversas."""

    def test_list_conversations_empty(self, client, auth_headers):
        """Listagem sem conversas retorna lista vazia."""
        resp = client.get("/api/conversations/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_conversations_returns_items(self, client, auth_headers, db_session):
        """Listagem retorna conversas inseridas no DB."""
        convs = [_make_conversation(session_id=f"list-test-{i}") for i in range(3)]
        _seed_sync(db_session, *convs)

        resp = client.get("/api/conversations/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3

    def test_list_conversations_pagination(self, client, auth_headers, db_session):
        """Paginação skip/limit funciona corretamente."""
        convs = [_make_conversation(session_id=f"pag-test-{i}") for i in range(5)]
        _seed_sync(db_session, *convs)

        resp = client.get("/api/conversations/?skip=0&limit=2", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp2 = client.get("/api/conversations/?skip=2&limit=2", headers=auth_headers)
        assert resp2.status_code == 200
        assert len(resp2.json()) == 2

    def test_list_conversations_unauthorized(self, unauth_client):
        """Listagem sem auth retorna 403."""
        resp = unauth_client.get("/api/conversations/")
        assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# 3. Get Conversation  GET /api/conversations/{id}
# ═════════════════════════════════════════════════════════════════════════════

class TestGetConversation:
    """Testes para o endpoint de detalhes de uma conversa."""

    def test_get_conversation_success(self, client, auth_headers, db_session):
        """GET com ID válido retorna a conversa."""
        conv = _make_conversation(session_id="detail-test")
        _seed_sync(db_session, conv)

        resp = client.get(f"/api/conversations/{conv.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == conv.id
        assert data["session_id"] == "detail-test"

    def test_get_conversation_not_found(self, client, auth_headers):
        """GET com ID inexistente retorna 404."""
        resp = client.get("/api/conversations/nonexistent-id-999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_conversation_unauthorized(self, unauth_client):
        """GET sem auth retorna 403."""
        resp = unauth_client.get("/api/conversations/any-id")
        assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# 4. Get Messages  GET /api/conversations/{id}/messages
# ═════════════════════════════════════════════════════════════════════════════

class TestGetMessages:
    """Testes para o endpoint de mensagens de uma conversa."""

    def _seed_conversation_with_messages(self, db_session, num_messages=5):
        """Insere conversa com mensagens no DB e retorna o conversation id."""
        import asyncio
        conv = _make_conversation(session_id=f"msg-test-{uuid.uuid4().hex[:8]}")

        async def _seed():
            db_session.add(conv)
            await db_session.flush()
            for i in range(1, num_messages + 1):
                sender = "Maria" if i % 2 == 0 else "João"
                media = MediaType.AUDIO if i == 3 else MediaType.TEXT
                msg = _make_message(conv.id, i, sender=sender, media_type=media)
                db_session.add(msg)
            await db_session.commit()

        asyncio.get_event_loop().run_until_complete(_seed())
        return conv.id

    def test_get_messages_success(self, client, auth_headers, db_session):
        """GET mensagens retorna lista de mensagens."""
        conv_id = self._seed_conversation_with_messages(db_session)
        resp = client.get(f"/api/conversations/{conv_id}/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        # Verificar ordenação por sequence_number
        seqs = [m["sequence_number"] for m in data]
        assert seqs == sorted(seqs)

    def test_get_messages_media_only_filter(self, client, auth_headers, db_session):
        """Filtro media_only retorna apenas mensagens com mídia."""
        conv_id = self._seed_conversation_with_messages(db_session)
        resp = client.get(
            f"/api/conversations/{conv_id}/messages?media_only=true",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for msg in data:
            assert msg["media_type"] != "text"

    def test_get_messages_sender_filter(self, client, auth_headers, db_session):
        """Filtro por sender retorna apenas mensagens do remetente."""
        conv_id = self._seed_conversation_with_messages(db_session)
        resp = client.get(
            f"/api/conversations/{conv_id}/messages?sender=Maria",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for msg in data:
            assert msg["sender"] == "Maria"

    def test_get_messages_pagination(self, client, auth_headers, db_session):
        """Paginação skip/limit funciona para mensagens."""
        conv_id = self._seed_conversation_with_messages(db_session, num_messages=10)
        resp = client.get(
            f"/api/conversations/{conv_id}/messages?skip=0&limit=3",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_get_messages_unauthorized(self, unauth_client):
        """GET mensagens sem auth retorna 403."""
        resp = unauth_client.get("/api/conversations/any-id/messages")
        assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# 5. Delete Conversation  DELETE /api/conversations/{id}
# ═════════════════════════════════════════════════════════════════════════════

class TestDeleteConversation:
    """Testes para o endpoint de exclusão de conversa."""

    def test_delete_conversation_success(self, client, auth_headers, db_session):
        """DELETE com ID válido remove a conversa e retorna mensagem de sucesso."""
        conv = _make_conversation(session_id="del-test")
        _seed_sync(db_session, conv)

        resp = client.delete(f"/api/conversations/{conv.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert "removida" in resp.json()["message"].lower()

        # Verificar que foi realmente deletada
        resp2 = client.get(f"/api/conversations/{conv.id}", headers=auth_headers)
        assert resp2.status_code == 404

    def test_delete_conversation_not_found(self, client, auth_headers):
        """DELETE com ID inexistente retorna 404."""
        resp = client.delete("/api/conversations/nonexistent-id-999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_conversation_unauthorized(self, unauth_client):
        """DELETE sem auth retorna 403."""
        resp = unauth_client.delete("/api/conversations/any-id")
        assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# 6. Progress  GET /api/conversations/progress/{session_id}
# ═════════════════════════════════════════════════════════════════════════════

class TestProgress:
    """Testes para o endpoint de progresso de processamento."""

    def test_progress_from_db(self, client, auth_headers, db_session):
        """GET progress retorna dados de progresso do DB."""
        session_id = f"prog-{uuid.uuid4().hex[:8]}"
        conv = _make_conversation(
            session_id=session_id,
            status=ProcessingStatus.PROCESSING,
            progress=0.5,
            progress_message="Processando...",
            total_messages=100,
        )
        _seed_sync(db_session, conv)

        resp = client.get(
            f"/api/conversations/progress/{session_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["status"] == "processing"
        assert data["progress"] == 0.5

    def test_progress_not_found(self, client, auth_headers):
        """GET progress com session_id inexistente retorna 404."""
        resp = client.get(
            "/api/conversations/progress/nonexistent-session", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_progress_from_memory_store(self, client, auth_headers):
        """GET progress usa _progress_store quando não encontra no DB."""
        from app.routers.conversations import _progress_store

        session_id = f"mem-{uuid.uuid4().hex[:8]}"
        _progress_store[session_id] = {
            "status": ProcessingStatus.UPLOADING,
            "progress": 0.1,
            "message": "Upload em andamento",
        }

        try:
            resp = client.get(
                f"/api/conversations/progress/{session_id}", headers=auth_headers
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == session_id
            assert data["status"] == "uploading"
        finally:
            _progress_store.pop(session_id, None)

    def test_progress_unauthorized(self, unauth_client):
        """GET progress sem auth retorna 403."""
        resp = unauth_client.get("/api/conversations/progress/any-session")
        assert resp.status_code == 403
