"""
Testes do parser de exportações do WhatsApp.
"""
import os
import tempfile
import pytest
from datetime import datetime

from app.services.whatsapp_parser import (
    WhatsAppParser,
    ParsedMessage,
    PATTERNS,
    FORWARDED_PATTERNS,
    EDITED_PATTERNS,
)


class TestParseBasicMessage:
    """Testes para parse de mensagens básicas."""

    def test_parse_basic_message(self):
        """Mensagem simples no formato Android PT-BR."""
        parser = WhatsAppParser()
        content = "26/03/2025, 23:10 - João: Olá, tudo bem?"
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            assert len(messages) >= 1
            msg = messages[0]
            assert msg.sender == "João"
            assert "Olá, tudo bem?" in msg.text
            assert isinstance(msg.timestamp, datetime)
        finally:
            os.unlink(temp_path)

    def test_parse_multiple_messages(self):
        """Múltiplas mensagens em sequência."""
        parser = WhatsAppParser()
        content = (
            "26/03/2025, 08:00 - João: Bom dia!\n"
            "26/03/2025, 08:01 - Maria: Bom dia João!\n"
            "26/03/2025, 08:05 - Pedro: Olá pessoal\n"
        )
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            assert len(messages) >= 3
            senders = {m.sender for m in messages}
            assert "João" in senders
            assert "Maria" in senders
            assert "Pedro" in senders
        finally:
            os.unlink(temp_path)


class TestParseSystemMessage:
    """Testes para mensagens de sistema."""

    def test_parse_system_message(self):
        """Mensagens de sistema são ignoradas (retornam None no _parse_line)."""
        parser = WhatsAppParser()
        content = (
            "26/03/2025, 08:00 - As mensagens e as chamadas são protegidas com criptografia de ponta a ponta.\n"
            "26/03/2025, 08:01 - João: Olá!\n"
        )
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            # Mensagem de sistema deve ser filtrada
            user_messages = [m for m in messages if not m.is_system]
            assert len(user_messages) >= 1
            assert user_messages[0].sender == "João"
        finally:
            os.unlink(temp_path)


class TestParseMediaMessage:
    """Testes para mensagens com mídia."""

    def test_parse_media_message(self):
        """Mensagem com mídia omitida."""
        parser = WhatsAppParser()
        content = "26/03/2025, 10:00 - João: <Mídia omitida>"
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            assert len(messages) >= 1
        finally:
            os.unlink(temp_path)

    def test_parse_media_attached(self):
        """Mensagem com arquivo anexado."""
        parser = WhatsAppParser()
        content = "26/03/2025, 10:00 - Maria: IMG-20250326-WA0001.jpg (arquivo anexado)"
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            assert len(messages) >= 1
        finally:
            os.unlink(temp_path)


class TestParseForwardedMessage:
    """Testes para mensagens encaminhadas."""

    def test_forwarded_pattern_detection(self):
        """Detecção do padrão de encaminhamento."""
        for pattern in FORWARDED_PATTERNS:
            assert pattern.match("Forwarded") or pattern.match("Encaminhada")


class TestParseEditedMessage:
    """Testes para mensagens editadas."""

    def test_edited_pattern_detection(self):
        """Detecção do padrão de edição."""
        assert any(p.search("<This message was edited>") for p in EDITED_PATTERNS)
        assert any(p.search("<Esta mensagem foi editada>") for p in EDITED_PATTERNS)


class TestParseMultilineMessage:
    """Testes para mensagens multi-linha."""

    def test_parse_multiline_message(self):
        """Mensagem que ocupa múltiplas linhas."""
        parser = WhatsAppParser()
        content = (
            "26/03/2025, 08:00 - João: Primeira linha\n"
            "Segunda linha\n"
            "Terceira linha\n"
            "26/03/2025, 08:01 - Maria: Resposta\n"
        )
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            assert len(messages) >= 2
            # A primeira mensagem deve conter as linhas extras
            joao_msg = [m for m in messages if m.sender == "João"]
            assert len(joao_msg) >= 1
            assert "Primeira linha" in joao_msg[0].text
        finally:
            os.unlink(temp_path)


class TestParseDateFormats:
    """Testes para diferentes formatos de data."""

    def test_parse_android_format(self):
        """Formato Android: dd/mm/yyyy, HH:MM"""
        parser = WhatsAppParser()
        content = "26/03/2025, 23:10 - João: Mensagem"
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            assert len(messages) >= 1
        finally:
            os.unlink(temp_path)

    def test_parse_ios_format(self):
        """Formato iOS: [dd/mm/yyyy, HH:MM:SS]"""
        parser = WhatsAppParser()
        content = "[26/03/2025, 23:10:15] João: Mensagem iOS"
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            assert len(messages) >= 1
        finally:
            os.unlink(temp_path)

    def test_parse_iso_format(self):
        """Formato ISO: yyyy-mm-dd, HH:MM"""
        parser = WhatsAppParser()
        content = "2025-03-26, 23:10 - João: Mensagem ISO"
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            assert len(messages) >= 1
        finally:
            os.unlink(temp_path)


class TestParseEdgeCases:
    """Testes para casos extremos."""

    def test_parse_empty_input(self):
        """Input vazio deve levantar ParserError."""
        from app.exceptions import ParserError
        
        parser = WhatsAppParser()
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("")
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ParserError):
                parser.parse_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_parse_invalid_format(self):
        """Texto sem formato de chat retorna lista vazia ou sem mensagens válidas."""
        parser = WhatsAppParser()
        content = "Este texto não é uma exportação do WhatsApp.\nApenas texto normal."
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            # Texto sem formato válido deve retornar 0 mensagens parseadas
            assert len(messages) == 0
        finally:
            os.unlink(temp_path)

    def test_parser_participants_tracking(self):
        """Parser rastreia participantes corretamente."""
        parser = WhatsAppParser()
        content = (
            "26/03/2025, 08:00 - João: Olá\n"
            "26/03/2025, 08:01 - Maria: Oi\n"
            "26/03/2025, 08:02 - João: Tudo bem?\n"
        )
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            messages = parser.parse_file(temp_path)
            assert "João" in parser.participants
            assert "Maria" in parser.participants
        finally:
            os.unlink(temp_path)
