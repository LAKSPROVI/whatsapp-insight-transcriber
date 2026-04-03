"""
Contexto de tracing distribuido.

Gerencia trace_id, span_id, request_id e parent_span_id
usando contextvars para propagacao segura em async.
"""
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Optional, Dict, Any


# ── Context Variables ──────────────────────────────────────────────
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
parent_span_id_var: ContextVar[Optional[str]] = ContextVar("parent_span_id", default=None)


def generate_trace_id() -> str:
    """Gera um trace_id no formato UUID v4."""
    return str(uuid.uuid4())


def generate_span_id() -> str:
    """Gera um span_id no formato hex de 16 caracteres."""
    return uuid.uuid4().hex[:16]


def generate_request_id() -> str:
    """Gera um request_id no formato UUID v4."""
    return str(uuid.uuid4())


def get_trace_context() -> Dict[str, Any]:
    """Retorna o contexto de tracing atual como dicionario."""
    return {
        "trace_id": trace_id_var.get(""),
        "span_id": span_id_var.get(""),
        "request_id": request_id_var.get(""),
        "parent_span_id": parent_span_id_var.get(None),
    }


def bind_trace_context(
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    request_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Bind trace context nas contextvars.
    Retorna o contexto efetivo (gerado ou fornecido).
    """
    effective_trace_id = trace_id or generate_trace_id()
    effective_span_id = span_id or generate_span_id()
    effective_request_id = request_id or generate_request_id()

    trace_id_var.set(effective_trace_id)
    span_id_var.set(effective_span_id)
    request_id_var.set(effective_request_id)
    if parent_span_id is not None:
        parent_span_id_var.set(parent_span_id)

    return {
        "trace_id": effective_trace_id,
        "span_id": effective_span_id,
        "request_id": effective_request_id,
        "parent_span_id": parent_span_id,
    }


@contextmanager
def new_span(operation_name: str = ""):
    """
    Context manager que cria um novo span filho, preservando trace_id.

    Uso:
        with new_span("claude.transcribe_audio") as span_ctx:
            logger.info("operacao iniciada", **span_ctx)
            # ... operacao ...
    """
    old_span_id = span_id_var.get("")
    old_parent = parent_span_id_var.get(None)

    child_span_id = generate_span_id()
    span_id_var.set(child_span_id)
    parent_span_id_var.set(old_span_id or None)

    span_context = {
        "trace_id": trace_id_var.get(""),
        "span_id": child_span_id,
        "parent_span_id": old_span_id or None,
        "operation": operation_name,
    }

    try:
        yield span_context
    finally:
        span_id_var.set(old_span_id)
        parent_span_id_var.set(old_parent)
