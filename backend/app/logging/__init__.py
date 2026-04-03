"""
Modulo de logging estruturado do WhatsApp Insight Transcriber.

Exporta os componentes principais para uso em toda a aplicacao.
"""

from app.logging.config import setup_logging, get_logger
from app.logging.context import (
    trace_id_var,
    span_id_var,
    request_id_var,
    parent_span_id_var,
    get_trace_context,
    bind_trace_context,
    new_span,
)
from app.logging.redaction import redact, redact_processor, RedactionFilter
from app.logging.error_advisor import get_error_suggestion, ErrorAdvisor
from app.logging.middleware import RequestTracingMiddleware

__all__ = [
    "setup_logging",
    "get_logger",
    "trace_id_var",
    "span_id_var",
    "request_id_var",
    "parent_span_id_var",
    "get_trace_context",
    "bind_trace_context",
    "new_span",
    "redact",
    "redact_processor",
    "RedactionFilter",
    "get_error_suggestion",
    "ErrorAdvisor",
    "RequestTracingMiddleware",
]
