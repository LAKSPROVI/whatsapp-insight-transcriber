"""
Testes para o router de pesquisa (search).
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models import Conversation, Message, ProcessingStatus, MediaType, Base
from app.routers.search import _highlight, _score_message


# ─── Fixture: seed search data via engine ────────────────────────────────────

@pytest.fixture
def seeded_app(app, db_engine):
    """
    Seeds the test database with search data and returns (app, conv_id).
    Uses the same engine the app override points to.
    """
    import asyncio

    async def _seed():
        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            conv = Conversation(
                session_id="search-test-session",
                original_filename="test.zip",
                upload_path="/tmp/test.zip",
                extract_path="/tmp/media/test",
                status=ProcessingStatus.COMPLETED,
                progress=1.0,
                conversation_name="Grupo Trabalho",
                participants=["João", "Maria"],
                total_messages=3,
                total_media=0,
            )
            session.add(conv)
            await session.commit()
            await session.refresh(conv)

            messages_data = [
                ("João", "Vamos marcar a reunião para amanhã"),
                ("Maria", "Ok, pode ser às 14h na sala de reunião"),
                ("João", "Perfeito, confirmado"),
            ]
            for i, (sender, msg_text) in enumerate(messages_data):
                msg = Message(
                    conversation_id=conv.id,
                    sequence_number=i + 1,
                    timestamp=datetime(2026, 1, 1, 8, i, tzinfo=timezone.utc),
                    sender=sender,
                    original_text=msg_text,
                    media_type=MediaType.TEXT,
                )
                session.add(msg)
            await session.commit()
            return conv.id

    loop = asyncio.new_event_loop()
    conv_id = loop.run_until_complete(_seed())
    loop.close()
    return app, conv_id


@pytest.fixture
def seeded_client(seeded_app):
    """TestClient with seeded data."""
    from fastapi.testclient import TestClient

    app, conv_id = seeded_app
    with TestClient(app, raise_server_exceptions=False) as c:
        c._conv_id = conv_id  # attach for test access
        yield c


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Search Messages
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchMessages:
    """Testes para GET /api/search/messages."""

    def test_search_messages_returns_results(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/messages", params={"q": "reunião"}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "reunião"
        assert data["total"] >= 1
        assert len(data["results"]) >= 1

    def test_search_messages_empty_results(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/messages",
            params={"q": "xyznonexistent"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []

    def test_search_messages_pagination_limit(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/messages",
            params={"q": "reunião", "limit": 1, "offset": 0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 1
        assert len(data["results"]) <= 1

    def test_search_messages_pagination_offset_beyond(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/messages",
            params={"q": "reunião", "limit": 50, "offset": 1000},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_search_messages_filter_by_sender(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/messages",
            params={"q": "reunião", "sender": "João"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        for item in resp.json()["results"]:
            assert item["sender"] == "João"

    def test_search_messages_filter_by_conversation_id(self, seeded_client, auth_headers):
        conv_id = seeded_client._conv_id
        resp = seeded_client.get(
            "/api/search/messages",
            params={"q": "reunião", "conversation_id": conv_id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        for item in resp.json()["results"]:
            assert item["conversation_id"] == conv_id

    def test_search_messages_regex(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/messages",
            params={"q": "reuni[ãa]o", "regex": "true"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_search_messages_invalid_regex(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/messages",
            params={"q": "[invalid(", "regex": "true"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_search_messages_sort_chronological(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/messages",
            params={"q": "reunião", "sort_by": "chronological"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        if len(results) >= 2:
            timestamps = [r["timestamp"] for r in results]
            assert timestamps == sorted(timestamps)

    def test_search_messages_sort_relevance(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/messages",
            params={"q": "reunião", "sort_by": "relevance"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        if len(results) >= 2:
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_search_messages_unauthorized(self, app):
        """Sem override de auth, token inválido retorna 401 ou 403."""
        from fastapi.testclient import TestClient
        from app.auth import get_current_user

        # Remove auth override to test real auth
        app.dependency_overrides.pop(get_current_user, None)
        try:
            with TestClient(app, raise_server_exceptions=False) as c:
                bad_headers = {"Authorization": "Bearer invalid-token-abc"}
                resp = c.get(
                    "/api/search/messages", params={"q": "test"}, headers=bad_headers
                )
                assert resp.status_code in (401, 403)
        finally:
            # Restore override
            async def _override():
                from app.auth import UserInfo
                return UserInfo(username="admin", full_name="Admin", is_admin=True)
            app.dependency_overrides[get_current_user] = _override


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Search Conversations
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchConversations:
    """Testes para GET /api/search/conversations."""

    def test_search_conversations_returns_results(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/conversations",
            params={"q": "Trabalho"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "Trabalho"
        assert data["total"] >= 1
        assert any("Trabalho" in r["conversation_name"] for r in data["results"])

    def test_search_conversations_empty_results(self, seeded_client, auth_headers):
        resp = seeded_client.get(
            "/api/search/conversations",
            params={"q": "xyznonexistent"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []

    def test_search_conversations_unauthorized(self, app):
        """Sem override de auth, token inválido retorna 401 ou 403."""
        from fastapi.testclient import TestClient
        from app.auth import get_current_user

        app.dependency_overrides.pop(get_current_user, None)
        try:
            with TestClient(app, raise_server_exceptions=False) as c:
                bad_headers = {"Authorization": "Bearer invalid-token-abc"}
                resp = c.get(
                    "/api/search/conversations",
                    params={"q": "test"},
                    headers=bad_headers,
                )
                assert resp.status_code in (401, 403)
        finally:
            async def _override():
                from app.auth import UserInfo
                return UserInfo(username="admin", full_name="Admin", is_admin=True)
            app.dependency_overrides[get_current_user] = _override


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Highlight Function (unit tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHighlight:
    """Testes unitários para _highlight."""

    def test_highlight_normal_text(self):
        result = _highlight("Vamos marcar a reunião para amanhã", "reunião")
        assert "**reunião**" in result

    def test_highlight_regex(self):
        result = _highlight("Vamos marcar a reunião para amanhã", r"reuni[ãa]o", is_regex=True)
        assert "**reunião**" in result

    def test_highlight_empty_query(self):
        text = "Texto qualquer"
        assert _highlight(text, "") == text

    def test_highlight_none_text(self):
        assert _highlight(None, "test") == ""

    def test_highlight_case_insensitive(self):
        result = _highlight("REUNIÃO marcada", "reunião")
        assert "**REUNIÃO**" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Score Function (unit tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestScoreMessage:
    """Testes unitários para _score_message."""

    def test_higher_score_for_more_occurrences(self):
        msg_one = Message(
            conversation_id="c1",
            sequence_number=1,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            sender="A",
            original_text="reunião",
            media_type=MediaType.TEXT,
        )
        msg_many = Message(
            conversation_id="c1",
            sequence_number=2,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            sender="A",
            original_text="reunião reunião reunião",
            media_type=MediaType.TEXT,
        )
        score_one = _score_message(msg_one, "reunião")
        score_many = _score_message(msg_many, "reunião")
        assert score_many > score_one

    def test_bonus_for_text_at_start(self):
        msg_start = Message(
            conversation_id="c1",
            sequence_number=1,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            sender="A",
            original_text="reunião marcada",
            media_type=MediaType.TEXT,
        )
        msg_middle = Message(
            conversation_id="c1",
            sequence_number=2,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            sender="A",
            original_text="a reunião marcada",
            media_type=MediaType.TEXT,
        )
        score_start = _score_message(msg_start, "reunião")
        score_middle = _score_message(msg_middle, "reunião")
        # Both have 1 occurrence (10 pts), but msg_start gets +5 bonus
        assert score_start == score_middle + 5.0
