"""
Serviço principal de processamento de conversas.
Orquestra todo o fluxo: parse -> DB -> agentes -> análise -> resultado.
Inclui tratamento de erros granular, retry e status parcial.
"""
import asyncio
import os
import shutil
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.exceptions import ParserError, ProcessingError, APIError
from app.logging import get_logger, new_span
from app.logging.error_advisor import get_error_suggestion
from app.models import (
    Conversation, Message, AgentJob as AgentJobModel,
    ProcessingStatus, MediaType, SentimentType
)
from app.services.whatsapp_parser import WhatsAppParser, ParsedMessage
from app.services.media_metadata import MediaMetadataExtractor
from app.services.agent_orchestrator import AgentOrchestrator, AgentJob, JobType
from app.services.claude_service import ClaudeService

logger = get_logger(__name__)


class ConversationProcessor:
    """
    Serviço principal que coordena todo o pipeline de processamento.
    """

    def __init__(self, db: AsyncSession, orchestrator: AgentOrchestrator):
        self.db = db
        self.orchestrator = orchestrator
        self.claude = orchestrator.claude_service
        self._progress_callbacks: Dict[str, List[Callable]] = {}

    async def _notify_progress(self, callback: Callable, conversation) -> None:
        """Chama progress_callback verificando se é async ou não"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(conversation)
            else:
                callback(conversation)
        except Exception as e:
            logger.warning(f"Erro no progress callback: {e}", exc_info=True)

    async def process_upload(
        self,
        zip_path: str,
        original_filename: str,
        session_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> Conversation:
        """
        Pipeline completo de processamento de um arquivo ZIP do WhatsApp.
        Cada etapa tem tratamento de erros independente com status parcial.
        """
        conversation = None
        step = "init"
        failed_steps: List[str] = []

        try:
            # ─── 1. Buscar registro existente ou criar na DB ──────────────
            step = "create_record"
            extract_dir = str(settings.MEDIA_DIR / session_id)

            # O router de upload já cria o Conversation — buscar pelo session_id
            stmt = select(Conversation).where(Conversation.session_id == session_id)
            result = await self.db.execute(stmt)
            conversation = result.scalar_one_or_none()

            if conversation:
                # Atualizar registro existente
                conversation.status = ProcessingStatus.PARSING
                conversation.progress = 0.05
                conversation.progress_message = "Descompactando arquivo..."
                conversation.extract_path = extract_dir
                await self.db.commit()
                await self.db.refresh(conversation)
            else:
                # Fallback: criar novo se chamado diretamente (sem router)
                conversation = Conversation(
                    session_id=session_id,
                    original_filename=original_filename,
                    upload_path=zip_path,
                    extract_path=extract_dir,
                    status=ProcessingStatus.PARSING,
                    progress=0.05,
                    progress_message="Descompactando arquivo...",
                )
                self.db.add(conversation)
                await self.db.commit()
                await self.db.refresh(conversation)

            if progress_callback:
                await self._notify_progress(progress_callback, conversation)

            logger.info(
                "Processamento iniciado",
                extra={"session_id": session_id, "step": step, "filename": original_filename},
            )

            # ─── 2. Extrair ZIP e fazer parse ─────────────────────────────
            step = "parse"
            try:
                parser = WhatsAppParser()
                chat_file, media_files = parser.extract_zip(zip_path, extract_dir)
                parsed_messages = parser.parse_file(chat_file)

                if not parsed_messages:
                    raise ParserError(
                        detail="Nenhuma mensagem encontrada no arquivo",
                        context={"session_id": session_id, "chat_file": chat_file},
                    )
            except ParserError:
                raise
            except Exception as e:
                raise ParserError(
                    detail=f"Erro no parsing do arquivo: {str(e)}",
                    context={"session_id": session_id, "step": step},
                )

            date_start, date_end = parser.get_date_range()
            participants = parser.get_participants()
            conversation_name = self._infer_conversation_name(original_filename, participants)

            logger.info(
                "conversation_parse_completed",
                event="conversation.parse.completed",
                session_id=session_id,
                messages_count=len(parsed_messages),
                participants_count=len(participants),
            )

            # ─── 3. Salvar mensagens na DB ────────────────────────────────
            step = "save_messages"
            try:
                await self._update_conversation(conversation, {
                    "status": ProcessingStatus.PROCESSING,
                    "progress": 0.15,
                    "progress_message": f"Analisando {len(parsed_messages)} mensagens...",
                    "conversation_name": conversation_name,
                    "participants": participants,
                    "total_messages": len(parsed_messages),
                    "total_media": sum(1 for m in parsed_messages if m.media_type != "text"),
                    "date_start": date_start,
                    "date_end": date_end,
                })

                if progress_callback:
                    await self._notify_progress(progress_callback, conversation)

                messages_db = await self._save_messages(conversation.id, parsed_messages, parser)
            except Exception as e:
                raise ProcessingError(
                    detail=f"Erro ao salvar mensagens no banco: {str(e)}",
                    context={"session_id": session_id, "step": step, "message_count": len(parsed_messages)},
                )

            # ─── 4. Processar mídias com os 20 agentes em paralelo ────────
            step = "process_media"
            media_messages = [m for m in messages_db if m.media_type != MediaType.TEXT and m.media_path]

            if media_messages:
                try:
                    logger.info(
                        "conversation_media_processing",
                        event="conversation.media.processing",
                        session_id=session_id,
                        media_count=len(media_messages),
                        agents_active=settings.MAX_AGENTS,
                    )
                    await self._update_conversation(conversation, {
                        "progress": 0.20,
                        "progress_message": f"Iniciando {len(media_messages)} processamentos de mídia com {settings.MAX_AGENTS} agentes paralelos...",
                    })
                    if progress_callback:
                        await self._notify_progress(progress_callback, conversation)

                    await self._process_media_parallel(
                        conversation,
                        media_messages,
                        progress_callback=progress_callback,
                    )
                except Exception as e:
                    logger.error(
                        f"Falha no processamento de mídia (continuando): {e}",
                        extra={"session_id": session_id, "step": step},
                        exc_info=True,
                    )
                    failed_steps.append(step)
                    # Continua — mídias são opcionais

            # ─── 5. Análises avançadas ────────────────────────────────────
            step = "advanced_analysis"
            try:
                logger.info(
                    "conversation_analysis_started",
                    event="conversation.analysis.started",
                    session_id=session_id,
                    conversation_id=conversation.id,
                )
                await self._update_conversation(conversation, {
                    "progress": 0.80,
                    "progress_message": "Gerando análises avançadas...",
                })
                if progress_callback:
                    await self._notify_progress(progress_callback, conversation)

                await self._run_advanced_analysis(conversation, parsed_messages)
                logger.info(
                    "conversation_analysis_completed",
                    event="conversation.analysis.completed",
                    session_id=session_id,
                    conversation_id=conversation.id,
                )
            except Exception as e:
                logger.error(
                    "conversation_analysis_failed",
                    event="conversation.analysis.failed",
                    session_id=session_id,
                    step=step,
                    error_type=type(e).__name__,
                    **get_error_suggestion(exc=e),
                )
                failed_steps.append(step)
                # Continua — análises avançadas são opcionais

            # ─── 6. Finalizar ─────────────────────────────────────────────
            step = "finalize"
            status = ProcessingStatus.COMPLETED
            progress_msg = "Processamento concluído!"

            if failed_steps:
                progress_msg = f"Processamento concluído com falhas parciais em: {', '.join(failed_steps)}"
                logger.warning(
                    f"Conversa concluída com falhas parciais",
                    extra={"session_id": session_id, "failed_steps": failed_steps},
                )

            await self._update_conversation(conversation, {
                "status": status,
                "progress": 1.0,
                "progress_message": progress_msg,
                "completed_at": datetime.now(timezone.utc),
            })

            if progress_callback:
                await self._notify_progress(progress_callback, conversation)

            logger.info(
                "conversation_upload_completed",
                event="conversation.upload.completed",
                session_id=session_id,
                conversation_id=conversation.id,
                failed_steps=failed_steps or None,
            )
            return conversation

        except (ParserError, ProcessingError, APIError) as e:
            # Exceções de negócio — repassar com status atualizado
            logger.error(
                "conversation_upload_failed",
                event="conversation.upload.failed",
                session_id=session_id,
                step=step,
                error_type=type(e).__name__,
                **get_error_suggestion(exc=e),
            )
            if conversation:
                await self._update_conversation(conversation, {
                    "status": ProcessingStatus.FAILED,
                    "progress_message": f"Erro na etapa '{step}': {str(e)}",
                })
            raise

        except Exception as e:
            logger.error(
                "conversation_upload_failed",
                event="conversation.upload.failed",
                session_id=session_id,
                step=step,
                error_type=type(e).__name__,
                **get_error_suggestion(exc=e),
            )
            if conversation:
                await self._update_conversation(conversation, {
                    "status": ProcessingStatus.FAILED,
                    "progress_message": f"Erro: {str(e)}",
                })
            raise ProcessingError(
                detail=f"Erro inesperado no processamento: {str(e)}",
                context={"session_id": session_id, "step": step},
            )

    async def _save_messages(
        self,
        conversation_id: str,
        parsed_messages: List[ParsedMessage],
        parser: WhatsAppParser,
    ) -> List[Message]:
        """Salva todas as mensagens no banco de dados"""
        messages_db = []
        base_url = f"/api/media/{conversation_id}"

        for parsed in parsed_messages:
            # Resolver caminho da mídia
            media_path = None
            media_url = None
            media_metadata = None

            if parsed.media_filename:
                resolved_path = parser.get_media_path(parsed.media_filename)
                if resolved_path and os.path.exists(resolved_path):
                    media_path = resolved_path
                    media_url = f"{base_url}/{parsed.media_filename}"
                    # Extrair metadados da mídia
                    try:
                        media_metadata = MediaMetadataExtractor.extract(resolved_path)
                    except Exception as e:
                        logger.warning(f"Erro ao extrair metadados de {parsed.media_filename}: {e}")

            # Mapear tipo de mídia
            media_type_map = {
                "text": MediaType.TEXT,
                "image": MediaType.IMAGE,
                "audio": MediaType.AUDIO,
                "video": MediaType.VIDEO,
                "document": MediaType.DOCUMENT,
                "sticker": MediaType.STICKER,
                "contact": MediaType.CONTACT,
                "location": MediaType.LOCATION,
            }
            db_media_type = media_type_map.get(parsed.media_type, MediaType.TEXT)

            if parsed.is_deleted:
                db_media_type = MediaType.DELETED

            msg = Message(
                conversation_id=conversation_id,
                sequence_number=parsed.sequence,
                timestamp=parsed.timestamp,
                sender=parsed.sender,
                original_text=parsed.text if db_media_type == MediaType.TEXT else None,
                media_type=db_media_type,
                media_filename=parsed.media_filename,
                media_path=media_path,
                media_url=media_url,
                media_metadata=media_metadata,
                processing_status=ProcessingStatus.PENDING if media_path else ProcessingStatus.COMPLETED,
            )
            self.db.add(msg)
            messages_db.append(msg)

        await self.db.commit()

        # Refresh para obter IDs
        for msg in messages_db:
            await self.db.refresh(msg)

        logger.info(f"{len(messages_db)} mensagens salvas no banco")
        return messages_db

    async def _process_media_parallel(
        self,
        conversation: Conversation,
        media_messages: List[Message],
        progress_callback: Optional[Callable] = None,
    ):
        """
        Usa os agentes para processar todas as mídias em paralelo.
        """
        jobs = []
        message_job_map: Dict[str, str] = {}  # job_id -> message_id

        for msg in media_messages:
            if not msg.media_path or not os.path.exists(msg.media_path):
                continue

            # Determinar tipo de job
            if msg.media_type == MediaType.AUDIO:
                job_type = JobType.TRANSCRIBE_AUDIO
            elif msg.media_type == MediaType.IMAGE or msg.media_type == MediaType.STICKER:
                job_type = JobType.DESCRIBE_IMAGE
            elif msg.media_type == MediaType.VIDEO:
                job_type = JobType.TRANSCRIBE_VIDEO
            else:
                continue

            job = AgentJob(
                job_type=job_type,
                conversation_id=conversation.id,
                message_id=msg.id,
                payload={
                    "file_path": msg.media_path,
                    "metadata": msg.media_metadata or {},
                },
                priority=3,  # Alta prioridade
            )
            jobs.append(job)
            message_job_map[job.job_id] = msg.id

        if not jobs:
            return

        logger.info(f"Submetendo {len(jobs)} jobs para {settings.MAX_AGENTS} agentes paralelos")

        # Submeter todos os jobs
        job_ids = await self.orchestrator.submit_batch(jobs)

        # Aguardar com progresso
        processed_count = 0
        total = len(job_ids)

        async def on_progress(completed: int, total_jobs: int):
            nonlocal processed_count
            processed_count = completed
            progress = 0.20 + (completed / total_jobs) * 0.55  # 20% a 75%
            await self._update_conversation(conversation, {
                "progress": progress,
                "progress_message": f"Processando mídias: {completed}/{total_jobs} ({len(self.orchestrator.agents)} agentes ativos)",
            })
            if progress_callback:
                await self._notify_progress(progress_callback, conversation)

        results = await self.orchestrator.wait_for_jobs(
            job_ids,
            progress_callback=on_progress,
            timeout=600.0,
        )

        # Salvar resultados no banco
        success_count = 0
        fail_count = 0

        for job_id, result in results.items():
            if not result:
                fail_count += 1
                continue

            message_id = message_job_map.get(job_id)
            if not message_id:
                continue

            try:
                # Buscar mensagem
                stmt = select(Message).where(Message.id == message_id)
                db_result = await self.db.execute(stmt)
                msg = db_result.scalar_one_or_none()

                if not msg:
                    continue

                if result.success and result.result:
                    data = result.result

                    # Áudio
                    if msg.media_type == MediaType.AUDIO:
                        msg.transcription = data.get("transcription")

                    # Imagem
                    elif msg.media_type in (MediaType.IMAGE, MediaType.STICKER):
                        msg.description = data.get("description")
                        msg.ocr_text = data.get("ocr_text")
                        if data.get("sentiment"):
                            sentiment_map = {
                                "positive": SentimentType.POSITIVE,
                                "negative": SentimentType.NEGATIVE,
                                "neutral": SentimentType.NEUTRAL,
                                "mixed": SentimentType.MIXED,
                            }
                            msg.sentiment = sentiment_map.get(data["sentiment"].lower(), SentimentType.NEUTRAL)

                    # Vídeo
                    elif msg.media_type == MediaType.VIDEO:
                        msg.description = data.get("description")
                        msg.transcription = data.get("audio_transcription")

                    msg.processing_status = ProcessingStatus.COMPLETED
                    msg.processing_time = result.processing_time
                    success_count += 1

                else:
                    msg.processing_status = ProcessingStatus.FAILED
                    msg.error_message = result.error if result else "Job sem resultado"
                    fail_count += 1

            except Exception as e:
                logger.error(f"Erro ao salvar resultado do job {job_id}: {e}", exc_info=True)
                fail_count += 1

        await self.db.commit()
        logger.info(f"Resultados de mídia: {success_count} sucessos, {fail_count} falhas")

    async def _run_advanced_analysis(
        self,
        conversation: Conversation,
        parsed_messages: List[ParsedMessage],
    ):
        """Executa análises avançadas em paralelo com tratamento individual."""
        # Preparar texto da conversa
        total_messages = len(parsed_messages)
        truncated = parsed_messages[:500]
        if total_messages > 500:
            logger.warning(f"Truncando {total_messages} mensagens para 500 na análise avançada")
        conv_text = self._build_conversation_text(truncated)

        # Executar em paralelo: resumo, palavras-chave, contradições, sentimento
        analysis_names = ["summary", "keywords", "contradictions", "sentiment"]
        tasks = [
            self.claude.generate_summary(conv_text, conversation.participants),
            self.claude.extract_keywords(conv_text),
            self.claude.detect_contradictions(conv_text),
            self.claude.analyze_sentiment(conv_text[:3000]),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        updates = {}
        failed_analyses = []

        for name, result in zip(analysis_names, results):
            if isinstance(result, Exception):
                logger.error(
                    f"Análise falhou ({name}): {result}",
                    extra={"analysis": name, "conversation_id": conversation.id},
                )
                failed_analyses.append(name)
                continue

            try:
                if name == "summary":
                    updates["summary"] = result.get("summary", "")
                    updates["key_moments"] = result.get("key_moments", [])

                elif name == "keywords":
                    updates["keywords"] = result.get("keywords", [])
                    updates["topics"] = result.get("topics", [])
                    updates["word_frequency"] = result.get("word_frequency", {})

                elif name == "contradictions":
                    updates["contradictions"] = result.get("contradictions", [])

                elif name == "sentiment":
                    score = result.get("score", 0.0)
                    if score >= 0.3:
                        updates["sentiment_overall"] = SentimentType.POSITIVE
                    elif score <= -0.3:
                        updates["sentiment_overall"] = SentimentType.NEGATIVE
                    else:
                        updates["sentiment_overall"] = SentimentType.NEUTRAL
                    updates["sentiment_score"] = score

            except Exception as e:
                logger.error(f"Erro ao processar resultado de {name}: {e}", exc_info=True)
                failed_analyses.append(name)

        if updates:
            await self._update_conversation(conversation, updates)

        if failed_analyses:
            logger.warning(
                f"Análises com falha: {', '.join(failed_analyses)}",
                extra={"conversation_id": conversation.id},
            )

    def _build_conversation_text(self, messages: List[ParsedMessage]) -> str:
        """Constrói texto formatado da conversa para análise"""
        lines = []
        for msg in messages:
            ts = msg.timestamp.strftime("%d/%m/%Y %H:%M")
            prefix = ""
            if msg.is_forwarded:
                prefix = "[Encaminhada] "
            if msg.is_edited:
                prefix += "[Editada] "

            if msg.media_type == "text":
                lines.append(f"[{ts}] {msg.sender}: {prefix}{msg.text}")
            else:
                lines.append(f"[{ts}] {msg.sender}: {prefix}[mídia: {msg.media_type}]")
        return "\n".join(lines)

    def _infer_conversation_name(self, filename: str, participants: List[str]) -> str:
        """Infere o nome da conversa"""
        name = filename.replace(".zip", "").replace("WhatsApp Chat with ", "").replace("WhatsApp Chat - ", "")
        if name and not name.startswith("WhatsApp"):
            return name.strip()
        if participants:
            return " & ".join(participants[:3])
        return "Conversa"

    async def _update_conversation(self, conversation: Conversation, updates: Dict[str, Any]):
        """Atualiza campos da conversa no banco com retry para erros de DB."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                for key, value in updates.items():
                    setattr(conversation, key, value)
                conversation.updated_at = datetime.now(timezone.utc)
                await self.db.commit()
                await self.db.refresh(conversation)
                return
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Erro ao atualizar conversa (tentativa {attempt + 1}): {e}")
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.error(f"Falha ao atualizar conversa após {max_retries + 1} tentativas: {e}")
                    raise
