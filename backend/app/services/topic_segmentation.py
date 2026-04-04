"""
Serviço de segmentação automática de tópicos em conversas.
Agrupa mensagens por tópicos usando IA para identificar mudanças de assunto.
"""
import json
from typing import List, Dict, Any, Optional

from app.logging import get_logger
from app.services.pii_redactor import redact_conversation_text

logger = get_logger(__name__)


class TopicSegmentationService:
    """
    Segmenta conversas em tópicos usando IA.
    Identifica transições de assunto e agrupa mensagens por tema.
    """

    def __init__(self, claude_service):
        self.claude_service = claude_service

    async def segment_conversation(
        self,
        conversation_text: str,
        participants: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Segmenta a conversa em tópicos.
        
        Returns:
            Dict com segments, cada um contendo:
            - topic: nome do tópico
            - summary: resumo do segmento
            - start_index: índice da primeira mensagem
            - end_index: índice da última mensagem
            - key_messages: mensagens-chave do segmento
        """
        limit = 12000
        redacted_text = redact_conversation_text(conversation_text[:limit])

        try:
            from app.services.cache_service import make_cache_key, get_cached_result, set_cached_result

            cache_key = make_cache_key(redacted_text, prefix="wit:topic_seg")
            cached = await get_cached_result(cache_key)
            if cached:
                return cached

            message = await self.claude_service._call_claude_with_retry(
                operation="analyze_sentiment",  # Uses SIMPLE model tier
                model=self.claude_service.get_model_for_operation("analyze_sentiment"),
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": f"""Analise esta conversa e segmente-a por tópicos/assuntos.
Identifique quando o assunto muda e agrupe as mensagens.

CONVERSA:
{redacted_text}

Responda em JSON:
{{
  "segments": [
    {{
      "topic": "nome do tópico",
      "summary": "resumo curto do que foi discutido",
      "message_range": "mensagens 1-15",
      "key_points": ["ponto principal 1", "ponto principal 2"],
      "participants_involved": ["nome1", "nome2"],
      "sentiment": "positive|negative|neutral"
    }}
  ],
  "total_topics": 3,
  "main_topic": "tópico mais discutido",
  "topic_transitions": [
    {{
      "from": "tópico A",
      "to": "tópico B",
      "trigger": "o que causou a mudança"
    }}
  ]
}}

Responda APENAS com o JSON."""
                }]
            )

            try:
                result = json.loads(message.content[0].text.strip())
            except json.JSONDecodeError:
                result = {
                    "segments": [],
                    "total_topics": 0,
                    "main_topic": "",
                    "topic_transitions": [],
                }

            result["tokens_used"] = message.usage.input_tokens + message.usage.output_tokens
            await set_cached_result(cache_key, result)
            return result

        except Exception as e:
            logger.error("topic_segmentation.error", error=str(e))
            return {
                "segments": [],
                "total_topics": 0,
                "main_topic": "",
                "topic_transitions": [],
                "error": str(e),
            }
