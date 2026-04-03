"""
Sistema de deteccao e recomendacao automatica de correcao de erros.

Mantém uma base de conhecimento de erros conhecidos com:
- Codigo de erro unico
- Mensagem de sugestao de correcao
- Link para runbook
- Acao automatica (se aplicavel)
- Severidade
"""
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ErrorSuggestion:
    """Sugestao de correcao para um erro conhecido."""
    code: str
    suggestion: str
    severity: str  # critical, high, medium, low
    runbook: str = ""
    auto_action: Optional[str] = None
    tags: list = field(default_factory=list)


# ── Base de Conhecimento de Erros ─────────────────────────────────
ERROR_KNOWLEDGE_BASE: Dict[str, ErrorSuggestion] = {
    # ── Claude API ────────────────────────────────────────────
    "AI_TIMEOUT_001": ErrorSuggestion(
        code="AI_TIMEOUT_001",
        suggestion="Claude API nao respondeu dentro do timeout. "
                   "Verificar status em status.anthropic.com. "
                   "Considerar aumentar AGENT_TIMEOUT ou reduzir tamanho do payload.",
        severity="high",
        runbook="/runbooks/claude-timeout",
        auto_action="circuit_breaker",
        tags=["ai", "timeout", "claude"],
    ),
    "AI_RATE_LIMIT_002": ErrorSuggestion(
        code="AI_RATE_LIMIT_002",
        suggestion="Rate limit da API Claude atingido. "
                   "Reduzir MAX_AGENTS ou implementar backoff mais agressivo.",
        severity="high",
        runbook="/runbooks/claude-rate-limit",
        auto_action="backoff_increase",
        tags=["ai", "rate_limit", "claude"],
    ),
    "AI_AUTH_003": ErrorSuggestion(
        code="AI_AUTH_003",
        suggestion="Falha de autenticacao na API Claude. "
                   "Verificar ANTHROPIC_API_KEY e ANTHROPIC_BASE_URL.",
        severity="critical",
        runbook="/runbooks/claude-auth",
        tags=["ai", "auth", "claude"],
    ),
    "AI_OVERLOAD_004": ErrorSuggestion(
        code="AI_OVERLOAD_004",
        suggestion="API Claude sobrecarregada (529). "
                   "Aguardar e retry com backoff exponencial.",
        severity="high",
        runbook="/runbooks/claude-overload",
        auto_action="exponential_backoff",
        tags=["ai", "overload", "claude"],
    ),
    "AI_CONTEXT_005": ErrorSuggestion(
        code="AI_CONTEXT_005",
        suggestion="Contexto excede limite de tokens do modelo. "
                   "Reduzir tamanho do input ou usar chunking.",
        severity="medium",
        runbook="/runbooks/claude-context",
        tags=["ai", "tokens", "claude"],
    ),

    # ── Database ──────────────────────────────────────────────
    "DB_CONN_001": ErrorSuggestion(
        code="DB_CONN_001",
        suggestion="Pool de conexoes PostgreSQL esgotado. "
                   "Verificar pool_size e max_overflow em database.py. "
                   "Verificar queries lentas com pg_stat_activity.",
        severity="high",
        runbook="/runbooks/db-connection-pool",
        auto_action="pool_reset",
        tags=["database", "connection", "pool"],
    ),
    "DB_TIMEOUT_002": ErrorSuggestion(
        code="DB_TIMEOUT_002",
        suggestion="Query ao banco de dados excedeu timeout. "
                   "Verificar indices e otimizar query. "
                   "Considerar aumentar pool_timeout.",
        severity="high",
        runbook="/runbooks/db-timeout",
        tags=["database", "timeout", "query"],
    ),
    "DB_INTEGRITY_003": ErrorSuggestion(
        code="DB_INTEGRITY_003",
        suggestion="Violacao de integridade no banco de dados. "
                   "Verificar constraints e dados duplicados.",
        severity="medium",
        runbook="/runbooks/db-integrity",
        tags=["database", "integrity"],
    ),

    # ── Redis/Cache ───────────────────────────────────────────
    "REDIS_CONN_001": ErrorSuggestion(
        code="REDIS_CONN_001",
        suggestion="Falha na conexao com Redis. "
                   "Verificar REDIS_URL e saude do container Redis. "
                   "Aplicacao opera sem cache como fallback.",
        severity="medium",
        runbook="/runbooks/redis-failure",
        auto_action="cache_bypass",
        tags=["redis", "connection", "cache"],
    ),
    "REDIS_TIMEOUT_002": ErrorSuggestion(
        code="REDIS_TIMEOUT_002",
        suggestion="Timeout na operacao Redis. "
                   "Verificar latencia de rede e carga do Redis.",
        severity="medium",
        runbook="/runbooks/redis-timeout",
        auto_action="cache_bypass",
        tags=["redis", "timeout", "cache"],
    ),

    # ── Parser WhatsApp ───────────────────────────────────────
    "PARSE_FORMAT_001": ErrorSuggestion(
        code="PARSE_FORMAT_001",
        suggestion="Formato de exportacao WhatsApp nao reconhecido. "
                   "Verificar se o ZIP contem arquivo _chat.txt. "
                   "Formatos suportados: Android e iOS.",
        severity="medium",
        runbook="/runbooks/parser-format",
        tags=["parser", "format", "whatsapp"],
    ),
    "PARSE_ZIP_002": ErrorSuggestion(
        code="PARSE_ZIP_002",
        suggestion="Arquivo ZIP corrompido ou invalido. "
                   "Solicitar ao usuario re-exportar a conversa.",
        severity="medium",
        runbook="/runbooks/parser-zip",
        tags=["parser", "zip", "upload"],
    ),
    "PARSE_ENCODING_003": ErrorSuggestion(
        code="PARSE_ENCODING_003",
        suggestion="Erro de encoding no arquivo de chat. "
                   "Tentar UTF-8 e Latin-1 como fallback.",
        severity="low",
        runbook="/runbooks/parser-encoding",
        tags=["parser", "encoding"],
    ),

    # ── Autenticacao/Seguranca ────────────────────────────────
    "AUTH_INVALID_001": ErrorSuggestion(
        code="AUTH_INVALID_001",
        suggestion="Token JWT invalido ou expirado. "
                   "Cliente deve re-autenticar via /api/auth/login.",
        severity="low",
        runbook="/runbooks/auth-jwt",
        tags=["auth", "jwt", "security"],
    ),
    "AUTH_FORBIDDEN_002": ErrorSuggestion(
        code="AUTH_FORBIDDEN_002",
        suggestion="Usuario nao possui permissao para esta acao. "
                   "Verificar role do usuario.",
        severity="low",
        runbook="/runbooks/auth-forbidden",
        tags=["auth", "permission", "security"],
    ),
    "AUTH_BRUTEFORCE_003": ErrorSuggestion(
        code="AUTH_BRUTEFORCE_003",
        suggestion="Multiplas tentativas de login falharam do mesmo IP. "
                   "Possivel ataque de forca bruta. Considerar bloqueio temporario.",
        severity="high",
        runbook="/runbooks/auth-bruteforce",
        auto_action="ip_block_temp",
        tags=["auth", "security", "bruteforce"],
    ),

    # ── Media Processing ─────────────────────────────────────
    "MEDIA_CORRUPT_001": ErrorSuggestion(
        code="MEDIA_CORRUPT_001",
        suggestion="Arquivo de midia corrompido ou formato nao suportado. "
                   "Marcar como indisponivel e prosseguir com outras midias.",
        severity="low",
        runbook="/runbooks/media-corruption",
        auto_action="mark_unavailable",
        tags=["media", "corruption"],
    ),
    "MEDIA_TOO_LARGE_002": ErrorSuggestion(
        code="MEDIA_TOO_LARGE_002",
        suggestion="Arquivo de midia excede limite de tamanho para processamento. "
                   "Verificar MAX_UPLOAD_SIZE.",
        severity="low",
        runbook="/runbooks/media-size",
        tags=["media", "size", "upload"],
    ),
    "MEDIA_FFMPEG_003": ErrorSuggestion(
        code="MEDIA_FFMPEG_003",
        suggestion="FFmpeg falhou ao processar midia. "
                   "Verificar instalacao do ffmpeg e codecs disponiveis.",
        severity="medium",
        runbook="/runbooks/media-ffmpeg",
        tags=["media", "ffmpeg", "processing"],
    ),

    # ── Export ────────────────────────────────────────────────
    "EXPORT_GEN_001": ErrorSuggestion(
        code="EXPORT_GEN_001",
        suggestion="Falha na geracao do arquivo de exportacao. "
                   "Verificar memoria disponivel e tamanho da conversa.",
        severity="medium",
        runbook="/runbooks/export-generation",
        tags=["export", "pdf", "docx"],
    ),

    # ── Rate Limiting ────────────────────────────────────────
    "RATE_LIMIT_001": ErrorSuggestion(
        code="RATE_LIMIT_001",
        suggestion="Rate limit excedido. "
                   "Aguardar o periodo indicado no header Retry-After.",
        severity="low",
        runbook="/runbooks/rate-limit",
        tags=["rate_limit", "throttle"],
    ),

    # ── Infrastructure ───────────────────────────────────────
    "INFRA_DISK_001": ErrorSuggestion(
        code="INFRA_DISK_001",
        suggestion="Espaco em disco critico (<500MB). "
                   "Limpar uploads antigos e rotacionar logs.",
        severity="critical",
        runbook="/runbooks/disk-full",
        auto_action="emergency_cleanup",
        tags=["infra", "disk", "storage"],
    ),
    "INFRA_MEMORY_002": ErrorSuggestion(
        code="INFRA_MEMORY_002",
        suggestion="Uso de memoria elevado (>2GB). "
                   "Verificar memory leaks e considerar restart.",
        severity="high",
        runbook="/runbooks/memory-high",
        tags=["infra", "memory"],
    ),
}


class ErrorAdvisor:
    """
    Consulta a base de conhecimento para obter sugestoes de correcao.
    Tambem faz pattern matching para erros nao catalogados.
    """

    def __init__(self, knowledge_base: Dict[str, ErrorSuggestion] = None):
        self.kb = knowledge_base or ERROR_KNOWLEDGE_BASE
        self._exception_map = self._build_exception_map()

    def _build_exception_map(self) -> Dict[str, str]:
        """Mapeia tipos de excecao comuns para codigos de erro."""
        return {
            "TimeoutError": "AI_TIMEOUT_001",
            "asyncio.TimeoutError": "AI_TIMEOUT_001",
            "ConnectionRefusedError": "DB_CONN_001",
            "OperationalError": "DB_CONN_001",
            "IntegrityError": "DB_INTEGRITY_003",
            "RedisConnectionError": "REDIS_CONN_001",
            "ConnectionError": "REDIS_CONN_001",
            "redis.ConnectionError": "REDIS_CONN_001",
            "redis.TimeoutError": "REDIS_TIMEOUT_002",
            "zipfile.BadZipFile": "PARSE_ZIP_002",
            "BadZipFile": "PARSE_ZIP_002",
            "UnicodeDecodeError": "PARSE_ENCODING_003",
            "PermissionError": "AUTH_FORBIDDEN_002",
            "FileNotFoundError": "MEDIA_CORRUPT_001",
            "subprocess.CalledProcessError": "MEDIA_FFMPEG_003",
        }

    def get_by_code(self, error_code: str) -> Optional[ErrorSuggestion]:
        """Busca sugestao por codigo de erro."""
        return self.kb.get(error_code)

    def get_by_exception(self, exc: Exception) -> Optional[ErrorSuggestion]:
        """Busca sugestao pelo tipo de excecao."""
        exc_type = type(exc).__name__
        exc_full = f"{type(exc).__module__}.{exc_type}"

        error_code = self._exception_map.get(exc_full) or self._exception_map.get(exc_type)

        if error_code:
            return self.kb.get(error_code)

        # Pattern matching em mensagem de erro
        return self._match_by_message(str(exc))

    def _match_by_message(self, message: str) -> Optional[ErrorSuggestion]:
        """Tenta identificar erro por keywords na mensagem."""
        message_lower = message.lower()

        patterns = {
            "rate limit": "AI_RATE_LIMIT_002",
            "rate_limit": "AI_RATE_LIMIT_002",
            "429": "AI_RATE_LIMIT_002",
            "timeout": "AI_TIMEOUT_001",
            "timed out": "AI_TIMEOUT_001",
            "connection refused": "DB_CONN_001",
            "connection pool": "DB_CONN_001",
            "authentication": "AI_AUTH_003",
            "unauthorized": "AUTH_INVALID_001",
            "401": "AUTH_INVALID_001",
            "forbidden": "AUTH_FORBIDDEN_002",
            "403": "AUTH_FORBIDDEN_002",
            "disk": "INFRA_DISK_001",
            "no space": "INFRA_DISK_001",
            "memory": "INFRA_MEMORY_002",
            "out of memory": "INFRA_MEMORY_002",
            "overloaded": "AI_OVERLOAD_004",
            "529": "AI_OVERLOAD_004",
            "corrupt": "MEDIA_CORRUPT_001",
            "bad zip": "PARSE_ZIP_002",
            "ffmpeg": "MEDIA_FFMPEG_003",
            "codec": "MEDIA_FFMPEG_003",
        }

        for pattern, code in patterns.items():
            if pattern in message_lower:
                return self.kb.get(code)

        return None

    def get_suggestion_dict(self, error_code: str = None, exc: Exception = None) -> Dict[str, Any]:
        """
        Retorna sugestao como dicionario para inclusao direta em logs.

        Uso:
            advisor = ErrorAdvisor()
            log_extra = advisor.get_suggestion_dict(exc=exc)
            logger.error("operacao falhou", error=log_extra)
        """
        suggestion = None
        if error_code:
            suggestion = self.get_by_code(error_code)
        elif exc:
            suggestion = self.get_by_exception(exc)

        if suggestion:
            return {
                "error_code": suggestion.code,
                "suggestion": suggestion.suggestion,
                "severity": suggestion.severity,
                "runbook": suggestion.runbook,
                "auto_action": suggestion.auto_action,
            }

        # Erro desconhecido
        return {
            "error_code": "UNKNOWN_000",
            "suggestion": "Erro desconhecido. Consultar logs detalhados e escalar para engenharia.",
            "severity": "medium",
            "runbook": "/runbooks/unknown-error",
            "auto_action": None,
        }


# ── Instancia global ─────────────────────────────────────────────
_advisor = ErrorAdvisor()


def get_error_suggestion(error_code: str = None, exc: Exception = None) -> Dict[str, Any]:
    """Funcao de conveniencia para obter sugestao de erro."""
    return _advisor.get_suggestion_dict(error_code=error_code, exc=exc)
