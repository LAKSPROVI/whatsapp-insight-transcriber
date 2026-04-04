"""Custom Prometheus metrics for WIT"""
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram, Gauge

# AI Metrics
ai_tokens_total = Counter(
    "wit_ai_tokens_total",
    "Total AI tokens used",
    ["model", "operation"]
)

ai_call_duration = Histogram(
    "wit_ai_call_duration_seconds",
    "AI API call duration",
    ["model", "operation"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300]
)

ai_rate_limits = Counter(
    "wit_ai_rate_limit_total",
    "AI API rate limit hits",
    ["model"]
)

ai_errors = Counter(
    "wit_ai_errors_total",
    "AI API errors",
    ["model", "error_type"]
)

# Processing Metrics
processing_queue_depth = Gauge(
    "wit_processing_queue_depth",
    "Number of jobs in processing queue"
)

active_agents = Gauge(
    "wit_active_agents",
    "Number of active AI processing agents"
)

conversations_processed = Counter(
    "wit_conversations_processed_total",
    "Total conversations processed",
    ["status"]
)

# WebSocket Metrics
ws_active_connections = Gauge(
    "wit_ws_active_connections",
    "Active WebSocket connections"
)

# Cache Metrics
cache_operations = Counter(
    "wit_cache_operations_total",
    "Cache operations",
    ["operation", "result"]  # get/set, hit/miss
)


def setup_instrumentator() -> Instrumentator:
    """Configure Prometheus FastAPI instrumentator."""
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        excluded_handlers=["/api/health", "/metrics", "/api/health/detailed"],
        env_var_name="ENABLE_METRICS",
    )
    return instrumentator


def set_processing_queue_depth(value: int) -> None:
    processing_queue_depth.set(max(0, value))


def set_active_agents(value: int) -> None:
    active_agents.set(max(0, value))


def increment_conversations_processed(status: str) -> None:
    conversations_processed.labels(status=status).inc()


def set_ws_active_connections(value: int) -> None:
    ws_active_connections.set(max(0, value))


def track_cache_operation(operation: str, result: str) -> None:
    cache_operations.labels(operation=operation, result=result).inc()
