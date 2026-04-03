"""
Testes de validação dos schemas Pydantic.
"""
import pytest
from pydantic import ValidationError

from app.schemas import (
    ChatRequest,
    ExportRequest,
    ConversationCreate,
    SearchMessageRequest,
)


class TestChatRequestValidation:
    """Testes para validação do ChatRequest."""

    def test_chat_request_valid(self):
        """ChatRequest válido aceita dados corretos."""
        req = ChatRequest(
            conversation_id="conv-abc123",
            message="Qual o resumo da conversa?",
            include_context=True,
        )
        assert req.conversation_id == "conv-abc123"
        assert req.message == "Qual o resumo da conversa?"

    def test_chat_request_empty_message(self):
        """ChatRequest rejeita mensagem vazia."""
        with pytest.raises(ValidationError):
            ChatRequest(
                conversation_id="conv-abc123",
                message="",
            )

    def test_chat_request_sanitization(self):
        """ChatRequest sanitiza caracteres de controle."""
        req = ChatRequest(
            conversation_id="conv-abc123",
            message="Mensagem com \x00null byte\x07 e controle",
        )
        # Null bytes e caracteres de controle devem ser removidos
        assert "\x00" not in req.message
        assert "\x07" not in req.message
        assert "Mensagem com" in req.message

    def test_chat_request_max_length(self):
        """ChatRequest rejeita mensagem que excede limite."""
        with pytest.raises(ValidationError):
            ChatRequest(
                conversation_id="conv-abc123",
                message="x" * 10001,  # Limite é 10000
            )

    def test_chat_request_invalid_conversation_id(self):
        """ChatRequest rejeita conversation_id com caracteres inválidos."""
        with pytest.raises(ValidationError):
            ChatRequest(
                conversation_id="conv/../../../etc/passwd",
                message="Teste",
            )

    def test_chat_request_special_chars_in_id(self):
        """ChatRequest rejeita IDs com espaços e caracteres especiais."""
        with pytest.raises(ValidationError):
            ChatRequest(
                conversation_id="conv id com espaços!",
                message="Teste",
            )


class TestConversationCreateValidation:
    """Testes para validação do ConversationCreate."""

    def test_conversation_create_valid(self):
        """ConversationCreate válido aceita dados corretos."""
        conv = ConversationCreate(
            session_id="test-session-001",
            original_filename="chat.zip",
            upload_path="/tmp/chat.zip",
        )
        assert conv.session_id == "test-session-001"

    def test_conversation_create_path_traversal(self):
        """ConversationCreate rejeita filename com path traversal."""
        with pytest.raises(ValidationError):
            ConversationCreate(
                session_id="test-session-001",
                original_filename="../../etc/passwd",
                upload_path="/tmp/chat.zip",
            )

    def test_conversation_create_invalid_session_id(self):
        """ConversationCreate rejeita session_id com caracteres inválidos."""
        with pytest.raises(ValidationError):
            ConversationCreate(
                session_id="session com espaços!",
                original_filename="chat.zip",
                upload_path="/tmp/chat.zip",
            )


class TestSearchRequestValidation:
    """Testes para validação do SearchMessageRequest."""

    def test_search_request_valid(self):
        """SearchMessageRequest válido aceita dados corretos."""
        req = SearchMessageRequest(
            q="reunião",
            conversation_id="conv-abc123",
            limit=50,
        )
        assert req.q == "reunião"

    def test_search_request_empty_query(self):
        """SearchMessageRequest rejeita query vazia."""
        with pytest.raises(ValidationError):
            SearchMessageRequest(q="")

    def test_search_request_long_query(self):
        """SearchMessageRequest rejeita query muito longa."""
        with pytest.raises(ValidationError):
            SearchMessageRequest(q="x" * 501)

    def test_search_request_invalid_sort(self):
        """SearchMessageRequest rejeita sort_by inválido."""
        with pytest.raises(ValidationError):
            SearchMessageRequest(q="teste", sort_by="invalid")

    def test_search_request_limit_bounds(self):
        """SearchMessageRequest respeita limites de paginação."""
        with pytest.raises(ValidationError):
            SearchMessageRequest(q="teste", limit=0)
        with pytest.raises(ValidationError):
            SearchMessageRequest(q="teste", limit=201)


class TestExportRequestValidation:
    """Testes para validação do ExportRequest."""

    def test_export_request_valid(self):
        """ExportRequest válido aceita formato suportado."""
        req = ExportRequest(format="pdf")
        assert req.format == "pdf"

    def test_export_request_all_formats(self):
        """ExportRequest aceita todos os formatos suportados."""
        for fmt in ["pdf", "docx", "xlsx", "csv", "html", "json"]:
            req = ExportRequest(format=fmt)
            assert req.format == fmt

    def test_export_request_invalid_format(self):
        """ExportRequest rejeita formato não suportado."""
        with pytest.raises(ValidationError):
            ExportRequest(format="txt")

    def test_export_request_defaults(self):
        """ExportRequest tem valores padrão corretos."""
        req = ExportRequest(format="pdf")
        assert req.include_media_descriptions is True
        assert req.include_sentiment_analysis is True
        assert req.include_summary is True
        assert req.include_statistics is True
