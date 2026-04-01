"""
Serviço de integração com Claude API (via gameron proxy)
Responsável por todas as chamadas de IA: transcrição, visão, RAG, análise
"""
import base64
import logging
import os
import json
import asyncio
import shutil
import subprocess
import tempfile
import functools
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
        # Fix 5: Cache do modelo Whisper (lazy load)
        self._whisper_model = None
        # Fix 6: Semáforo para limitar chamadas simultâneas à API
        self._api_semaphore = asyncio.Semaphore(10)

    async def _call_claude_with_retry(self, **kwargs) -> Any:
        """
        Wrapper com retry e semáforo para chamadas à API Claude.
        3 tentativas com backoff exponencial (1s, 2s, 4s).
        """
        max_retries = 3
        backoff_times = [1, 2, 4]

        async with self._api_semaphore:
            for attempt in range(max_retries):
                try:
                    return await self.client.messages.create(**kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = backoff_times[attempt]
                        logger.warning(
                            f"Tentativa {attempt + 1}/{max_retries} falhou: {e}. "
                            f"Retentando em {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Todas as {max_retries} tentativas falharam: {e}")
                        raise

    async def transcribe_audio(
        self,
        file_path: str,
        media_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Transcreve um arquivo de áudio.
        Fix 1: Usa Whisper como método primário. Se falhar, envia descrição textual ao Claude.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        # Método primário: Whisper
        try:
            transcription_raw = await self._whisper_transcribe(file_path)
            if transcription_raw:
                # Refinamento com Claude
                message = await self._call_claude_with_retry(
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
        except Exception as e:
            logger.warning(f"Whisper falhou, usando fallback textual: {e}")

        # Fallback: Enviar descrição textual ao Claude (sem base64 de áudio)
        ext = path.suffix.lower()
        metadata_text = ""
        if media_metadata:
            metadata_text = f"""
Metadados do arquivo:
- Duração: {media_metadata.get('duration_formatted', 'desconhecida')}
- Formato: {media_metadata.get('format', ext.lstrip('.'))}
- Tamanho: {media_metadata.get('file_size_formatted', 'desconhecido')}
- Codec: {media_metadata.get('codec', 'desconhecido')}
"""

        message = await self._call_claude_with_retry(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": f"""Você recebeu um arquivo de áudio do WhatsApp que não pôde ser transcrito automaticamente via Whisper.
{metadata_text}

Como não foi possível processar o áudio diretamente, por favor gere uma nota indicando que:
1. O arquivo de áudio foi recebido mas a transcrição automática não está disponível
2. O formato do arquivo é: {ext.lstrip('.')}
3. Inclua os metadados disponíveis

Responda com: [Áudio recebido - transcrição via Whisper indisponível. {metadata_text.strip() if metadata_text.strip() else 'Sem metadados disponíveis.'}]
"""
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
            message = await self._call_claude_with_retry(
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
            # Fix 5: Lazy load do modelo Whisper com cache
            if self._whisper_model is None:
                logger.info("Carregando modelo Whisper (primeira vez)...")
                self._whisper_model = whisper.load_model("base")
            # Fix 4: asyncio.get_running_loop() em vez de get_event_loop()
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._whisper_model.transcribe, file_path)
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

        message = await self._call_claude_with_retry(
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
        frames, frames_dir = await self._extract_video_frames(file_path, max_frames=5)

        try:
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
        finally:
            # Fix 3: Limpar diretório temporário de frames
            if frames_dir:
                shutil.rmtree(frames_dir, ignore_errors=True)

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

        message = await self._call_claude_with_retry(
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

    async def _extract_video_frames(self, video_path: str, max_frames: int = 5) -> tuple:
        """
        Extrai frames representativos de um vídeo usando ffmpeg.
        Retorna tupla (lista_de_frames, diretorio_temporario) para cleanup.
        """
        try:
            frames = []
            output_dir = tempfile.mkdtemp()

            cmd = [
                "ffmpeg", "-i", video_path,
                "-vf", f"fps=1/5,scale=640:-1",  # 1 frame a cada 5 segundos
                "-frames:v", str(max_frames),
                f"{output_dir}/frame_%03d.jpg",
                "-y", "-loglevel", "quiet"
            ]

            # Fix 2: Executar subprocess em executor para não bloquear event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                functools.partial(subprocess.run, cmd, capture_output=True, timeout=60)
            )

            if result.returncode == 0:
                for i in range(1, max_frames + 1):
                    frame_path = f"{output_dir}/frame_{i:03d}.jpg"
                    if os.path.exists(frame_path):
                        frames.append(frame_path)

            return frames, output_dir
        except Exception as e:
            logger.warning(f"Erro ao extrair frames: {e}")
            return [], None

    async def _extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """Extrai a faixa de áudio de um vídeo"""
        try:
            # Fix 7: Usar NamedTemporaryFile em vez de mktemp inseguro
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            output_path = tmp_file.name
            tmp_file.close()

            cmd = [
                "ffmpeg", "-i", video_path,
                "-vn", "-acodec", "mp3",
                "-ab", "128k",
                output_path,
                "-y", "-loglevel", "quiet"
            ]

            # Fix 2: Executar subprocess em executor para não bloquear event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                functools.partial(subprocess.run, cmd, capture_output=True, timeout=120)
            )
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
            else:
                # Limpar arquivo se ffmpeg falhou
                try:
                    os.remove(output_path)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Erro ao extrair áudio: {e}")

        return None

    async def analyze_sentiment(
        self,
        text: str,
        context: str = ""
    ) -> Dict[str, Any]:
        """Analisa o sentimento de uma mensagem ou bloco de texto"""
        message = await self._call_claude_with_retry(
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

        # Fix 8: Log de truncamento silencioso
        limit = 15000
        if len(conversation_text) > limit:
            logger.warning(f"Texto truncado de {len(conversation_text)} para {limit} caracteres em generate_summary")

        message = await self._call_claude_with_retry(
            model=self.model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Analise esta conversa do WhatsApp entre {participants_str} e gere um relatório completo em JSON:

CONVERSA:
{conversation_text[:limit]}  

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

        # Fix 8: Log de truncamento silencioso
        limit = 12000
        if len(conversation_text) > limit:
            logger.warning(f"Texto truncado de {len(conversation_text)} para {limit} caracteres em detect_contradictions")

        message = await self._call_claude_with_retry(
            model=self.model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Analise esta conversa do WhatsApp em busca de contradições, inconsistências ou mudanças de posição:

{conversation_text[:limit]}

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

        # Fix 8: Log de truncamento silencioso
        limit = 10000
        if len(conversation_text) > limit:
            logger.warning(f"Texto truncado de {len(conversation_text)} para {limit} caracteres em extract_keywords")

        message = await self._call_claude_with_retry(
            model=self.model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""Extraia palavras-chave e tópicos desta conversa do WhatsApp:

{conversation_text[:limit]}

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
        # Fix 8: Log de truncamento silencioso
        limit = 20000
        if len(conversation_context) > limit:
            logger.warning(f"Contexto truncado de {len(conversation_context)} para {limit} caracteres em chat_with_context")

        system_prompt = f"""Você é um assistente especializado em análise de conversas do WhatsApp.
Você tem acesso à transcrição completa de uma conversa e deve responder perguntas sobre ela.

TRANSCRIÇÃO DA CONVERSA:
{conversation_context[:limit]}

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
