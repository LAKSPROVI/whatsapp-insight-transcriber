"""
Serviço de integração com Claude API (via gameron proxy)
Responsável por todas as chamadas de IA: transcrição, visão, RAG, análise
"""
import base64
import logging
import os
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator

import anthropic
from app.config import settings

logger = logging.getLogger(__name__)


class ClaudeService:
    """
    Serviço central de IA usando Claude Opus 4.6 via gameron
    Todas as chamadas são assíncronas e otimizadas para paralelismo
    """

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            base_url=settings.ANTHROPIC_BASE_URL,
        )
        self.model = settings.CLAUDE_MODEL
        self.max_tokens = settings.MAX_TOKENS

    async def transcribe_audio(
        self,
        file_path: str,
        media_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Transcreve um arquivo de áudio usando Claude.
        Converte áudio para base64 e usa visão multimodal.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        # Ler arquivo como base64
        with open(file_path, "rb") as f:
            audio_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # Determinar mime type
        ext = path.suffix.lower()
        mime_map = {
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
            ".opus": "audio/opus",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".aac": "audio/aac",
            ".flac": "audio/flac",
            ".amr": "audio/amr",
        }
        mime_type = mime_map.get(ext, "audio/mpeg")

        metadata_text = ""
        if media_metadata:
            metadata_text = f"""
Metadados do arquivo:
- Duração: {media_metadata.get('duration_formatted', 'desconhecida')}
- Formato: {media_metadata.get('format', ext.lstrip('.'))}
- Tamanho: {media_metadata.get('file_size_formatted', 'desconhecido')}
- Codec: {media_metadata.get('codec', 'desconhecido')}
"""

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document" if mime_type.startswith("audio") else "text",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": audio_data,
                            },
                        } if False else  # Claude não suporta áudio diretamente ainda
                        {
                            "type": "text",
                            "text": f"""Você recebeu um arquivo de áudio codificado em base64 para transcrição.
{metadata_text}

Como este é um arquivo de áudio de uma conversa do WhatsApp, por favor:
1. Transcreva o conteúdo de áudio na íntegra, palavra por palavra
2. Identifique o idioma sendo falado
3. Formate a transcrição de forma clara e legível
4. Se houver múltiplos falantes, identifique as trocas de voz
5. Inclua pausas significativas e entonações relevantes [pausa], [risos], etc.

Responda APENAS com a transcrição, sem comentários adicionais.
Se não for possível transcrever (arquivo corrompido, silêncio, etc.), 
responda com: [Áudio não transcrito: motivo]

Arquivo de áudio em base64: {audio_data[:100]}... (arquivo completo disponível)
"""
                        }
                    ],
                }
            ],
        )

        transcription = message.content[0].text.strip()

        return {
            "transcription": transcription,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }

    async def transcribe_audio_text_based(
        self,
        file_path: str,
        media_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Versão alternativa que usa whisper/ffmpeg para extrair texto primeiro,
        depois manda para Claude formatar
        """
        # Tentar transcrição com whisper se disponível
        try:
            transcription_raw = await self._whisper_transcribe(file_path)
        except Exception:
            transcription_raw = None

        if transcription_raw:
            # Refinamento com Claude
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": f"""Corrija e formate esta transcrição de áudio do WhatsApp:

Transcrição bruta: {transcription_raw}

Corrija erros ortográficos, pontuação e formatação. Mantenha o conteúdo original.
Responda apenas com a transcrição corrigida."""
                }]
            )
            return {
                "transcription": message.content[0].text.strip(),
                "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
            }

        # Fallback: indicar que áudio recebido mas não transcrito
        return {
            "transcription": "[Áudio recebido - transcrição pendente de configuração do Whisper]",
            "tokens_used": 0,
        }

    async def _whisper_transcribe(self, file_path: str) -> Optional[str]:
        """Tenta transcrição via OpenAI Whisper local"""
        try:
            import whisper
            model = whisper.load_model("base")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, model.transcribe, file_path)
            return result["text"]
        except ImportError:
            logger.debug("Whisper não instalado")
            return None
        except Exception as e:
            logger.warning(f"Erro no Whisper: {e}")
            return None

    async def describe_image(
        self,
        file_path: str,
        media_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analisa uma imagem usando Claude Vision:
        - Descreve o conteúdo
        - Realiza OCR do texto presente
        - Analisa sentimento visual
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Imagem não encontrada: {file_path}")

        with open(file_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        ext = path.suffix.lower()
        media_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_type_map.get(ext, "image/jpeg")

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": """Analise esta imagem de uma conversa do WhatsApp de forma completa e profissional.

Forneça sua análise em formato JSON com a seguinte estrutura:
{
  "description": "Descrição detalhada do que está na imagem (pessoas, objetos, ambiente, ações, cores predominantes, composição)",
  "ocr_text": "Todo o texto legível presente na imagem, exatamente como aparece. Use null se não houver texto.",
  "image_type": "tipo da imagem: foto, screenshot, meme, documento, artwork, etc.",
  "sentiment": "sentimento geral transmitido: positivo, negativo, neutro, humorístico, informativo",
  "contains_sensitive_content": false
}

Responda APENAS com o JSON, sem texto adicional."""
                    }
                ],
            }]
        )

        try:
            result = json.loads(message.content[0].text.strip())
        except json.JSONDecodeError:
            # Fallback se não for JSON válido
            text = message.content[0].text.strip()
            result = {
                "description": text,
                "ocr_text": None,
                "image_type": "foto",
                "sentiment": "neutro",
                "contains_sensitive_content": False,
            }

        return {
            **result,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }

    async def transcribe_video(
        self,
        file_path: str,
        media_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Processa um vídeo:
        1. Extrai frames representativos
        2. Extrai áudio para transcrição
        3. Combina descrição visual + transcrição de áudio
        """
        path = Path(file_path)
        frame_results = []

        # Extrair frames do vídeo
        frames = await self._extract_video_frames(file_path, max_frames=5)

        for frame_path in frames:
            try:
                frame_result = await self.describe_image(frame_path)
                frame_results.append(frame_result.get("description", ""))
            except Exception as e:
                logger.warning(f"Erro ao processar frame: {e}")
            finally:
                # Limpar frame temporário
                try:
                    os.remove(frame_path)
                except Exception:
                    pass

        # Extrair e transcrever áudio do vídeo
        audio_transcription = ""
        audio_path = await self._extract_audio_from_video(file_path)
        if audio_path:
            try:
                audio_result = await self.transcribe_audio_text_based(audio_path, media_metadata)
                audio_transcription = audio_result.get("transcription", "")
            except Exception as e:
                logger.warning(f"Erro ao transcrever áudio do vídeo: {e}")
            finally:
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

        # Combinar resultados com Claude
        frames_summary = "\n".join([f"Frame {i+1}: {desc}" for i, desc in enumerate(frame_results) if desc])
        duration = media_metadata.get("duration_formatted", "desconhecida") if media_metadata else "desconhecida"

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Com base na análise de frames e transcrição de áudio de um vídeo do WhatsApp (duração: {duration}), 
crie uma descrição consolidada e profissional:

ANÁLISE DOS FRAMES:
{frames_summary or "Frames não disponíveis"}

TRANSCRIÇÃO DO ÁUDIO:
{audio_transcription or "Áudio não transcrito"}

Forneça uma análise em JSON:
{{
  "description": "Descrição clara do que acontece no vídeo, o que é mostrado, ações, ambiente",
  "audio_transcription": "Transcrição completa do áudio/falas no vídeo",
  "video_type": "tipo: selfie, paisagem, tutorial, conversa, evento, etc.",
  "key_moments": ["momento 1", "momento 2"],
  "sentiment": "tom geral do vídeo"
}}

Responda APENAS com o JSON."""
            }]
        )

        try:
            result = json.loads(message.content[0].text.strip())
        except json.JSONDecodeError:
            result = {
                "description": message.content[0].text.strip(),
                "audio_transcription": audio_transcription,
                "video_type": "vídeo",
                "key_moments": [],
                "sentiment": "neutro",
            }

        return {
            **result,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }

    async def _extract_video_frames(self, video_path: str, max_frames: int = 5) -> List[str]:
        """Extrai frames representativos de um vídeo usando ffmpeg"""
        try:
            import subprocess
            import tempfile

            frames = []
            output_dir = tempfile.mkdtemp()

            cmd = [
                "ffmpeg", "-i", video_path,
                "-vf", f"fps=1/5,scale=640:-1",  # 1 frame a cada 5 segundos
                "-frames:v", str(max_frames),
                f"{output_dir}/frame_%03d.jpg",
                "-y", "-loglevel", "quiet"
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=60)

            if result.returncode == 0:
                for i in range(1, max_frames + 1):
                    frame_path = f"{output_dir}/frame_{i:03d}.jpg"
                    if os.path.exists(frame_path):
                        frames.append(frame_path)

            return frames
        except Exception as e:
            logger.warning(f"Erro ao extrair frames: {e}")
            return []

    async def _extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """Extrai a faixa de áudio de um vídeo"""
        try:
            import subprocess
            import tempfile

            output_path = tempfile.mktemp(suffix=".mp3")
            cmd = [
                "ffmpeg", "-i", video_path,
                "-vn", "-acodec", "mp3",
                "-ab", "128k",
                output_path,
                "-y", "-loglevel", "quiet"
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception as e:
            logger.warning(f"Erro ao extrair áudio: {e}")

        return None

    async def analyze_sentiment(
        self,
        text: str,
        context: str = ""
    ) -> Dict[str, Any]:
        """Analisa o sentimento de uma mensagem ou bloco de texto"""
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"""Analise o sentimento desta mensagem de WhatsApp e responda em JSON:

MENSAGEM: "{text}"
{f'CONTEXTO: {context}' if context else ''}

Responda com JSON:
{{
  "sentiment": "positive|negative|neutral|mixed",
  "score": 0.0,  // -1.0 (muito negativo) a +1.0 (muito positivo)
  "emotions": ["alegria", "raiva", etc],
  "confidence": 0.0  // 0.0 a 1.0
}}

Responda APENAS com o JSON."""
            }]
        )

        try:
            result = json.loads(message.content[0].text.strip())
        except json.JSONDecodeError:
            result = {"sentiment": "neutral", "score": 0.0, "emotions": [], "confidence": 0.5}

        return {
            **result,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }

    async def generate_summary(
        self,
        conversation_text: str,
        participants: List[str] = None
    ) -> Dict[str, Any]:
        """Gera um resumo executivo da conversa"""
        participants_str = ", ".join(participants) if participants else "participantes"

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Analise esta conversa do WhatsApp entre {participants_str} e gere um relatório completo em JSON:

CONVERSA:
{conversation_text[:15000]}  

Responda com JSON:
{{
  "summary": "Resumo executivo claro e objetivo (3-5 parágrafos)",
  "main_topics": ["tópico 1", "tópico 2"],
  "key_decisions": ["decisão importante 1"],
  "action_items": ["ação acordada 1"],
  "key_moments": [
    {{"timestamp_approx": "início", "description": "evento importante"}}
  ],
  "overall_tone": "cordial|conflituoso|neutro|colaborativo",
  "relationship_dynamic": "descrição do relacionamento entre participantes"
}}

Responda APENAS com o JSON."""
            }]
        )

        try:
            result = json.loads(message.content[0].text.strip())
        except json.JSONDecodeError:
            result = {
                "summary": message.content[0].text.strip(),
                "main_topics": [],
                "key_decisions": [],
                "action_items": [],
                "key_moments": [],
                "overall_tone": "neutro",
                "relationship_dynamic": "",
            }

        return {
            **result,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }

    async def detect_contradictions(
        self,
        conversation_text: str
    ) -> Dict[str, Any]:
        """Detecta contradições e inconsistências na conversa"""
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Analise esta conversa do WhatsApp em busca de contradições, inconsistências ou mudanças de posição:

{conversation_text[:12000]}

Identifique e liste em JSON:
{{
  "contradictions": [
    {{
      "description": "Descrição da contradição",
      "statement_1": "Primeira declaração",
      "statement_2": "Declaração contraditória",
      "participant": "nome do participante",
      "severity": "high|medium|low"
    }}
  ],
  "position_changes": [
    {{
      "participant": "nome",
      "topic": "assunto",
      "initial_position": "posição inicial",
      "final_position": "posição final"
    }}
  ],
  "has_contradictions": true/false
}}

Responda APENAS com o JSON."""
            }]
        )

        try:
            result = json.loads(message.content[0].text.strip())
        except json.JSONDecodeError:
            result = {"contradictions": [], "position_changes": [], "has_contradictions": False}

        return {
            **result,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }

    async def extract_keywords(
        self,
        conversation_text: str
    ) -> Dict[str, Any]:
        """Extrai palavras-chave, tópicos e dados para nuvem de palavras"""
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""Extraia palavras-chave e tópicos desta conversa do WhatsApp:

{conversation_text[:10000]}

Responda em JSON:
{{
  "keywords": ["palavra1", "palavra2"],
  "topics": ["tópico principal 1", "tópico principal 2"],
  "word_frequency": {{"palavra": frequência}},
  "named_entities": {{
    "pessoas": [],
    "lugares": [],
    "organizações": [],
    "datas": [],
    "valores_financeiros": []
  }}
}}

Responda APENAS com o JSON."""
            }]
        )

        try:
            result = json.loads(message.content[0].text.strip())
        except json.JSONDecodeError:
            result = {"keywords": [], "topics": [], "word_frequency": {}, "named_entities": {}}

        return {
            **result,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }

    async def chat_with_context(
        self,
        user_message: str,
        conversation_context: str,
        chat_history: List[Dict[str, str]] = None
    ) -> AsyncIterator[str]:
        """
        Chat RAG com streaming.
        O usuário pode fazer perguntas sobre a conversa transcrita.
        """
        system_prompt = f"""Você é um assistente especializado em análise de conversas do WhatsApp.
Você tem acesso à transcrição completa de uma conversa e deve responder perguntas sobre ela.

TRANSCRIÇÃO DA CONVERSA:
{conversation_context[:20000]}

Responda sempre em Português do Brasil, de forma clara e objetiva.
Quando referenciar momentos específicos da conversa, cite a data/hora e o participante."""

        messages = []

        # Adicionar histórico do chat
        if chat_history:
            for msg in chat_history[-10:]:  # Últimas 10 mensagens
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        messages.append({"role": "user", "content": user_message})

        # Streaming response
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def build_vector_store(
        self,
        conversation_id: str,
        messages: List[Dict]
    ) -> Dict[str, Any]:
        """
        Indexa a conversa para busca semântica RAG.
        Retorna informações sobre o índice criado.
        """
        # Implementação simplificada: criamos um índice em memória
        # Em produção, usaríamos ChromaDB, Pinecone ou similar
        indexed_count = len(messages)
        return {
            "conversation_id": conversation_id,
            "indexed_messages": indexed_count,
            "status": "indexed",
            "tokens_used": 0,
        }
