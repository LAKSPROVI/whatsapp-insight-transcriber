"""
Testes para o serviço de exportação (CSV, HTML, JSON).
Usa MagicMock para evitar dependência de banco de dados.
"""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models import MediaType, SentimentType, ProcessingStatus
from app.services.export_service import (
    sanitize_for_pdf,
    _format_timestamp,
    _sentiment_label,
    _media_type_label,
    CSVExporter,
    HTMLExporter,
    JSONExporter,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _make_message(
    sequence: int,
    sender: str,
    text: str | None,
    media_type: MediaType = MediaType.TEXT,
    timestamp: datetime | None = None,
    transcription: str | None = None,
    description: str | None = None,
    ocr_text: str | None = None,
    media_filename: str | None = None,
    media_metadata: dict | None = None,
    sentiment: SentimentType | None = None,
    sentiment_score: float | None = None,
    is_key_moment: bool = False,
) -> MagicMock:
    msg = MagicMock()
    msg.sequence_number = sequence
    msg.sender = sender
    msg.original_text = text
    msg.media_type = media_type
    msg.timestamp = timestamp or datetime(2026, 1, 1, 10, sequence, 0, tzinfo=timezone.utc)
    msg.transcription = transcription
    msg.description = description
    msg.ocr_text = ocr_text
    msg.media_filename = media_filename
    msg.media_metadata = media_metadata
    msg.sentiment = sentiment
    msg.sentiment_score = sentiment_score
    msg.is_key_moment = is_key_moment
    return msg


@pytest.fixture
def mock_conversation() -> MagicMock:
    conv = MagicMock()
    conv.id = "conv-1"
    conv.conversation_name = "Test Conv"
    conv.participants = ["João", "Maria"]
    conv.total_messages = 3
    conv.total_media = 1
    conv.date_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    conv.date_end = datetime(2026, 1, 2, tzinfo=timezone.utc)
    conv.summary = "Test summary"
    conv.topics = ["topic1"]
    conv.keywords = ["kw1"]
    conv.contradictions = []
    conv.key_moments = []
    conv.word_frequency = {"hello": 5}
    conv.sentiment_overall = SentimentType.POSITIVE
    conv.sentiment_score = 0.8
    conv.status = ProcessingStatus.COMPLETED
    return conv


@pytest.fixture
def mock_messages() -> list[MagicMock]:
    return [
        _make_message(
            sequence=1,
            sender="João",
            text="Bom dia pessoal!",
            media_type=MediaType.TEXT,
            timestamp=datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
            sentiment=SentimentType.POSITIVE,
            sentiment_score=0.9,
        ),
        _make_message(
            sequence=2,
            sender="Maria",
            text=None,
            media_type=MediaType.AUDIO,
            timestamp=datetime(2026, 1, 1, 8, 5, 0, tzinfo=timezone.utc),
            transcription="Olá pessoal, tudo bem?",
            description="Audio message from Maria",
            media_filename="audio-001.opus",
            media_metadata={"duration_formatted": "0:15", "format": "opus"},
        ),
        _make_message(
            sequence=3,
            sender="João",
            text="Tudo ótimo!",
            media_type=MediaType.TEXT,
            timestamp=datetime(2026, 1, 1, 8, 10, 0, tzinfo=timezone.utc),
            is_key_moment=True,
        ),
    ]


# ─── Helper Functions ────────────────────────────────────────────────────────


class TestSanitizeForPdf:
    def test_removes_chars_outside_bmp(self):
        # Emoji 🎉 is U+1F389, outside BMP
        result = sanitize_for_pdf("Hello 🎉 World")
        assert result == "Hello  World"

    def test_preserves_bmp_chars(self):
        text = "Olá, João! Tudo bem?"
        assert sanitize_for_pdf(text) == text

    def test_handles_empty_string(self):
        assert sanitize_for_pdf("") == ""

    def test_handles_none(self):
        assert sanitize_for_pdf(None) == ""


class TestFormatTimestamp:
    def test_formats_datetime_correctly(self):
        dt = datetime(2026, 3, 15, 14, 30, 45)
        result = _format_timestamp(dt)
        assert result == "15/03/2026 às 14:30:45"

    def test_returns_dash_for_none(self):
        assert _format_timestamp(None) == "—"


class TestSentimentLabel:
    def test_positive(self):
        assert _sentiment_label(SentimentType.POSITIVE) == "😊 Positivo"

    def test_negative(self):
        assert _sentiment_label(SentimentType.NEGATIVE) == "😔 Negativo"

    def test_neutral(self):
        assert _sentiment_label(SentimentType.NEUTRAL) == "😐 Neutro"

    def test_mixed(self):
        assert _sentiment_label(SentimentType.MIXED) == "🤔 Misto"

    def test_none(self):
        assert _sentiment_label(None) == "—"


class TestMediaTypeLabel:
    def test_image(self):
        assert _media_type_label(MediaType.IMAGE) == "🖼️ Imagem"

    def test_audio(self):
        assert _media_type_label(MediaType.AUDIO) == "🎵 Áudio"

    def test_video(self):
        assert _media_type_label(MediaType.VIDEO) == "🎬 Vídeo"

    def test_document(self):
        assert _media_type_label(MediaType.DOCUMENT) == "📄 Documento"

    def test_sticker(self):
        assert _media_type_label(MediaType.STICKER) == "🎭 Sticker"

    def test_deleted(self):
        assert _media_type_label(MediaType.DELETED) == "🗑️ Mensagem Deletada"

    def test_text_returns_default(self):
        # TEXT is not in the labels dict, so should return default
        assert _media_type_label(MediaType.TEXT) == "📎 Mídia"


# ─── CSVExporter ─────────────────────────────────────────────────────────────


class TestCSVExporter:
    def test_generate_returns_bytes(self, mock_conversation, mock_messages):
        exporter = CSVExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        assert isinstance(result, bytes)

    def test_output_starts_with_utf8_bom(self, mock_conversation, mock_messages):
        exporter = CSVExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        assert result[:3] == b"\xef\xbb\xbf"

    def test_output_contains_headers(self, mock_conversation, mock_messages):
        exporter = CSVExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        text = result[3:].decode("utf-8")  # skip BOM
        lines = text.strip().split("\n")
        header = lines[0]
        for col in ["timestamp", "sender", "message", "type", "is_system"]:
            assert col in header

    def test_messages_appear_in_output(self, mock_conversation, mock_messages):
        exporter = CSVExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        text = result.decode("utf-8-sig")
        assert "João" in text
        assert "Maria" in text
        assert "Bom dia pessoal!" in text

    def test_transcriptions_included(self, mock_conversation, mock_messages):
        exporter = CSVExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        text = result.decode("utf-8-sig")
        assert "Olá pessoal, tudo bem?" in text
        assert "Transcrição" in text

    def test_descriptions_included(self, mock_conversation, mock_messages):
        exporter = CSVExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        text = result.decode("utf-8-sig")
        assert "Audio message from Maria" in text
        assert "Descrição" in text

    def test_correct_number_of_rows(self, mock_conversation, mock_messages):
        exporter = CSVExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        text = result.decode("utf-8-sig").strip()
        lines = text.split("\n")
        # 1 header + 3 messages = 4 lines
        assert len(lines) == 4


# ─── HTMLExporter ────────────────────────────────────────────────────────────


class TestHTMLExporter:
    def test_generate_returns_bytes(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        assert isinstance(result, bytes)

    def test_output_is_valid_utf8(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        html = result.decode("utf-8")
        assert "<!DOCTYPE html>" in html

    def test_contains_conversation_name(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        html = result.decode("utf-8")
        assert "Test Conv" in html

    def test_contains_participant_names(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        html = result.decode("utf-8")
        assert "João" in html
        assert "Maria" in html

    def test_contains_messages(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        html = result.decode("utf-8")
        assert "Bom dia pessoal!" in html
        assert "Tudo ótimo!" in html

    def test_has_search_filter_javascript(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        html = result.decode("utf-8")
        assert "filterMessages" in html
        assert "searchBox" in html
        assert "senderFilter" in html

    def test_includes_summary_when_enabled(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages, options={"include_summary": True})
        html = result.decode("utf-8")
        assert "Test summary" in html

    def test_excludes_summary_when_disabled(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages, options={"include_summary": False})
        html = result.decode("utf-8")
        assert "Test summary" not in html

    def test_includes_statistics_section(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages, options={"include_statistics": True})
        html = result.decode("utf-8")
        assert "Total de Mensagens" in html

    def test_contains_transcription_in_html(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        html = result.decode("utf-8")
        assert "Olá pessoal, tudo bem?" in html

    def test_media_badge_for_non_text(self, mock_conversation, mock_messages):
        exporter = HTMLExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        html = result.decode("utf-8")
        assert "media-badge" in html


# ─── JSONExporter ────────────────────────────────────────────────────────────


class TestJSONExporter:
    def test_generate_returns_bytes(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        assert isinstance(result, bytes)

    def test_output_is_valid_json(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        data = json.loads(result.decode("utf-8"))
        assert isinstance(data, dict)

    def test_contains_metadata_section(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        data = json.loads(result.decode("utf-8"))
        assert "metadata" in data
        assert "exporter" in data["metadata"]
        assert "exported_at" in data["metadata"]
        assert "format_version" in data["metadata"]

    def test_contains_conversation_section(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        data = json.loads(result.decode("utf-8"))
        assert "conversation" in data
        conv = data["conversation"]
        assert conv["id"] == "conv-1"
        assert conv["name"] == "Test Conv"
        assert conv["participants"] == ["João", "Maria"]
        assert conv["total_messages"] == 3
        assert conv["total_media"] == 1

    def test_contains_messages_section(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        data = json.loads(result.decode("utf-8"))
        assert "messages" in data
        assert len(data["messages"]) == 3

    def test_messages_have_required_fields(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        data = json.loads(result.decode("utf-8"))
        for msg in data["messages"]:
            assert "sequence" in msg
            assert "timestamp" in msg
            assert "sender" in msg
            assert "text" in msg
            assert "type" in msg
            assert "is_key_moment" in msg

    def test_includes_analysis_when_summary_enabled(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages, options={"include_summary": True})
        data = json.loads(result.decode("utf-8"))
        assert "analysis" in data
        assert data["analysis"]["summary"] == "Test summary"
        assert data["analysis"]["topics"] == ["topic1"]
        assert data["analysis"]["keywords"] == ["kw1"]
        assert data["analysis"]["sentiment_overall"] == "positive"
        assert data["analysis"]["sentiment_score"] == 0.8

    def test_excludes_analysis_when_summary_disabled(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages, options={"include_summary": False})
        data = json.loads(result.decode("utf-8"))
        assert "analysis" not in data

    def test_includes_contradictions_when_sentiment_enabled(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages, options={"include_sentiment_analysis": True})
        data = json.loads(result.decode("utf-8"))
        assert "contradictions" in data
        assert "key_moments" in data

    def test_excludes_contradictions_when_sentiment_disabled(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(
            mock_conversation, mock_messages,
            options={"include_sentiment_analysis": False, "include_summary": False},
        )
        data = json.loads(result.decode("utf-8"))
        assert "contradictions" not in data
        assert "key_moments" not in data

    def test_audio_message_has_transcription(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        data = json.loads(result.decode("utf-8"))
        audio_msg = data["messages"][1]
        assert audio_msg["type"] == "audio"
        assert audio_msg["transcription"] == "Olá pessoal, tudo bem?"
        assert audio_msg["description"] == "Audio message from Maria"
        assert audio_msg["media_filename"] == "audio-001.opus"

    def test_key_moment_flag(self, mock_conversation, mock_messages):
        exporter = JSONExporter()
        result = exporter.generate(mock_conversation, mock_messages)
        data = json.loads(result.decode("utf-8"))
        assert data["messages"][0]["is_key_moment"] is False
        assert data["messages"][2]["is_key_moment"] is True
