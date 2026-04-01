"""
Configuração de logging estruturado com structlog.
Suporta JSON logging (produção) e console colorido (dev).
"""
import logging
import sys
import time
import uuid
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


def setup_logging():
    """
    Configura structlog + logging stdlib.
    Chamado uma vez no startup da aplicação.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    use_json = settings.LOG_FORMAT.lower() == "json"

    # Processors comuns
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if use_json:
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silenciar loggers muito verbosos
    for noisy in ("uvicorn.access", "httpcore", "httpx", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # uvicorn.error fica no nível configurado
    logging.getLogger("uvicorn.error").setLevel(log_level)


def get_logger(name: str = __name__):
    """Obtém um logger structlog bound."""
    return structlog.get_logger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware que:
    1. Gera request_id único por request
    2. Injeta request_id no contexto de logging
    3. Loga request/response com timing
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        session_id = request.headers.get("X-Session-ID", "")

        # Bind ao contexto structlog (todas as mensagens de log terão esses campos)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            session_id=session_id or None,
        )

        logger = get_logger("http")
        start_time = time.perf_counter()

        # Log request
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else "unknown",
        )

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)

            # Log response
            log_method = logger.info if response.status_code < 400 else logger.warning
            log_method(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Injetar request_id no header de resposta
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise
