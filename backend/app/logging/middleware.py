"""
Middleware de tracing e logging para FastAPI.

Responsabilidades:
1. Gerar/propagar trace_id, span_id, request_id
2. Bind nos contextvars e structlog
3. Logar request/response com todos os campos da especificacao
4. Medir duracao e injetar headers de tracing na resposta
5. Integrar com error_advisor para erros
"""
import time
import uuid
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging.context import (
    bind_trace_context,
    generate_trace_id,
    generate_span_id,
    generate_request_id,
    get_trace_context,
)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware completo de tracing e logging HTTP.

    Para cada request:
    - Extrai ou gera trace_id, span_id, request_id
    - Bind nos contextvars (propagados para todas as coroutines)
    - Bind no structlog (todos os logs da request terao os IDs)
    - Loga request_started e request_completed/request_failed
    - Injeta headers X-Trace-ID, X-Request-ID, X-Duration-Ms na resposta
    """

    # Paths que nao devem ser logados em detalhe (health checks, metrics)
    SILENT_PATHS = {
        "/api/health",
        "/api/cache/stats",
        "/api/health/detailed",
        "/nginx-health",
        "/",
    }

    async def dispatch(self, request: Request, call_next):
        # ── Extrair ou gerar IDs de tracing ───────────────────
        trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
        span_id = generate_span_id()
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        parent_span_id = request.headers.get("X-Parent-Span-ID")
        session_id = request.headers.get("X-Session-ID", "")

        # ── Bind nos contextvars ──────────────────────────────
        structlog.contextvars.clear_contextvars()
        bind_trace_context(
            trace_id=trace_id,
            span_id=span_id,
            request_id=request_id,
            parent_span_id=parent_span_id,
        )

        # ── Bind adicional no structlog ───────────────────────
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            span_id=span_id,
            request_id=request_id,
        )
        if parent_span_id:
            structlog.contextvars.bind_contextvars(parent_span_id=parent_span_id)
        if session_id:
            structlog.contextvars.bind_contextvars(session_id=session_id)

        logger = structlog.get_logger("http")
        path = request.url.path
        is_silent = path in self.SILENT_PATHS
        start_time = time.perf_counter()

        # ── Extrair info do usuario ───────────────────────────
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "")[:256]

        # ── Log request started ───────────────────────────────
        if not is_silent:
            logger.info(
                "http.request.started",
                http_method=request.method,
                http_url=str(request.url.path),
                http_query=str(request.url.query) if request.url.query else None,
                client_ip=client_ip,
                user_agent=user_agent,
            )

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # ── Injetar headers de tracing na resposta ────────
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Span-ID"] = span_id
            response.headers["X-Duration-Ms"] = f"{duration_ms:.2f}"

            # ── Log request completed ─────────────────────────
            if not is_silent:
                log_level = "info" if response.status_code < 400 else "warning"
                log_method = getattr(logger, log_level)
                log_method(
                    "http.request.completed",
                    http_method=request.method,
                    http_url=str(request.url.path),
                    http_status_code=response.status_code,
                    http_duration_ms=duration_ms,
                    client_ip=client_ip,
                )

            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # ── Obter sugestao do error advisor ───────────────
            from app.logging.error_advisor import get_error_suggestion
            error_info = get_error_suggestion(exc=exc)

            logger.error(
                "http.request.failed",
                http_method=request.method,
                http_url=str(request.url.path),
                http_duration_ms=duration_ms,
                client_ip=client_ip,
                error_type=type(exc).__name__,
                error_message=str(exc)[:512],
                error_code=error_info.get("error_code"),
                error_suggestion=error_info.get("suggestion"),
                error_severity=error_info.get("severity"),
            )
            raise
