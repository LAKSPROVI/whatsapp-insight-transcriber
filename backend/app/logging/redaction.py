"""
Modulo de redacao/mascaramento de dados sensiveis em logs.

Duas camadas de protecao:
1. Funcao `redact()` para sanitizar strings antes de logar
2. Processor `redact_processor` para structlog que sanitiza campos automaticamente
"""
import re
import hashlib
from typing import Any, Dict, List, Set


# ── Campos que NUNCA devem ser logados ────────────────────────────
BLACKLISTED_FIELDS: Set[str] = {
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "cookie", "session", "credit_card", "card_number",
    "cvv", "ssn", "private_key", "secret_key", "access_token",
    "refresh_token", "hashed_password", "new_password", "current_password",
    "admin_password", "jwt_secret_key", "anthropic_api_key",
}

# ── Campos que devem ser mascarados (parcialmente visiveis) ──────
MASKED_FIELDS: Set[str] = {
    "email", "phone", "telephone", "celular", "cpf", "cnpj", "rg",
    "ip", "client_ip", "remote_addr", "user_agent",
}

# ── Patterns de redacao em texto livre ────────────────────────────
_REDACTION_PATTERNS = [
    # Telefones brasileiros
    (re.compile(r"\+?\d{2}\s?\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}"), "_mask_phone"),
    # Emails
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "_hash_email"),
    # CPF
    (re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}"), "_redact_cpf"),
    # CNPJ
    (re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"), "_redact_cnpj"),
    # JWT tokens
    (re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"), "_redact_jwt"),
    # API keys genéricos
    (re.compile(r"(sk-|ak-|key-|token-)[a-zA-Z0-9]{16,}"), "_redact_key"),
    # Números de cartão
    (re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"), "_redact_card"),
]

# ── Query params sensiveis em URLs ───────────────────────────────
_SENSITIVE_QUERY_PARAMS = re.compile(
    r"([?&])(token|key|password|secret|api_key|access_token|auth)=([^&]*)",
    re.IGNORECASE,
)


class RedactionFilter:
    """
    Filtro configuravel de redacao de dados sensiveis.
    """

    def __init__(
        self,
        blacklisted_fields: Set[str] = None,
        masked_fields: Set[str] = None,
        redact_text_patterns: bool = True,
    ):
        self.blacklisted = blacklisted_fields or BLACKLISTED_FIELDS
        self.masked = masked_fields or MASKED_FIELDS
        self.redact_text = redact_text_patterns

    def should_blacklist(self, field_name: str) -> bool:
        """Verifica se um campo deve ser completamente removido."""
        return field_name.lower() in self.blacklisted

    def should_mask(self, field_name: str) -> bool:
        """Verifica se um campo deve ser mascarado."""
        return field_name.lower() in self.masked

    def process_value(self, key: str, value: Any) -> Any:
        """Processa um valor aplicando redacao conforme necessario."""
        key_lower = key.lower()

        if self.should_blacklist(key_lower):
            return "[REDACTED]"

        if self.should_mask(key_lower):
            return _mask_value(key_lower, value)

        if isinstance(value, str) and self.redact_text:
            return redact(value)

        if isinstance(value, dict):
            return self.process_dict(value)

        if isinstance(value, list):
            return [self.process_value(key, item) for item in value]

        return value

    def process_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa recursivamente um dicionario aplicando redacao."""
        result = {}
        for key, value in data.items():
            result[key] = self.process_value(key, value)
        return result


# ── Instancia global ─────────────────────────────────────────────
_default_filter = RedactionFilter()


def redact(text: str) -> str:
    """
    Aplica redacao de dados sensiveis em uma string de texto livre.
    Usa patterns de regex para encontrar e mascarar dados pessoais.
    """
    if not isinstance(text, str) or len(text) < 5:
        return text

    result = text
    for pattern, method_name in _REDACTION_PATTERNS:
        method = globals().get(method_name)
        if method:
            result = pattern.sub(lambda m: method(m.group()), result)

    # Redact query params sensiveis em URLs
    result = _SENSITIVE_QUERY_PARAMS.sub(r"\1\2=[REDACTED]", result)

    return result


def redact_processor(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processor de structlog que aplica redacao automatica em todos os campos do log.
    Adicionar na chain de processors do structlog.
    """
    processed = {}
    for key, value in event_dict.items():
        # Preservar campos de controle do structlog
        if key.startswith("_"):
            processed[key] = value
            continue

        processed[key] = _default_filter.process_value(key, value)

    return processed


# ── Funcoes de mascaramento ──────────────────────────────────────

def _mask_phone(phone: str) -> str:
    """Mascara numero de telefone mantendo inicio e fim."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 8:
        return f"+{digits[:4]}****{digits[-4:]}"
    return "[REDACTED_PHONE]"


def _hash_email(email: str) -> str:
    """Substitui email por hash irreversivel."""
    h = hashlib.sha256(email.lower().encode()).hexdigest()[:8]
    return f"email_hash:{h}"


def _redact_cpf(cpf: str) -> str:
    """Mascara CPF completamente."""
    return "***.***.***-**"


def _redact_cnpj(cnpj: str) -> str:
    """Mascara CNPJ completamente."""
    return "**.***.***/*****-**"


def _redact_jwt(token: str) -> str:
    """Substitui JWT por hash parcial."""
    h = hashlib.sha256(token[-8:].encode()).hexdigest()[:8]
    return f"jwt_hash:{h}"


def _redact_key(key: str) -> str:
    """Redacta API keys mantendo prefixo."""
    prefix = key[:3]
    return f"{prefix}...[REDACTED]"


def _redact_card(card: str) -> str:
    """Mascara numero de cartao."""
    digits = re.sub(r"\D", "", card)
    if len(digits) >= 12:
        return f"****-****-****-{digits[-4:]}"
    return "[REDACTED_CARD]"


def _mask_value(key_lower: str, value: Any) -> Any:
    """Mascara valor baseado no tipo de campo."""
    if not isinstance(value, str):
        return value

    if key_lower in ("ip", "client_ip", "remote_addr"):
        return _mask_ip(value)
    elif key_lower in ("email",):
        return _hash_email(value)
    elif key_lower in ("phone", "telephone", "celular"):
        return _mask_phone(value)
    elif key_lower in ("cpf",):
        return _redact_cpf(value)
    elif key_lower in ("cnpj",):
        return _redact_cnpj(value)
    elif key_lower == "user_agent":
        return value[:256] if len(value) > 256 else value

    # Fallback: hash parcial
    if len(value) > 4:
        return f"{value[:2]}...{value[-2:]}"
    return "[REDACTED]"


def _mask_ip(ip: str) -> str:
    """Anonimiza ultimo octeto de IPv4."""
    parts = ip.split(".")
    if len(parts) == 4:
        parts[-1] = "xxx"
        return ".".join(parts)
    # IPv6 - hash parcial
    if ":" in ip:
        h = hashlib.sha256(ip.encode()).hexdigest()[:8]
        return f"ipv6_hash:{h}"
    return ip
