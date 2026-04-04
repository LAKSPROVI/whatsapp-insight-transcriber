"""
Testes para o router de conversas (upload, listagem, detalhes, mensagens, delete, progresso).
"""
import io
import uuid
import zipfile
import httpx
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models import Conversation, Message, ProcessingStatus, MediaType
from app.dependencies import get_orchestrator
from app.auth import get_current_user, UserInfo


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


async def _seed(db_session, *objs):
    """Insere objetos no DB de forma assíncrona."""
    for obj in objs:
        db_session.add(obj)
    await db_session.commit()


# ─── Fixture: mock orchestrator ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def override_orchestrator(app):
    """Substitui o orchestrator real por um mock em todos os testes."""
    mock_orch = AsyncMock()
    app.dependency_overrides[get_orchestrator] = lambda: mock_orch
    yield mock_orch
    app.dependency_overrides.pop(get_orchestrator, None)


# ─── Fixture: client sem auth (para testes de 401/403) ───────────────────────

@pytest_asyncio.fixture
async def unauth_client(app):
    """Client que simula usuário não autenticado (get_current_user levanta 403)."""

    async def _deny():
        raise HTTPException(status_code=403, detail="Not authenticated")

    app.dependency_overrides[get_current_user] = _deny
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def non_admin_client(app):
    """Client autenticado como usuário comum para validar isolamento por owner."""

    async def _user():
        return UserInfo(id="regular-user-id", username="regular", full_name="Regular User", is_admin=False)

    app.dependency_overrides[get_current_user] = _user
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ═════════════════════════════════════════════════════════════════════════════
# 1. Upload Endpoint  POST /api/conversations/upload
# ═════════════════════════════════════════════════════════════════════════════

class TestUpload:
    """Testes para o endpoint de upload."""

    async def test_upload_valid_zip(self, client, auth_headers, tmp_path):
        """Upload de ZIP válido retorna 200 com session_id."""
        zip_buf = make_test_zip()
        with patch("app.routers.conversations.settings") as mock_settings:
            mock_settings.MAX_UPLOAD_SIZE_MB = 100
            mock_settings.MAX_ZIP_FILES = 5000
            mock_settings.MAX_ZIP_UNCOMPRESSED_SIZE = 1024 * 1024 * 1024
            mock_settings.UPLOAD_DIR = tmp_path
            mock_settings.MEDIA_DIR = tmp_path / "media"
            mock_settings.DATA_RETENTION_DAYS = 90

            resp = await client.post(
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

    async def test_upload_non_zip_file(self, client, auth_headers):
        """Upload de arquivo não-ZIP retorna 400."""
        fake_file = io.BytesIO(b"plain text content")
        resp = await client.post(
            "/api/conversations/upload",
            headers=auth_headers,
            files={"file": ("notes.txt", fake_file, "text/plain")},
        )
        assert resp.status_code == 400
        assert "zip" in resp.json()["detail"].lower()

    async def test_upload_without_auth(self, unauth_client):
        """Upload sem token de autenticação retorna 403."""
        zip_buf = make_test_zip()
        resp = await unauth_client.post(
            "/api/conversations/upload",
            files={"file": ("chat.zip", zip_buf, "application/zip")},
        )
        assert resp.status_code == 403

    async def test_upload_oversized_file(self, client, auth_headers):
        """Upload de arquivo maior que o limite retorna 413."""
        zip_buf = make_test_zip()
        with patch("app.routers.conversations.settings") as mock_settings:
            # Limitar a 0 MB para forçar 413
            mock_settings.MAX_UPLOAD_SIZE_MB = 0
            resp = await client.post(
                "/api/conversations/upload",
                headers=auth_headers,
                files={"file": ("chat.zip", zip_buf, "application/zip")},
            )
        assert resp.status_code == 413

    async def test_upload_zip_with_path_traversal(self, client, auth_headers, tmp_path):
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

            resp = await client.post(
                "/api/conversations/upload",
                headers=auth_headers,
                files={"file": ("evil.zip", buf, "application/zip")},
            )
        assert resp.status_code == 400
        assert "path traversal" in resp.json()["detail"].lower()

    async def test_upload_invalid_magic_bytes(self, client, auth_headers):
        """Upload de arquivo .zip com conteúdo não-ZIP (magic bytes errados) retorna 400."""
        fake_zip = io.BytesIO(b"this is not a zip at all")
        resp = await client.post(
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

    async def test_list_conversations_empty(self, client, auth_headers):
        """Listagem sem conversas retorna lista vazia."""
        resp = await client.get("/api/conversations/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_conversations_returns_items(self, client, auth_headers, db_session):
        """Listagem retorna conversas inseridas no DB."""
        convs = [_make_conversation(session_id=f"list-test-{i}") for i in range(3)]
        await _seed(db_session, *convs)

        resp = await client.get("/api/conversations/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3

    async def test_list_conversations_pagination(self, client, auth_headers, db_session):
        """Paginação skip/limit funciona corretamente."""
        convs = [_make_conversation(session_id=f"pag-test-{i}") for i in range(5)]
        await _seed(db_session, *convs)

        resp = await client.get("/api/conversations/?skip=0&limit=2", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp2 = await client.get("/api/conversations/?skip=2&limit=2", headers=auth_headers)
        assert resp2.status_code == 200
        assert len(resp2.json()) == 2

    async def test_list_conversations_unauthorized(self, unauth_client):
        """Listagem sem auth retorna 403."""
        resp = await unauth_client.get("/api/conversations/")
        assert resp.status_code == 403

    async def test_list_conversations_filters_by_owner_for_non_admin(self, non_admin_client, db_session):
        own = _make_conversation(session_id="owned-conv", owner_id="regular-user-id")
        foreign = _make_conversation(session_id="foreign-conv", owner_id="someone-else-id")
        await _seed(db_session, own, foreign)

        resp = await non_admin_client.get("/api/conversations/")
        assert resp.status_code == 200
        data = resp.json()
        ids = {item["id"] for item in data}
        assert own.id in ids
        assert foreign.id not in ids


# ═════════════════════════════════════════════════════════════════════════════
# 3. Get Conversation  GET /api/conversations/{id}
# ═════════════════════════════════════════════════════════════════════════════

class TestGetConversation:
    """Testes para o endpoint de detalhes de uma conversa."""

    async def test_get_conversation_success(self, client, auth_headers, db_session):
        """GET com ID válido retorna a conversa."""
        conv = _make_conversation(session_id="detail-test")
        await _seed(db_session, conv)

        resp = await client.get(f"/api/conversations/{conv.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == conv.id
        assert data["session_id"] == "detail-test"

    async def test_get_conversation_not_found(self, client, auth_headers):
        """GET com ID inexistente retorna 404."""
        resp = await client.get("/api/conversations/nonexistent-id-999", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_conversation_unauthorized(self, unauth_client):
        """GET sem auth retorna 403."""
        resp = await unauth_client.get("/api/conversations/any-id")
        assert resp.status_code == 403

    async def test_get_conversation_hidden_when_not_owner(self, non_admin_client, db_session):
        conv = _make_conversation(session_id="foreign-detail", owner_id="someone-else-id")
        await _seed(db_session, conv)

        resp = await non_admin_client.get(f"/api/conversations/{conv.id}")
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 4. Get Messages  GET /api/conversations/{id}/messages
# ═════════════════════════════════════════════════════════════════════════════

class TestGetMessages:
    """Testes para o endpoint de mensagens de uma conversa."""

    async def _seed_conversation_with_messages(self, db_session, num_messages=5):
        """Insere conversa com mensagens no DB e retorna o conversation id."""
        conv = _make_conversation(session_id=f"msg-test-{uuid.uuid4().hex[:8]}")
        db_session.add(conv)
        await db_session.flush()
        for i in range(1, num_messages + 1):
            sender = "Maria" if i % 2 == 0 else "João"
            media = MediaType.AUDIO if i == 3 else MediaType.TEXT
            msg = _make_message(conv.id, i, sender=sender, media_type=media)
            db_session.add(msg)
        await db_session.commit()
        return conv.id

    async def test_get_messages_success(self, client, auth_headers, db_session):
        """GET mensagens retorna lista de mensagens."""
        conv_id = await self._seed_conversation_with_messages(db_session)
        resp = await client.get(f"/api/conversations/{conv_id}/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        # Verificar ordenação por sequence_number
        seqs = [m["sequence_number"] for m in data]
        assert seqs == sorted(seqs)

    async def test_get_messages_media_only_filter(self, client, auth_headers, db_session):
        """Filtro media_only retorna apenas mensagens com mídia."""
        conv_id = await self._seed_conversation_with_messages(db_session)
        resp = await client.get(
            f"/api/conversations/{conv_id}/messages?media_only=true",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for msg in data:
            assert msg["media_type"] != "text"

    async def test_get_messages_sender_filter(self, client, auth_headers, db_session):
        """Filtro por sender retorna apenas mensagens do remetente."""
        conv_id = await self._seed_conversation_with_messages(db_session)
        resp = await client.get(
            f"/api/conversations/{conv_id}/messages?sender=Maria",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for msg in data:
            assert msg["sender"] == "Maria"

    async def test_get_messages_pagination(self, client, auth_headers, db_session):
        """Paginação skip/limit funciona para mensagens."""
        conv_id = await self._seed_conversation_with_messages(db_session, num_messages=10)
        resp = await client.get(
            f"/api/conversations/{conv_id}/messages?skip=0&limit=3",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    async def test_get_messages_unauthorized(self, unauth_client):
        """GET mensagens sem auth retorna 403."""
        resp = await unauth_client.get("/api/conversations/any-id/messages")
        assert resp.status_code == 403

    async def test_get_messages_hidden_when_not_owner(self, non_admin_client, db_session):
        conv = _make_conversation(session_id="foreign-msgs", owner_id="someone-else-id")
        await _seed(db_session, conv)

        resp = await non_admin_client.get(f"/api/conversations/{conv.id}/messages")
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 5. Delete Conversation  DELETE /api/conversations/{id}
# ═════════════════════════════════════════════════════════════════════════════

class TestDeleteConversation:
    """Testes para o endpoint de exclusão de conversa."""

    async def test_delete_conversation_success(self, client, auth_headers, db_session):
        """DELETE com ID válido remove a conversa e retorna mensagem de sucesso."""
        conv = _make_conversation(session_id="del-test")
        await _seed(db_session, conv)

        resp = await client.delete(f"/api/conversations/{conv.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert "removida" in resp.json()["message"].lower()

        # Verificar que foi realmente deletada
        resp2 = await client.get(f"/api/conversations/{conv.id}", headers=auth_headers)
        assert resp2.status_code == 404

    async def test_delete_conversation_not_found(self, client, auth_headers):
        """DELETE com ID inexistente retorna 404."""
        resp = await client.delete("/api/conversations/nonexistent-id-999", headers=auth_headers)
        assert resp.status_code == 404

    async def test_delete_conversation_unauthorized(self, unauth_client):
        """DELETE sem auth retorna 403."""
        resp = await unauth_client.delete("/api/conversations/any-id")
        assert resp.status_code == 403

    async def test_delete_conversation_hidden_when_not_owner(self, non_admin_client, db_session):
        conv = _make_conversation(session_id="foreign-del", owner_id="someone-else-id")
        await _seed(db_session, conv)

        resp = await non_admin_client.delete(f"/api/conversations/{conv.id}")
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 6. Progress  GET /api/conversations/progress/{session_id}
# ═════════════════════════════════════════════════════════════════════════════

class TestProgress:
    """Testes para o endpoint de progresso de processamento."""

    async def test_progress_from_db(self, client, auth_headers, db_session):
        """GET progress retorna dados de progresso do DB."""
        session_id = f"prog-{uuid.uuid4().hex[:8]}"
        conv = _make_conversation(
            session_id=session_id,
            status=ProcessingStatus.PROCESSING,
            progress=0.5,
            progress_message="Processando...",
            total_messages=100,
        )
        await _seed(db_session, conv)

        resp = await client.get(
            f"/api/conversations/progress/{session_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["status"] == "processing"
        assert data["progress"] == 0.5

    async def test_progress_not_found(self, client, auth_headers):
        """GET progress com session_id inexistente retorna 404."""
        resp = await client.get(
            "/api/conversations/progress/nonexistent-session", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_progress_from_memory_store(self, client, auth_headers):
        """GET progress usa _progress_store quando não encontra no DB."""
        from app.routers.conversations import _progress_store

        session_id = f"mem-{uuid.uuid4().hex[:8]}"
        _progress_store[session_id] = {
            "status": ProcessingStatus.UPLOADING,
            "progress": 0.1,
            "message": "Upload em andamento",
        }

        try:
            resp = await client.get(
                f"/api/conversations/progress/{session_id}", headers=auth_headers
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == session_id
            assert data["status"] == "uploading"
        finally:
            _progress_store.pop(session_id, None)

    async def test_progress_unauthorized(self, unauth_client):
        """GET progress sem auth retorna 403."""
        resp = await unauth_client.get("/api/conversations/progress/any-session")
        assert resp.status_code == 403
