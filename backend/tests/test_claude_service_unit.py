"""
Testes unitários para ClaudeService — mocks de API, retry, rate limit,
timeout, cache, transcrição de áudio e descrição de imagem.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from types import SimpleNamespace

from app.services.claude_service import (
    ClaudeService,
    MAX_RETRIES,
    BACKOFF_BASE,
    BACKOFF_MULTIPLIER,
    OPERATION_TIMEOUTS,
)
from app.exceptions import APIError, RateLimitError


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_claude_response(text="response text", input_tokens=10, output_tokens=20):
    """Cria um mock de resposta da API Claude."""
    content_block = SimpleNamespace(text=text)
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(content=[content_block], usage=usage)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def claude_service():
    """ClaudeService com client mockado."""
    with patch("app.services.claude_service.anthropic.AsyncAnthropic") as MockClient:
        service = ClaudeService()
        service.client = MagicMock()
        service.client.messages = MagicMock()
        service.client.messages.create = AsyncMock(
            return_value=_make_claude_response()
        )
        yield service


# ─── Testes de _call_claude_with_retry ───────────────────────────────────────

class TestCallClaudeWithRetry:
    @pytest.mark.asyncio
    async def test_successful_call(self, claude_service):
        result = await claude_service._call_claude_with_retry(
            operation="default",
            model="claude-test",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert result.content[0].text == "response text"
        assert claude_service._total_calls == 1
        assert claude_service._total_errors == 0

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, claude_service):
        import anthropic

        rate_limit_err = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        claude_service.client.messages.create = AsyncMock(
            side_effect=[rate_limit_err, rate_limit_err, _make_claude_response("ok")]
        )

        with patch("app.services.claude_service.asyncio.sleep", new_callable=AsyncMock):
            result = await claude_service._call_claude_with_retry(
                operation="default",
                model="claude-test",
                max_tokens=100,
                messages=[{"role": "user", "content": "Hello"}],
            )
        assert result.content[0].text == "ok"
        assert claude_service._rate_limit_hits == 2
        assert claude_service._total_retries == 2

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, claude_service):
        import anthropic

        conn_err = anthropic.APIConnectionError(request=MagicMock())
        claude_service.client.messages.create = AsyncMock(
            side_effect=[conn_err, _make_claude_response("recovered")]
        )

        with patch("app.services.claude_service.asyncio.sleep", new_callable=AsyncMock):
            result = await claude_service._call_claude_with_retry(
                operation="default",
                model="claude-test",
                max_tokens=100,
                messages=[{"role": "user", "content": "test"}],
            )
        assert result.content[0].text == "recovered"
        assert claude_service._total_retries == 1

    @pytest.mark.asyncio
    async def test_timeout_handling(self, claude_service):
        claude_service.client.messages.create = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        with patch("app.services.claude_service.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(APIError, match="Falha após"):
                await claude_service._call_claude_with_retry(
                    operation="default",
                    model="claude-test",
                    max_tokens=100,
                    messages=[{"role": "user", "content": "test"}],
                )
        assert claude_service._total_calls == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_rate_limit(self, claude_service):
        import anthropic

        rate_limit_err = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        claude_service.client.messages.create = AsyncMock(
            side_effect=rate_limit_err
        )

        with patch("app.services.claude_service.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RateLimitError):
                await claude_service._call_claude_with_retry(
                    operation="default",
                    model="claude-test",
                    max_tokens=100,
                    messages=[{"role": "user", "content": "test"}],
                )

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(self, claude_service):
        import anthropic

        status_err = anthropic.APIStatusError(
            message="does not support image input",
            response=MagicMock(status_code=400, headers={}),
            body=None,
        )
        claude_service.client.messages.create = AsyncMock(side_effect=status_err)

        with pytest.raises(anthropic.APIStatusError):
            await claude_service._call_claude_with_retry(
                operation="describe_image",
                model="claude-test",
                max_tokens=100,
                messages=[{"role": "user", "content": "test"}],
            )
        # Should NOT have retried — only 1 call
        assert claude_service._total_calls == 1


# ─── Testes de operações específicas ─────────────────────────────────────────

class TestOperationTimeouts:
    def test_transcribe_audio_timeout(self):
        assert OPERATION_TIMEOUTS["transcribe_audio"] == 90.0

    def test_describe_image_timeout(self):
        assert OPERATION_TIMEOUTS["describe_image"] == 60.0

    def test_default_timeout(self):
        assert OPERATION_TIMEOUTS["default"] == 60.0


class TestTranscribeAudio:
    @pytest.mark.asyncio
    async def test_transcribe_audio_whisper_success(self, claude_service, tmp_path):
        audio_file = tmp_path / "test.opus"
        audio_file.write_bytes(b"\x00" * 100)

        claude_service._whisper_transcribe = AsyncMock(return_value="raw transcription")
        claude_service.client.messages.create = AsyncMock(
            return_value=_make_claude_response("Corrected transcription")
        )

        result = await claude_service.transcribe_audio(str(audio_file))
        assert result["transcription"] == "Corrected transcription"
        assert result["tokens_used"] == 30  # 10 + 20

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_not_found(self, claude_service):
        with pytest.raises(FileNotFoundError):
            await claude_service.transcribe_audio("/nonexistent/file.opus")

    @pytest.mark.asyncio
    async def test_transcribe_audio_whisper_fallback(self, claude_service, tmp_path):
        audio_file = tmp_path / "test.opus"
        audio_file.write_bytes(b"\x00" * 100)

        claude_service._whisper_transcribe = AsyncMock(side_effect=Exception("whisper failed"))
        claude_service.client.messages.create = AsyncMock(
            return_value=_make_claude_response("[Áudio recebido - transcrição via Whisper indisponível]")
        )

        result = await claude_service.transcribe_audio(str(audio_file))
        assert "Áudio recebido" in result["transcription"]


class TestDescribeImage:
    @pytest.mark.asyncio
    async def test_describe_image_vision_success(self, claude_service, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        json_response = '{"description": "A photo", "ocr_text": null, "image_type": "foto", "sentiment": "neutro", "contains_sensitive_content": false}'
        claude_service.client.messages.create = AsyncMock(
            return_value=_make_claude_response(json_response)
        )

        result = await claude_service.describe_image(str(img_file))
        assert result["description"] == "A photo"
        assert result["tokens_used"] == 30

    @pytest.mark.asyncio
    async def test_describe_image_not_found(self, claude_service):
        with pytest.raises(FileNotFoundError):
            await claude_service.describe_image("/nonexistent/image.jpg")

    @pytest.mark.asyncio
    async def test_describe_image_fallback_on_unsupported(self, claude_service, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG" + b"\x00" * 100)

        claude_service._describe_image_vision = AsyncMock(
            side_effect=Exception("does not support image input")
        )

        result = await claude_service.describe_image(str(img_file))
        assert "análise visual indisponível" in result["description"]
        assert result["tokens_used"] == 0

    @pytest.mark.asyncio
    async def test_describe_image_fallback_on_200_error_content(self, claude_service, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        # Vision returns 200 but text says model doesn't support images
        claude_service._describe_image_vision = AsyncMock(
            return_value={"description": "This model does not support image input", "tokens_used": 5}
        )

        result = await claude_service.describe_image(str(img_file))
        assert "análise visual indisponível" in result["description"]


# ─── Testes de cache ─────────────────────────────────────────────────────────

class TestCacheIntegration:
    @pytest.mark.asyncio
    async def test_analyze_sentiment_cache_hit(self, claude_service):
        cached_result = {
            "sentiment": "positive",
            "score": 0.8,
            "emotions": ["alegria"],
            "confidence": 0.9,
            "tokens_used": 0,
            "cached": True,
        }

        with patch("app.services.claude_service.get_cached_result", new_callable=AsyncMock, return_value=cached_result):
            result = await claude_service.analyze_sentiment("Estou muito feliz!")
        assert result["cached"] is True
        # API should NOT have been called
        claude_service.client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_sentiment_cache_miss(self, claude_service):
        json_resp = '{"sentiment": "positive", "score": 0.7, "emotions": ["alegria"], "confidence": 0.85}'
        claude_service.client.messages.create = AsyncMock(
            return_value=_make_claude_response(json_resp)
        )

        with patch("app.services.claude_service.get_cached_result", new_callable=AsyncMock, return_value=None), \
             patch("app.services.claude_service.set_cached_result", new_callable=AsyncMock) as mock_set:
            result = await claude_service.analyze_sentiment("Estou feliz!")
        assert result["sentiment"] == "positive"
        mock_set.assert_called_once()


# ─── Testes de streaming (chat_with_context) ────────────────────────────────

class TestChatWithContext:
    @pytest.mark.asyncio
    async def test_chat_streaming(self, claude_service):
        async def fake_text_stream():
            for chunk in ["Olá", ", ", "tudo bem?"]:
                yield chunk

        mock_stream_ctx = MagicMock()
        mock_stream_obj = MagicMock()
        mock_stream_obj.text_stream = fake_text_stream()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_obj)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        claude_service.client.messages.stream = MagicMock(return_value=mock_stream_ctx)

        chunks = []
        async for chunk in claude_service.chat_with_context(
            user_message="Oi",
            conversation_context="Contexto de teste",
        ):
            chunks.append(chunk)
        assert "".join(chunks) == "Olá, tudo bem?"


# ─── Testes de get_stats ─────────────────────────────────────────────────────

class TestGetStats:
    def test_initial_stats(self, claude_service):
        stats = claude_service.get_stats()
        assert stats["total_calls"] == 0
        assert stats["total_errors"] == 0
        assert stats["total_retries"] == 0
        assert stats["rate_limit_hits"] == 0
