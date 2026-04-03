"""
Testes para o router de exportação (export.py).
Cobre endpoints de export, mídia e status dos agentes.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models import (
    Conversation, Message, ProcessingStatus, MediaType, SentimentType,
)


# ─── Helper: seed completed conversation ─────────────────────────────────────

async def _seed_export_data(db_session: AsyncSession) -> Conversation:
    conv = Conversation(
        session_id="export-test-session",
        original_filename="test.zip",
        upload_path="/tmp/test.zip",
        extract_path="/tmp/media/test",
        status=ProcessingStatus.COMPLETED,
        progress=1.0,
        conversation_name="Export Test Conv",
        participants=["João", "Maria"],
        total_messages=2,
        total_media=0,
        date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        summary="Test summary",
        sentiment_overall=SentimentType.POSITIVE,
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


async def _seed_pending_conversation(db_session: AsyncSession) -> Conversation:
    conv = Conversation(
        session_id="pending-test-session",
        original_filename="pending.zip",
        upload_path="/tmp/pending.zip",
        extract_path="/tmp/media/pending",
        status=ProcessingStatus.PROCESSING,
        progress=0.5,
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


# ─── Fixture: DB session via engine ──────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_db(db_engine):
    """Creates a session, seeds data, and returns (conv, pending_conv)."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        conv = await _seed_export_data(session)
        pending = await _seed_pending_conversation(session)
    return conv, pending


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Export Conversation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestExportConversation:
    """POST /api/conversations/{id}/export"""

    @pytest.fixture(autouse=True)
    def _mock_exporters(self):
        """Mock all exporters so we don't need real generation logic."""
        fake_exporter = MagicMock()
        fake_exporter.return_value.generate.return_value = b"fake-file-content"

        targets = [
            "app.routers.export.PDFExporter",
            "app.routers.export.DOCXExporter",
            "app.routers.export.ExcelExporter",
            "app.routers.export.CSVExporter",
            "app.routers.export.HTMLExporter",
            "app.routers.export.JSONExporter",
        ]
        patches = [patch(t, fake_exporter) for t in targets]
        for p in patches:
            p.start()
        yield
        for p in patches:
            p.stop()

    def test_export_csv(self, client, auth_headers, seeded_db):
        conv, _ = seeded_db
        resp = client.post(
            f"/api/conversations/{conv.id}/export",
            json={"format": "csv"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]

    def test_export_json(self, client, auth_headers, seeded_db):
        conv, _ = seeded_db
        resp = client.post(
            f"/api/conversations/{conv.id}/export",
            json={"format": "json"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

    def test_export_html(self, client, auth_headers, seeded_db):
        conv, _ = seeded_db
        resp = client.post(
            f"/api/conversations/{conv.id}/export",
            json={"format": "html"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_export_pdf(self, client, auth_headers, seeded_db):
        conv, _ = seeded_db
        resp = client.post(
            f"/api/conversations/{conv.id}/export",
            json={"format": "pdf"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]

    def test_export_docx(self, client, auth_headers, seeded_db):
        conv, _ = seeded_db
        resp = client.post(
            f"/api/conversations/{conv.id}/export",
            json={"format": "docx"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_export_nonexistent_conversation_returns_404(self, client, auth_headers):
        resp = client.post(
            "/api/conversations/nonexistent-id-999/export",
            json={"format": "csv"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_export_non_completed_conversation_returns_400(
        self, client, auth_headers, seeded_db
    ):
        _, pending = seeded_db
        resp = client.post(
            f"/api/conversations/{pending.id}/export",
            json={"format": "csv"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_export_invalid_format_returns_422(self, client, auth_headers, seeded_db):
        conv, _ = seeded_db
        resp = client.post(
            f"/api/conversations/{conv.id}/export",
            json={"format": "invalid_fmt"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_export_unauthorized_returns_403(self, app, seeded_db):
        from app.auth import get_current_user
        app.dependency_overrides.pop(get_current_user, None)
        from fastapi.testclient import TestClient
        conv, _ = seeded_db
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(
                f"/api/conversations/{conv.id}/export",
                json={"format": "csv"},
            )
            # 401 or 403 depending on auth implementation
            assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Media Endpoints Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMediaEndpoints:
    """GET /api/media/{conv_id}/{filename} and /info"""

    def test_media_nonexistent_returns_404(self, client, auth_headers, seeded_db):
        conv, _ = seeded_db
        resp = client.get(
            f"/api/media/{conv.id}/nonexistent_file.opus",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_media_path_traversal_returns_400(self, client, auth_headers, seeded_db):
        conv, _ = seeded_db
        resp = client.get(
            f"/api/media/{conv.id}/..%2F..%2Fetc%2Fpasswd",
            headers=auth_headers,
        )
        # The router checks for ".." in filename; may return 400 or 404
        assert resp.status_code in (400, 404)

    def test_media_info_nonexistent_returns_404(self, client, auth_headers, seeded_db):
        conv, _ = seeded_db
        resp = client.get(
            f"/api/media/{conv.id}/nonexistent_file.opus/info",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_media_unauthorized(self, app, seeded_db):
        from app.auth import get_current_user
        app.dependency_overrides.pop(get_current_user, None)
        from fastapi.testclient import TestClient
        conv, _ = seeded_db
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get(f"/api/media/{conv.id}/file.opus")
            assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Agents Status Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentsStatus:
    """GET /api/agents/status"""

    def test_agents_status_returns_response(self, client, auth_headers):
        resp = client.get("/api/agents/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Even without orchestrator, it should return a message
        assert isinstance(data, dict)

    def test_agents_status_unauthorized(self, app):
        from app.auth import get_current_user
        app.dependency_overrides.pop(get_current_user, None)
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/agents/status")
            assert resp.status_code in (401, 403)
