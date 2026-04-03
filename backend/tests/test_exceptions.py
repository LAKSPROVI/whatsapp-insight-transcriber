"""
Testes para exceções customizadas e configuração da aplicação.
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.exceptions import (
    AppBaseException,
    ParserError,
    ProcessingError,
    APIError,
    CacheError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
)


# ─── Custom Exceptions ──────────────────────────────────────────────────────


class TestAppBaseException:
    def test_default_status_code_and_detail(self):
        """AppBaseException tem status_code=500 e detail padrão."""
        exc = AppBaseException()
        assert exc.status_code == 500
        assert exc.detail == "Erro interno do servidor"

    def test_custom_detail_and_status(self):
        """Aceita detail e status_code customizados."""
        exc = AppBaseException(detail="custom error", status_code=418)
        assert exc.detail == "custom error"
        assert exc.status_code == 418


class TestParserError:
    def test_status_code(self):
        exc = ParserError()
        assert exc.status_code == 422

    def test_default_detail(self):
        exc = ParserError()
        assert "parse" in exc.detail.lower()


class TestProcessingError:
    def test_status_code(self):
        exc = ProcessingError()
        assert exc.status_code == 500


class TestAPIError:
    def test_status_code(self):
        exc = APIError()
        assert exc.status_code == 502


class TestCacheError:
    def test_status_code(self):
        exc = CacheError()
        assert exc.status_code == 503


class TestAuthenticationError:
    def test_status_code(self):
        exc = AuthenticationError()
        assert exc.status_code == 401


class TestRateLimitError:
    def test_status_code(self):
        exc = RateLimitError()
        assert exc.status_code == 429


class TestValidationError:
    def test_status_code(self):
        exc = ValidationError()
        assert exc.status_code == 422


class TestExceptionToDict:
    def test_to_dict_structure(self):
        """to_dict() retorna a estrutura correta."""
        exc = ParserError(detail="bad file", context={"filename": "chat.txt"})
        d = exc.to_dict()

        assert d["error"] == "ParserError"
        assert d["detail"] == "bad file"
        assert d["status_code"] == 422
        assert d["context"] == {"filename": "chat.txt"}

    def test_to_dict_empty_context(self):
        """Context vazio por padrão."""
        exc = AppBaseException()
        d = exc.to_dict()
        assert d["context"] == {}


class TestExceptionContext:
    def test_context_field(self):
        """Campo context é armazenado corretamente."""
        ctx = {"file": "audio.opus", "size": 1024}
        exc = ProcessingError(context=ctx)
        assert exc.context == ctx

    def test_context_default_empty(self):
        exc = ProcessingError()
        assert exc.context == {}


# ─── Config / Settings ───────────────────────────────────────────────────────


class TestSettings:
    def test_loads_from_environment(self, monkeypatch, tmp_path):
        """Settings carrega valores do ambiente."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setenv("CLAUDE_MODEL", "claude-custom")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
        monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "med"))

        from app.config import Settings

        s = Settings()
        assert s.ANTHROPIC_API_KEY == "sk-test-key"
        assert s.CLAUDE_MODEL == "claude-custom"
        assert s.DEBUG is True

    def test_default_values(self, monkeypatch, tmp_path):
        """Valores padrão são aplicados quando variáveis não estão definidas."""
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
        monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "med"))

        from app.config import Settings

        s = Settings()
        assert s.MAX_AGENTS == 20
        assert s.TEMPERATURE == 0.3
        assert s.MAX_TOKENS == 4096
        assert s.APP_NAME == "WhatsApp Insight Transcriber"

    def test_upload_and_media_dir_are_paths(self, monkeypatch, tmp_path):
        """UPLOAD_DIR e MEDIA_DIR são objetos Path."""
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
        monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "med"))

        from app.config import Settings

        s = Settings()
        assert isinstance(s.UPLOAD_DIR, Path)
        assert isinstance(s.MEDIA_DIR, Path)

    def test_allowed_origins_is_list(self, monkeypatch, tmp_path):
        """ALLOWED_ORIGINS é uma lista de strings."""
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
        monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "med"))

        from app.config import Settings

        s = Settings()
        assert isinstance(s.ALLOWED_ORIGINS, list)
        assert all(isinstance(o, str) for o in s.ALLOWED_ORIGINS)


class TestValidateSettings:
    def test_raises_on_missing_api_key(self, monkeypatch, tmp_path):
        """validate_settings levanta ValueError quando ANTHROPIC_API_KEY está vazia."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ADMIN_PASSWORD", "ValidPass1")
        monkeypatch.setenv("SECRET_KEY", "a" * 16)
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
        monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "med"))

        from app.config import Settings, validate_settings

        s = Settings()
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            validate_settings(s)

    def test_raises_on_missing_jwt_secret(self, monkeypatch, tmp_path):
        """validate_settings levanta ValueError quando JWT_SECRET_KEY está vazia."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid")
        monkeypatch.setenv("JWT_SECRET_KEY", "")
        monkeypatch.setenv("ADMIN_PASSWORD", "ValidPass1")
        monkeypatch.setenv("SECRET_KEY", "a" * 16)
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
        monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "med"))

        from app.config import Settings, validate_settings

        s = Settings()
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            validate_settings(s)

    def test_raises_on_short_jwt_secret(self, monkeypatch, tmp_path):
        """validate_settings levanta ValueError quando JWT_SECRET_KEY é curta demais."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid")
        monkeypatch.setenv("JWT_SECRET_KEY", "short")
        monkeypatch.setenv("ADMIN_PASSWORD", "ValidPass1")
        monkeypatch.setenv("SECRET_KEY", "a" * 16)
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
        monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "med"))

        from app.config import Settings, validate_settings

        s = Settings()
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            validate_settings(s)

    def test_raises_on_missing_admin_password(self, monkeypatch, tmp_path):
        """validate_settings levanta ValueError quando ADMIN_PASSWORD está vazia."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid")
        monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ADMIN_PASSWORD", "")
        monkeypatch.setenv("SECRET_KEY", "a" * 16)
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
        monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "med"))

        from app.config import Settings, validate_settings

        s = Settings()
        with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
            validate_settings(s)

    def test_raises_on_short_admin_password(self, monkeypatch, tmp_path):
        """validate_settings levanta ValueError quando ADMIN_PASSWORD é curta demais."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid")
        monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ADMIN_PASSWORD", "short")
        monkeypatch.setenv("SECRET_KEY", "a" * 16)
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
        monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "med"))

        from app.config import Settings, validate_settings

        s = Settings()
        with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
            validate_settings(s)
