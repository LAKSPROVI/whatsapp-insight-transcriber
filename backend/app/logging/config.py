"""
Configuracao avancada de logging estruturado com structlog.

Funcionalidades:
- JSON estruturado (producao) ou console colorido (dev)
- Integracao com contextvars para trace_id/span_id
- Processor de redacao automatica de dados sensiveis
- Campos obrigatorios conforme especificacao (service, event, environment, version)
- Suporte a niveis DEBUG, INFO, WARN, ERROR
"""
import logging
import os
import sys
from typing import Any, Dict

import structlog


def _get_settings():
    """Importa settings de forma lazy para evitar circular imports."""
    from app.config import settings
    return settings


def _add_service_context(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processor que adiciona campos obrigatorios do servico.
    Injeta: service, environment, version.
    """
    settings = _get_settings()
    event_dict.setdefault("service", "wit-backend")
    event_dict.setdefault("environment", "production" if not settings.DEBUG else "development")
    event_dict.setdefault("version", settings.APP_VERSION)
    return event_dict


def _add_trace_context(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processor que injeta trace_id, span_id, request_id, parent_span_id
    das contextvars no evento de log.
    """
    from app.logging.context import (
        trace_id_var, span_id_var, request_id_var, parent_span_id_var
    )

    trace_id = trace_id_var.get("")
    span_id = span_id_var.get("")
    request_id = request_id_var.get("")
    parent_span_id = parent_span_id_var.get(None)

    if trace_id:
        event_dict.setdefault("trace_id", trace_id)
    if span_id:
        event_dict.setdefault("span_id", span_id)
    if request_id:
        event_dict.setdefault("request_id", request_id)
    if parent_span_id:
        event_dict.setdefault("parent_span_id", parent_span_id)

    return event_dict


def _sanitize_event(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processor que sanitiza o campo 'event' para prevenir log injection.
    Trunca mensagens longas e remove caracteres de controle.
    """
    event = event_dict.get("event", "")
    if isinstance(event, str):
        # Remover caracteres de controle (exceto newline para stack traces)
        event = event.replace("\r", "").replace("\x00", "")
        # Truncar a 1024 caracteres
        if len(event) > 1024:
            event = event[:1021] + "..."
        event_dict["event"] = event

    # Truncar mensagem se presente
    message = event_dict.get("message", "")
    if isinstance(message, str) and len(message) > 1024:
        event_dict["message"] = message[:1021] + "..."

    return event_dict


def _rename_event_to_message(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Em JSON mode, renomeia 'event' para 'message' para compatibilidade
    com o schema de log definido na especificacao.
    """
    settings = _get_settings()
    if settings.LOG_FORMAT.lower() == "json":
        if "event" in event_dict and "message" not in event_dict:
            event_dict["message"] = event_dict["event"]
    return event_dict


def setup_logging():
    """
    Configura structlog + logging stdlib com todos os processors.
    Chamado uma vez no startup da aplicacao.
    """
    settings = _get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    use_json = settings.LOG_FORMAT.lower() == "json"

    # Determinar se redacao esta ativa
    redaction_enabled = getattr(settings, "LOG_REDACTION_ENABLED", True)

    # Chain de processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service_context,
        _add_trace_context,
        _sanitize_event,
    ]

    # Adicionar redacao se habilitada
    if redaction_enabled:
        from app.logging.redaction import redact_processor
        shared_processors.append(redact_processor)

    shared_processors.append(_rename_event_to_message)

    if use_json:
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
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

    # Silenciar loggers ruidosos
    for noisy in ("uvicorn.access", "httpcore", "httpx", "hpack", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # uvicorn.error no nivel configurado
    logging.getLogger("uvicorn.error").setLevel(log_level)


def get_logger(name: str = __name__):
    """Obtem um logger structlog bound com contexto do servico."""
    return structlog.get_logger(name)
