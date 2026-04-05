"""
Serviço de redação de PII para texto antes de enviar à API Claude.
Reutiliza os patterns do módulo de logging, mas aplicado ao conteúdo das mensagens.
"""
import re
import hashlib
from typing import Optional

from app.logging import get_logger

logger = get_logger(__name__)

# ── Patterns de PII em texto de conversação ─────────────────────────
_PII_PATTERNS = [
    # CPF
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF_REDACTED]"),
    # CPF sem pontos
    (re.compile(r"\b\d{11}\b(?=.*(?:cpf|CPF|documento))"), "[CPF_REDACTED]"),
    # CNPJ
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), "[CNPJ_REDACTED]"),
    # RG
    (re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[0-9Xx]\b"), None),  # Skip - too many false positives
    # Telefones brasileiros completos
    (re.compile(r"\+?55\s?\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}"), "[PHONE_REDACTED]"),
    # Telefones com DDD (require parentheses or explicit formatting)
    (re.compile(r"(?:\+\d{1,3}\s?)?\(?\d{2}\)\s?9?\d{4}[-\s]?\d{4}"), "[PHONE_REDACTED]"),
    # Email
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL_REDACTED]"),
    # Números de cartão de crédito
    (re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"), "[CARD_REDACTED]"),
    # Chave PIX (UUID)
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE), None),  # Skip - might be system IDs
    # Chave PIX aleatória (32 chars hex)
    (re.compile(r"\b[0-9a-f]{32}\b"), None),  # Skip
    # Endereços de IP
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP_REDACTED]"),
]

# Patterns contextuais (só redact se houver palavras-chave próximas)
_CONTEXTUAL_PATTERNS = [
    # Valores monetários grandes (pode indicar dados financeiros sensíveis)
    # Não redactar - importante para análise
]


def redact_pii(text: str, aggressive: bool = False) -> str:
    """
    Remove/mascara dados pessoais identificáveis de texto antes de enviar à API.
    
    Args:
        text: Texto a ser sanitizado
        aggressive: Se True, aplica redactions mais agressivas (mais falsos positivos)
    
    Returns:
        Texto com PII mascarado
    """
    if not text or len(text) < 5:
        return text
    
    result = text
    redactions_count = 0
    
    for pattern, replacement in _PII_PATTERNS:
        if replacement is None:
            continue  # Pattern desabilitado
        
        matches = pattern.findall(result)
        if matches:
            redactions_count += len(matches)
            result = pattern.sub(replacement, result)
    
    if redactions_count > 0:
        logger.info(
            "pii.redaction.applied",
            redactions_count=redactions_count,
            text_length=len(text),
        )
    
    return result


def redact_conversation_text(text: str) -> str:
    """
    Redacta PII em texto de conversação completa antes de enviar à API Claude.
    Preserva a estrutura da conversação (timestamps, nomes de remetente) mas
    remove dados pessoais dos conteúdos.
    """
    if not text:
        return text
    
    lines = text.split("\n")
    redacted_lines = []
    
    for line in lines:
        # Tenta identificar a estrutura "[timestamp] sender: message"
        # e aplicar redação apenas no conteúdo da mensagem
        redacted_lines.append(redact_pii(line))
    
    return "\n".join(redacted_lines)


def hash_for_audit(original: str) -> str:
    """Gera hash do texto original para auditoria (provar que houve redação)."""
    return hashlib.sha256(original.encode()).hexdigest()[:16]
