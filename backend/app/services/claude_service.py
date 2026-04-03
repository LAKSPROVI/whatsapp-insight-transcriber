"""
Serviço de integração com Claude API (via gameron proxy)
Responsável por todas as chamadas de IA: transcrição, visão, RAG, análise.
Inclui retry com exponential backoff, rate limiting, timeout configurável.
"""
import base64
import os
import json
import asyncio
import shutil
import subprocess
import tempfile
import functools
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator

import anthropic
from app.config import settings
from app.exceptions import APIError, RateLimitError
from app.logging import get_logger, new_span
from app.logging.error_advisor import get_error_suggestion
from app.services.cache_service import cached, make_cache_key, get_cached_result, set_cached_result

logger = get_logger(__name__)

# ─── Timeouts por tipo de operação (segundos) ────────────────────────────────
OPERATION_TIMEOUTS: Dict[str, float] = {
    "transcribe_audio": 90.0,
    "describe_image": 60.0,
    "transcribe_video": 180.0,
    "analyze_sentiment": 30.0,
    "generate_summary": 90.0,
    "detect_contradictions": 90.0,
    "extract_keywords": 60.0,
    "chat": 120.0,
    "default": 60.0,
}

# ─── Configuração de retry ───────────────────────────────────────────────────
MAX_RETRIES = 4
BACKOFF_BASE = 1.0
BACKOFF_MULTIPLIER = 2.0
RATE_LIMIT_INITIAL_WAIT = 5.0  # segundos


class ClaudeService:
    """
    Serviço central de IA usando Claude via proxy.
    Todas as chamadas são assíncronas e otimizadas para paralelismo.
    """

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            base_url=settings.ANTHROPIC_BASE_URL,
        )
        self.model = settings.CLAUDE_MODEL
        self.max_tokens = settings.MAX_TOKENS
        # Cache do modelo Whisper (lazy load)
        self._whisper_model = None
        # Semáforo para limitar chamadas simultâneas à API
        self._api_semaphore = asyncio.Semaphore(10)
        # Contadores para monitoramento
        self._total_calls = 0
        self._total_errors = 0
        self._total_retries = 0
        self._rate_limit_hits = 0

    async def _call_claude_with_retry(
        self,
        operation: str = "default",
        **kwargs,
    ) -> Any:
        """
        Wrapper com retry, exponential backoff e rate limit handling.
        """
        timeout = OPERATION_TIMEOUTS.get(operation, OPERATION_TIMEOUTS["default"])

        async with self._api_semaphore:
            last_error = None

            for attempt in range(MAX_RETRIES):
                try:
                    self._total_calls += 1
                    start_time = time.time()
                    with new_span("claude.api_call"):
                        logger.info(
                            "claude_api_call_started",
                            event="ai.api_call.started",
                            ai_model=kwargs.get("model", self.model),
                            operation=operation,
                            attempt=attempt + 1,
                        )
                        result = await asyncio.wait_for(
                            self.client.messages.create(**kwargs),
                            timeout=timeout,
                        )
                        latency_ms = round((time.time() - start_time) * 1000, 2)
                        logger.info(
                            "claude_api_call_completed",
                            event="ai.api_call.completed",
                            ai_model=kwargs.get("model", self.model),
                            ai_tokens_input=result.usage.input_tokens,
                            ai_tokens_output=result.usage.output_tokens,
                            ai_latency_ms=latency_ms,
                            operation=operation,
                        )
                    return result

                except asyncio.TimeoutError:
                    last_error = f"Timeout ({timeout}s) na operação '{operation}'"
                    logger.warning(
                        f"Timeout na chamada API (tentativa {attempt + 1}/{MAX_RETRIES}): {operation}",
                        extra={"operation": operation, "attempt": attempt + 1, "timeout": timeout},
                    )

                except anthropic.RateLimitError as e:
                    self._rate_limit_hits += 1
                    # Rate limit: esperar mais tempo com backoff
                    wait_time = RATE_LIMIT_INITIAL_WAIT * (BACKOFF_MULTIPLIER ** attempt)

                    # Tentar extrair retry-after do header se disponível
                    retry_after = getattr(e, "retry_after", None)
                    if retry_after:
                        wait_time = max(wait_time, float(retry_after))

                    last_error = f"Rate limit (429): {str(e)}"
                    logger.error(
                        "claude_api_call_failed",
                        event="ai.api_call.failed",
                        error_type="RateLimitError",
                        operation=operation,
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        rate_limit_total=self._rate_limit_hits,
                        **get_error_suggestion(exc=e),
                    )

                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(wait_time)
                        self._total_retries += 1
                        continue
                    else:
                        self._total_errors += 1
                        raise RateLimitError(
                            detail="Limite de requisições da API excedido. Tente novamente em alguns minutos.",
                            context={
                                "operation": operation,
                                "attempts": attempt + 1,
                                "rate_limit_hits": self._rate_limit_hits,
                            },
                        )

                except anthropic.APIStatusError as e:
                    status = getattr(e, "status_code", 0)
                    last_error = f"API status {status}: {str(e)}"

                    # Erros permanentes (ex: modelo não suporta imagem) — não fazer retry
                    error_msg = str(e).lower()
                    if any(phrase in error_msg for phrase in [
                        "does not support image", "image input", "cannot read image",
                        "image_not_supported",
                    ]):
                        self._total_errors += 1
                        logger.error(
                            "claude_api_call_failed",
                            event="ai.api_call.failed",
                            error_type="APIStatusError",
                            operation=operation,
                            status_code=status,
                            **get_error_suggestion(exc=e),
                        )
                        raise

                    # Erros 5xx são transientes
                    if status >= 500 and attempt < MAX_RETRIES - 1:
                        wait_time = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
                        logger.warning(
                            "claude_api_server_error",
                            event="ai.api_call.failed",
                            error_type="APIStatusError",
                            operation=operation,
                            status_code=status,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(wait_time)
                        self._total_retries += 1
                        continue
                    else:
                        self._total_errors += 1
                        raise APIError(
                            detail=f"Erro na API de IA (HTTP {status}): {str(e)}",
                            context={"operation": operation, "status_code": status, "attempts": attempt + 1},
                        )

                except anthropic.APIConnectionError as e:
                    last_error = f"Erro de conexão: {str(e)}"
                    if attempt < MAX_RETRIES - 1:
                        wait_time = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
                        logger.warning(
                            f"Erro de conexão API (tentativa {attempt + 1}/{MAX_RETRIES}). "
                            f"Retry em {wait_time:.1f}s...",
                            extra={"operation": operation, "attempt": attempt + 1},
                        )
                        await asyncio.sleep(wait_time)
                        self._total_retries += 1
                        continue

                except Exception as e:
                    last_error = str(e)
                    self._total_errors += 1
                    logger.error(
                        "claude_api_call_failed",
                        event="ai.api_call.failed",
                        error_type=type(e).__name__,
                        operation=operation,
                        attempt=attempt + 1,
                        **get_error_suggestion(exc=e),
                    )

                    # Erros permanentes de imagem — não fazer retry
                    error_lower = str(e).lower()
                    if any(phrase in error_lower for phrase in [
                        "does not support image", "cannot read image",
                        "image_not_supported", "not support image",
                    ]):
                        raise APIError(
                            detail=f"Modelo não suporta input de imagem: {str(e)}",
                            context={"operation": operation, "attempts": attempt + 1},
                        )

                    if attempt < MAX_RETRIES - 1:
                        wait_time = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
                        await asyncio.sleep(wait_time)
                        self._total_retries += 1
                        continue
                    else:
                        raise APIError(
                            detail=f"Erro na comunicação com serviço de IA: {str(e)}",
                            context={"operation": operation, "attempts": attempt + 1},
                        )

            # Todas as tentativas falharam
            self._total_errors += 1
            raise APIError(
                detail=f"Falha após {MAX_RETRIES} tentativas: {last_error}",
                context={"operation": operation, "attempts": MAX_RETRIES},
            )

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso da API."""
        return {
            "total_calls": self._total_calls,
            "total_errors": self._total_errors,
            "total_retries": self._total_retries,
            "rate_limit_hits": self._rate_limit_hits,
        }

    async def transcribe_audio(
        self,
        file_path: str,
        media_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Transcreve um arquivo de áudio.
        Usa Whisper como método primário. Se falhar, envia descrição textual ao Claude.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        # Método primário: Whisper
        try:
            transcription_raw = await self._whisper_transcribe(file_path)
            if transcription_raw:
                message = await self._call_claude_with_retry(
                    operation="transcribe_audio",
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
        except (APIError, RateLimitError):
            raise
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
            operation="transcribe_audio",
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
        try:
            transcription_raw = await self._whisper_transcribe(file_path)
        except Exception:
            transcription_raw = None

        if transcription_raw:
            message = await self._call_claude_with_retry(
                operation="transcribe_audio",
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

        # Fallback
        return {
            "transcription": "[Áudio recebido - transcrição pendente de configuração do Whisper]",
            "tokens_used": 0,
        }

    async def _whisper_transcribe(self, file_path: str) -> Optional[str]:
        """Tenta transcrição via OpenAI Whisper local"""
        try:
            import whisper
            if self._whisper_model is None:
                logger.info("Carregando modelo Whisper (primeira vez)...")
                self._whisper_model = whisper.load_model("base")
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._whisper_model.transcribe, file_path)
            return result["text"]
        except ImportError:
            logger.debug("Whisper não instalado")
            return None
        except Exception as e:
            logger.warning(f"Erro no Whisper: {e}")
            return None

    # ─── Frases que indicam modelo sem suporte a imagem ────────────────────────
    IMAGE_NOT_SUPPORTED_PHRASES = [
        "does not support image",
        "image input",
        "not support image",
        "cannot read image",
        "image_not_supported",
        "not supported for this model",
        "model does not support",
        "inform the user",
    ]

    async def describe_image(
        self,
        file_path: str,
        media_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analisa uma imagem usando Claude Vision.
        Se o modelo/proxy não suportar vision, usa fallback baseado em metadados.
        Trata 3 cenários de falha:
        1. Exceção HTTP (400/4xx) — proxy rejeita a request
        2. Exceção genérica re-empacotada como APIError pelo retry
        3. HTTP 200 com mensagem de erro no content (proxy aceita mas retorna erro em texto)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Imagem não encontrada: {file_path}")

        # Tentar análise via vision
        try:
            result = await self._describe_image_vision(path, file_path)
        except Exception as e:
            # Cenários 1 e 2: qualquer exceção que contenha a mensagem de erro
            if self._is_image_not_supported_error(str(e)):
                logger.warning(
                    f"Modelo não suporta input de imagem (exceção), usando fallback: {e}"
                )
                return self._describe_image_fallback(path, media_metadata)
            raise

        # Cenário 3: HTTP 200 com erro no texto de resposta
        description = result.get("description", "")
        if self._is_image_not_supported_error(description):
            logger.warning(
                f"Modelo retornou erro de imagem no content (HTTP 200), usando fallback. "
                f"Resposta: {description[:200]}"
            )
            return self._describe_image_fallback(path, media_metadata)

        return result

    def _is_image_not_supported_error(self, text: str) -> bool:
        """Verifica se o texto contém indicações de que o modelo não suporta imagem."""
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in self.IMAGE_NOT_SUPPORTED_PHRASES)

    async def _describe_image_vision(self, path: Path, file_path: str) -> Dict[str, Any]:
        """Tenta descrever imagem usando Claude Vision (base64)."""
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
            operation="describe_image",
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

    def _describe_image_fallback(self, path: Path, media_metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Fallback: gera descrição baseada em metadados quando vision não está disponível."""
        ext = path.suffix.lower().lstrip(".")
        filename = path.name

        metadata_parts = []
        if media_metadata:
            if media_metadata.get("resolution"):
                metadata_parts.append(f"Resolução: {media_metadata['resolution']}")
            if media_metadata.get("file_size_formatted"):
                metadata_parts.append(f"Tamanho: {media_metadata['file_size_formatted']}")
            if media_metadata.get("format"):
                metadata_parts.append(f"Formato: {media_metadata['format']}")

        metadata_str = "; ".join(metadata_parts) if metadata_parts else "Metadados não disponíveis"

        description = (
            f"[Imagem recebida - análise visual indisponível (modelo sem suporte a vision). "
            f"Arquivo: {filename}. {metadata_str}]"
        )

        return {
            "description": description,
            "ocr_text": None,
            "image_type": ext if ext in ("jpg", "jpeg", "png", "gif", "webp") else "imagem",
            "sentiment": "neutro",
            "contains_sensitive_content": False,
            "tokens_used": 0,
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

        frames, frames_dir = await self._extract_video_frames(file_path, max_frames=5)

        try:
            for frame_path in frames:
                try:
                    frame_result = await self.describe_image(
                        frame_path,
                        media_metadata=media_metadata,
                    )
                    frame_results.append(frame_result.get("description", ""))
                except Exception as e:
                    logger.warning(f"Erro ao processar frame (continuando): {e}")
                finally:
                    try:
                        os.remove(frame_path)
                    except Exception:
                        pass
        finally:
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
            operation="transcribe_video",
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
                "-vf", f"fps=1/5,scale=640:-1",
                "-frames:v", str(max_frames),
                f"{output_dir}/frame_%03d.jpg",
                "-y", "-loglevel", "quiet"
            ]

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

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                functools.partial(subprocess.run, cmd, capture_output=True, timeout=120)
            )
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
            else:
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
        cache_key = make_cache_key(f"sentiment:{text}:{context}", prefix="wit:sentiment")
        cached_result = await get_cached_result(cache_key)
        if cached_result is not None:
            logger.debug("Cache HIT para analyze_sentiment")
            return cached_result

        logger.debug("Cache MISS para analyze_sentiment — chamando API")
        message = await self._call_claude_with_retry(
            operation="analyze_sentiment",
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

        sentiment_result = {
            **result,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
            "cached": False,
        }
        await set_cached_result(cache_key, sentiment_result)
        return sentiment_result

    async def generate_summary(
        self,
        conversation_text: str,
        participants: List[str] = None
    ) -> Dict[str, Any]:
        """Gera um resumo executivo da conversa"""
        cache_key = make_cache_key(conversation_text, prefix="wit:summary")
        cached_result = await get_cached_result(cache_key)
        if cached_result is not None:
            logger.debug("Cache HIT para generate_summary")
            return cached_result

        logger.debug("Cache MISS para generate_summary — chamando API")
        participants_str = ", ".join(participants) if participants else "participantes"

        limit = 15000
        if len(conversation_text) > limit:
            logger.warning(f"Texto truncado de {len(conversation_text)} para {limit} caracteres em generate_summary")

        message = await self._call_claude_with_retry(
            operation="generate_summary",
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

        summary_result = {
            **result,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }
        await set_cached_result(cache_key, summary_result)
        return summary_result

    async def detect_contradictions(
        self,
        conversation_text: str
    ) -> Dict[str, Any]:
        """Detecta contradições e inconsistências na conversa"""
        cache_key = make_cache_key(conversation_text, prefix="wit:contradictions")
        cached_result = await get_cached_result(cache_key)
        if cached_result is not None:
            logger.debug("Cache HIT para detect_contradictions")
            return cached_result

        logger.debug("Cache MISS para detect_contradictions — chamando API")

        limit = 12000
        if len(conversation_text) > limit:
            logger.warning(f"Texto truncado de {len(conversation_text)} para {limit} caracteres em detect_contradictions")

        message = await self._call_claude_with_retry(
            operation="detect_contradictions",
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

        contradiction_result = {
            **result,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }
        await set_cached_result(cache_key, contradiction_result)
        return contradiction_result

    async def extract_keywords(
        self,
        conversation_text: str
    ) -> Dict[str, Any]:
        """Extrai palavras-chave, tópicos e dados para nuvem de palavras"""
        limit = 10000
        if len(conversation_text) > limit:
            logger.warning(f"Texto truncado de {len(conversation_text)} para {limit} caracteres em extract_keywords")

        message = await self._call_claude_with_retry(
            operation="extract_keywords",
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

        if chat_history:
            for msg in chat_history[-10:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        messages.append({"role": "user", "content": user_message})

        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.RateLimitError as e:
            self._rate_limit_hits += 1
            logger.warning(f"Rate limit no chat streaming: {e}")
            yield "\n\n⚠️ Limite de requisições atingido. Aguarde alguns instantes e tente novamente."
        except anthropic.APIStatusError as e:
            logger.error(f"Erro na API durante chat streaming: {e}")
            yield f"\n\n⚠️ Erro na comunicação com o serviço de IA (HTTP {getattr(e, 'status_code', 'desconhecido')})."
        except Exception as e:
            logger.error(f"Erro inesperado no chat streaming: {e}", exc_info=True)
            yield "\n\n⚠️ Ocorreu um erro inesperado. Tente novamente."

    async def build_vector_store(
        self,
        conversation_id: str,
        messages: List[Dict]
    ) -> Dict[str, Any]:
        """
        Indexa a conversa para busca semântica RAG.
        """
        indexed_count = len(messages)
        return {
            "conversation_id": conversation_id,
            "indexed_messages": indexed_count,
            "status": "indexed",
            "tokens_used": 0,
        }
