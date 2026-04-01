"""
Serviço principal de processamento de conversas.
Orquestra todo o fluxo: parse -> DB -> agentes -> análise -> resultado.
"""
import asyncio
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models import (
    Conversation, Message, AgentJob as AgentJobModel,
    ProcessingStatus, MediaType, SentimentType
)
from app.services.whatsapp_parser import WhatsAppParser, ParsedMessage
from app.services.media_metadata import MediaMetadataExtractor
from app.services.agent_orchestrator import AgentOrchestrator, AgentJob, JobType
from app.services.claude_service import ClaudeService

logger = logging.getLogger(__name__)


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
        """Fix #13: Chama progress_callback verificando se é async ou não"""
        if asyncio.iscoroutinefunction(callback):
            await callback(conversation)
        else:
            callback(conversation)

    async def process_upload(
        self,
        zip_path: str,
        original_filename: str,
        session_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> Conversation:
        """
        Pipeline completo de processamento de um arquivo ZIP do WhatsApp.
        """
        conversation = None

        try:
            # ─── 1. Criar registro na DB ──────────────────────────────────
            extract_dir = str(settings.MEDIA_DIR / session_id)

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

            # ─── 2. Extrair ZIP e fazer parse ─────────────────────────────
            parser = WhatsAppParser()
            chat_file, media_files = parser.extract_zip(zip_path, extract_dir)
            parsed_messages = parser.parse_file(chat_file)

            if not parsed_messages:
                raise ValueError("Nenhuma mensagem encontrada no arquivo")

            date_start, date_end = parser.get_date_range()
            participants = parser.get_participants()
            conversation_name = self._infer_conversation_name(original_filename, participants)

            # ─── 3. Salvar mensagens na DB ────────────────────────────────
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

            # Salvar mensagens em batch
            messages_db = await self._save_messages(conversation.id, parsed_messages, parser)

            # ─── 4. Processar mídias com os 20 agentes em paralelo ────────
            media_messages = [m for m in messages_db if m.media_type != MediaType.TEXT and m.media_path]

            if media_messages:
                await self._update_conversation(conversation, {
                    "progress": 0.20,
                    "progress_message": f"Iniciando {len(media_messages)} processamentos de mídia com 20 agentes paralelos...",
                })
                if progress_callback:
                    await self._notify_progress(progress_callback, conversation)

                await self._process_media_parallel(
                    conversation,
                    media_messages,
                    progress_callback=progress_callback,
                )

            # ─── 5. Análises avançadas ────────────────────────────────────
            await self._update_conversation(conversation, {
                "progress": 0.80,
                "progress_message": "Gerando análises avançadas...",
            })
            if progress_callback:
                await self._notify_progress(progress_callback, conversation)

            await self._run_advanced_analysis(conversation, parsed_messages)

            # ─── 6. Finalizar ─────────────────────────────────────────────
            await self._update_conversation(conversation, {
                "status": ProcessingStatus.COMPLETED,
                "progress": 1.0,
                "progress_message": "Processamento concluído!",
                "completed_at": datetime.utcnow(),
            })

            if progress_callback:
                await self._notify_progress(progress_callback, conversation)

            logger.info(f"✅ Conversa {conversation.id} processada com sucesso!")
            return conversation

        except Exception as e:
            logger.error(f"Erro ao processar conversa: {e}", exc_info=True)
            if conversation:
                await self._update_conversation(conversation, {
                    "status": ProcessingStatus.FAILED,
                    "progress_message": f"Erro: {str(e)}",
                })
            raise

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

        logger.info(f"✅ {len(messages_db)} mensagens salvas no banco")
        return messages_db

    async def _process_media_parallel(
        self,
        conversation: Conversation,
        media_messages: List[Message],
        progress_callback: Optional[Callable] = None,
    ):
        """
        Usa os 20 agentes para processar todas as mídias em paralelo.
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
        for job_id, result in results.items():
            if not result:
                continue

            message_id = message_job_map.get(job_id)
            if not message_id:
                continue

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

            else:
                msg.processing_status = ProcessingStatus.FAILED
                msg.error_message = result.error if result else "Job sem resultado"

        await self.db.commit()
        logger.info(f"✅ Resultados de mídia salvos para {len(results)} jobs")

    async def _run_advanced_analysis(
        self,
        conversation: Conversation,
        parsed_messages: List[ParsedMessage],
    ):
        """Executa análises avançadas em paralelo"""
        # Preparar texto da conversa
        total_messages = len(parsed_messages)
        truncated = parsed_messages[:500]  # Limitar para não estourar tokens
        if total_messages > 500:
            logger.warning(f"Fix #12: Truncando {total_messages} mensagens para 500 na análise avançada")  # Fix #12
        conv_text = self._build_conversation_text(truncated)

        # Executar em paralelo: resumo, palavras-chave, contradições, sentimento
        tasks = [
            self.claude.generate_summary(conv_text, conversation.participants),
            self.claude.extract_keywords(conv_text),
            self.claude.detect_contradictions(conv_text),
            self.claude.analyze_sentiment(conv_text[:3000]),
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            summary_result, keywords_result, contradictions_result, sentiment_result = results

            updates = {}

            if not isinstance(summary_result, Exception):
                updates["summary"] = summary_result.get("summary", "")
                key_moments = summary_result.get("key_moments", [])
                updates["key_moments"] = key_moments
            else:
                logger.error(f"Análise falhou (summary): {summary_result}")  # Fix #11

            if not isinstance(keywords_result, Exception):
                updates["keywords"] = keywords_result.get("keywords", [])
                updates["topics"] = keywords_result.get("topics", [])
                updates["word_frequency"] = keywords_result.get("word_frequency", {})
            else:
                logger.error(f"Análise falhou (keywords): {keywords_result}")  # Fix #11

            if not isinstance(contradictions_result, Exception):
                updates["contradictions"] = contradictions_result.get("contradictions", [])
            else:
                logger.error(f"Análise falhou (contradictions): {contradictions_result}")  # Fix #11

            if not isinstance(sentiment_result, Exception):
                score = sentiment_result.get("score", 0.0)
                if score >= 0.3:
                    updates["sentiment_overall"] = SentimentType.POSITIVE
                elif score <= -0.3:
                    updates["sentiment_overall"] = SentimentType.NEGATIVE
                else:
                    updates["sentiment_overall"] = SentimentType.NEUTRAL
                updates["sentiment_score"] = score
            else:
                logger.error(f"Análise falhou (sentiment): {sentiment_result}")  # Fix #11

            await self._update_conversation(conversation, updates)

        except Exception as e:
            logger.error(f"Erro nas análises avançadas: {e}", exc_info=True)

    def _build_conversation_text(self, messages: List[ParsedMessage]) -> str:
        """Constrói texto formatado da conversa para análise"""
        lines = []
        for msg in messages:
            ts = msg.timestamp.strftime("%d/%m/%Y %H:%M")
            if msg.media_type == "text":
                lines.append(f"[{ts}] {msg.sender}: {msg.text}")
            else:
                lines.append(f"[{ts}] {msg.sender}: [mídia: {msg.media_type}]")
        return "\n".join(lines)

    def _infer_conversation_name(self, filename: str, participants: List[str]) -> str:
        """Infere o nome da conversa"""
        # Remover extensão e prefixos comuns
        name = filename.replace(".zip", "").replace("WhatsApp Chat with ", "").replace("WhatsApp Chat - ", "")
        if name and not name.startswith("WhatsApp"):
            return name.strip()
        if participants:
            return " & ".join(participants[:3])
        return "Conversa"

    async def _update_conversation(self, conversation: Conversation, updates: Dict[str, Any]):
        """Atualiza campos da conversa no banco"""
        for key, value in updates.items():
            setattr(conversation, key, value)
        conversation.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(conversation)
