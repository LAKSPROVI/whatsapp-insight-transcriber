"""
Exceções customizadas do WhatsApp Insight Transcriber.
Cada exceção carrega status_code HTTP, detail e context dict.
"""
from typing import Any, Dict, Optional


class AppBaseException(Exception):
    """Exceção base da aplicação com status_code, detail e context."""

    status_code: int = 500
    detail: str = "Erro interno do servidor"

    def __init__(
        self,
        detail: Optional[str] = None,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.detail = detail or self.__class__.detail
        self.status_code = status_code or self.__class__.status_code
        self.context = context or {}
        super().__init__(self.detail)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "detail": self.detail,
            "status_code": self.status_code,
            "context": self.context,
        }


class ParserError(AppBaseException):
    """Erro no parsing do arquivo WhatsApp."""
    status_code = 422
    detail = "Erro ao fazer parse do arquivo do WhatsApp"


class ProcessingError(AppBaseException):
    """Erro no processamento da conversa."""
    status_code = 500
    detail = "Erro durante o processamento da conversa"


class APIError(AppBaseException):
    """Erro na comunicação com API externa (Claude)."""
    status_code = 502
    detail = "Erro na comunicação com serviço de IA"


class CacheError(AppBaseException):
    """Erro no cache Redis."""
    status_code = 503
    detail = "Erro no serviço de cache"


class AuthenticationError(AppBaseException):
    """Erro de autenticação."""
    status_code = 401
    detail = "Credenciais inválidas ou expiradas"


class RateLimitError(AppBaseException):
    """Rate limit excedido."""
    status_code = 429
    detail = "Limite de requisições excedido. Tente novamente em alguns instantes."


class ValidationError(AppBaseException):
    """Erro de validação customizado."""
    status_code = 422
    detail = "Erro de validação nos dados enviados"
