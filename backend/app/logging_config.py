"""
Compatibilidade retroativa - redireciona para app.logging.

Este modulo existe para manter imports existentes funcionando.
Todo o codigo novo deve importar de `app.logging` diretamente.

Deprecated: Use `from app.logging import setup_logging, get_logger, RequestTracingMiddleware`
"""
from app.logging.config import setup_logging, get_logger
from app.logging.middleware import RequestTracingMiddleware as RequestLoggingMiddleware

__all__ = ["setup_logging", "get_logger", "RequestLoggingMiddleware"]
