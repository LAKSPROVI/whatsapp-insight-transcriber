"""
Testes para o WhatsAppParser — parsing de mensagens, detecção de mídia,
mensagens de sistema, formatação rica, citações, reações, etc.
"""
import pytest
import pytest_asyncio
import os
import zipfile
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from app.exceptions import ParserError
from app.services.whatsapp_parser import WhatsAppParser, ParsedMessage, DELETED_PATTERNS


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def parser():
    return WhatsAppParser()


@pytest.fixture
def android_chat_content():
    """Chat exportado no formato Android PT-BR (dd/mm/yyyy)."""
    return (
        "26/03/2025, 23:10:15 - João: Oi, tudo bem?\n"
        "26/03/2025, 23:11:00 - Maria: Tudo ótimo!\n"
        "27/03/2025, 08:00:00 - João: Bom dia\n"
    )


@pytest.fixture
def ios_chat_content():
    """Chat exportado no formato iOS."""
    return (
        "[26/03/2025, 23:10:15] João: Olá pessoal\n"
        "[26/03/2025, 23:12:00] Maria: Oi João!\n"
    )


@pytest.fixture
def tmp_chat_file(android_chat_content):
    """Cria arquivo temporário com conteúdo de chat."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(android_chat_content)
    f.close()
    yield f.name
    os.unlink(f.name)


# ─── Testes de parsing de formato Android ────────────────────────────────────

class TestAndroidFormat:
    @pytest.mark.asyncio
    async def test_parse_android_messages(self, parser, tmp_chat_file):
        messages = await parser.parse_file(tmp_chat_file)
        assert len(messages) == 3
        assert messages[0].sender == "João"
        assert messages[0].text == "Oi, tudo bem?"
        assert messages[1].sender == "Maria"

    @pytest.mark.asyncio
    async def test_parse_android_timestamps(self, parser, tmp_chat_file):
        messages = await parser.parse_file(tmp_chat_file)
        assert messages[0].timestamp == datetime(2025, 3, 26, 23, 10, 15)
        assert messages[2].timestamp == datetime(2025, 3, 27, 8, 0, 0)

    @pytest.mark.asyncio
    async def test_participant_extraction(self, parser, tmp_chat_file):
        await parser.parse_file(tmp_chat_file)
        participants = parser.get_participants()
        assert participants == ["João", "Maria"]


# ─── Testes de formato iOS ───────────────────────────────────────────────────

class TestIOSFormat:
    @pytest.mark.asyncio
    async def test_parse_ios_messages(self, parser, ios_chat_content):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(ios_chat_content)
        f.close()
        try:
            messages = await parser.parse_file(f.name)
            assert len(messages) == 2
            assert messages[0].sender == "João"
            assert messages[0].text == "Olá pessoal"
        finally:
            os.unlink(f.name)


# ─── Testes de formato de data ───────────────────────────────────────────────

class TestDateFormats:
    @pytest.mark.asyncio
    async def test_portuguese_date_format_dmy(self, parser):
        content = "26/03/2025, 14:30:00 - Ana: Boa tarde\n"
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        try:
            messages = await parser.parse_file(f.name)
            assert len(messages) == 1
            # dia=26, mês=3
            assert messages[0].timestamp.day == 26
            assert messages[0].timestamp.month == 3
        finally:
            os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_english_date_format_mdy(self, parser):
        # Segundo campo > 12 triggers mdy detection
        content = "03/26/2025, 14:30:00 - Bob: Good afternoon\n"
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        try:
            messages = await parser.parse_file(f.name)
            assert len(messages) == 1
            assert messages[0].timestamp.month == 3
            assert messages[0].timestamp.day == 26
        finally:
            os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_ambiguous_date_defaults_to_dmy(self, parser):
        # Both fields <= 12, should default to dd/mm
        content = "05/03/2025, 10:00:00 - João: Teste\n"
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        try:
            messages = await parser.parse_file(f.name)
            assert len(messages) == 1
            assert messages[0].timestamp.day == 5
            assert messages[0].timestamp.month == 3
        finally:
            os.unlink(f.name)


# ─── Testes de detecção de mídia ─────────────────────────────────────────────

class TestMediaDetection:
    def test_detect_image_omitted(self, parser):
        media_type, filename = parser._detect_media("<image omitted>")
        assert media_type == "image"

    def test_detect_audio_omitted(self, parser):
        media_type, filename = parser._detect_media("<audio omitted>")
        assert media_type == "audio"

    def test_detect_video_omitted(self, parser):
        media_type, filename = parser._detect_media("<video omitted>")
        assert media_type == "video"

    def test_detect_document_omitted(self, parser):
        media_type, filename = parser._detect_media("<document omitted>")
        assert media_type == "document"

    def test_detect_sticker_omitted(self, parser):
        media_type, filename = parser._detect_media("<sticker omitted>")
        assert media_type == "sticker"

    def test_detect_contact_omitted(self, parser):
        media_type, filename = parser._detect_media("<contact omitted>")
        assert media_type == "contact"

    def test_detect_location_google_maps(self, parser):
        media_type, _ = parser._detect_media("https://maps.google.com/xyz")
        assert media_type == "location"

    def test_detect_filename_image(self, parser):
        media_type, filename = parser._detect_media("IMG-20250326-WA0001.jpg")
        assert media_type == "image"
        assert filename == "IMG-20250326-WA0001.jpg"

    def test_detect_filename_audio(self, parser):
        media_type, filename = parser._detect_media("PTT-20250326-WA0001.opus")
        assert media_type == "audio"

    def test_detect_vcf_contact(self, parser):
        media_type, filename = parser._detect_media("contact.vcf")
        assert media_type == "contact"
        assert filename == "contact.vcf"

    def test_plain_text_not_media(self, parser):
        media_type, filename = parser._detect_media("Hello world")
        assert media_type == "text"
        assert filename is None


# ─── Testes de mensagens de sistema ──────────────────────────────────────────

class TestSystemMessages:
    def test_detect_encryption_message(self, parser):
        assert parser._is_system_message("Messages and calls are end-to-end encrypted")

    def test_detect_group_creation(self, parser):
        assert parser._is_system_message("João criou este grupo")

    def test_detect_member_added(self, parser):
        assert parser._is_system_message("João added Maria")

    def test_regular_message_not_system(self, parser):
        assert not parser._is_system_message("Bom dia pessoal!")

    @pytest.mark.asyncio
    async def test_system_messages_filtered_from_parse(self, parser):
        content = (
            "26/03/2025, 10:00:00 - Messages and calls are end-to-end encrypted\n"
            "26/03/2025, 10:01:00 - João: Oi\n"
        )
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        try:
            messages = await parser.parse_file(f.name)
            assert len(messages) == 1
            assert messages[0].sender == "João"
        finally:
            os.unlink(f.name)

    def test_deleted_message_detection(self, parser):
        assert any("this message was deleted" in p for p in DELETED_PATTERNS)
        assert any("esta mensagem foi apagada" in p for p in DELETED_PATTERNS)

    def test_forwarded_detection(self, parser):
        assert parser._detect_forwarded("⁣Forwarded")
        assert parser._detect_forwarded("Encaminhada")
        assert not parser._detect_forwarded("Normal message")

    def test_edited_detection(self, parser):
        assert parser._detect_edited("<This message was edited>")
        assert parser._detect_edited("<Esta mensagem foi editada>")
        assert not parser._detect_edited("Normal text")


# ─── Testes de multi-linha ───────────────────────────────────────────────────

class TestMultiLineMessages:
    @pytest.mark.asyncio
    async def test_multiline_message_preserved(self, parser):
        content = (
            "26/03/2025, 10:00:00 - João: Primeira linha\n"
            "Segunda linha\n"
            "Terceira linha\n"
            "26/03/2025, 10:01:00 - Maria: Resposta\n"
        )
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        try:
            messages = await parser.parse_file(f.name)
            assert len(messages) == 2
            assert "Primeira linha" in messages[0].text
            assert "Segunda linha" in messages[0].text
            assert "Terceira linha" in messages[0].text
            assert messages[1].text == "Resposta"
        finally:
            os.unlink(f.name)


# ─── Testes de edge cases ────────────────────────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_file_raises_error(self, parser):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write("")
        f.close()
        try:
            with pytest.raises(ParserError):
                await parser.parse_file(f.name)
        finally:
            os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_whitespace_only_file_raises_error(self, parser):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write("   \n\n   \n")
        f.close()
        try:
            with pytest.raises(ParserError):
                await parser.parse_file(f.name)
        finally:
            os.unlink(f.name)

    def test_malformed_timestamp_returns_none(self, parser):
        parser._date_format = "dmy"
        result = parser._parse_datetime("99/99/9999", "25:61")
        assert result is None

    def test_system_sender_detection(self, parser):
        assert parser._is_system_sender("system")
        assert parser._is_system_sender("WhatsApp")
        assert not parser._is_system_sender("João")
        # Very long sender name = system
        assert parser._is_system_sender("a" * 101)


# ─── Testes de citação e reação ──────────────────────────────────────────────

class TestQuotedAndReactions:
    def test_detect_quoted_with_angle_bracket(self, parser):
        is_quoted, quoted_text = parser._detect_quoted("> Mensagem original\nResposta")
        assert is_quoted is True
        assert quoted_text == "> Mensagem original"

    def test_no_quote_in_normal_text(self, parser):
        is_quoted, quoted_text = parser._detect_quoted("Mensagem normal sem citação")
        assert is_quoted is False
        assert quoted_text is None

    def test_detect_emoji_reaction(self, parser):
        reaction = parser._detect_reaction("👍")
        assert reaction == "👍"

    def test_detect_multi_emoji_reaction(self, parser):
        reaction = parser._detect_reaction("😂🤣")
        assert reaction == "😂🤣"

    def test_no_reaction_for_text(self, parser):
        reaction = parser._detect_reaction("This is a normal message")
        assert reaction is None


# ─── Testes de formatação rica ───────────────────────────────────────────────

class TestRichFormatting:
    def test_detect_bold(self, parser):
        result = parser._detect_rich_formatting("Isso é *negrito* aqui")
        assert "bold" in result
        assert result["bold"] == ["negrito"]

    def test_detect_italic(self, parser):
        result = parser._detect_rich_formatting("Isso é _itálico_ aqui")
        assert "italic" in result
        assert result["italic"] == ["itálico"]

    def test_detect_strikethrough(self, parser):
        result = parser._detect_rich_formatting("Isso é ~tachado~ aqui")
        assert "strikethrough" in result
        assert result["strikethrough"] == ["tachado"]

    def test_detect_monospace(self, parser):
        result = parser._detect_rich_formatting("Código ```bloco``` aqui")
        assert "monospace" in result
        assert result["monospace"] == ["bloco"]

    def test_no_formatting_in_plain_text(self, parser):
        result = parser._detect_rich_formatting("Texto normal sem formatação")
        assert result == {}

    def test_multiple_formats_in_same_message(self, parser):
        result = parser._detect_rich_formatting("*negrito* e _itálico_ e ~tachado~")
        assert "bold" in result
        assert "italic" in result
        assert "strikethrough" in result


# ─── Testes de get_stats / get_date_range ────────────────────────────────────

class TestStats:
    @pytest.mark.asyncio
    async def test_get_date_range(self, parser, tmp_chat_file):
        await parser.parse_file(tmp_chat_file)
        start, end = parser.get_date_range()
        assert start is not None
        assert end is not None
        assert start <= end

    @pytest.mark.asyncio
    async def test_get_stats(self, parser, tmp_chat_file):
        await parser.parse_file(tmp_chat_file)
        stats = parser.get_stats()
        assert stats["total_messages"] == 3
        assert "João" in stats["participants"]
        assert "Maria" in stats["participants"]

    def test_empty_stats(self, parser):
        stats = parser.get_stats()
        assert stats == {}

    def test_empty_date_range(self, parser):
        start, end = parser.get_date_range()
        assert start is None
        assert end is None
