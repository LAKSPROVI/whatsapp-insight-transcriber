"""
Sistema de Agentes de IA - Orquestrador e Workers
20 agentes paralelos para processamento ultrarrápido.
Inclui timeout configurável, retry com exponential backoff e log detalhado.
"""
import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from app.exceptions import ProcessingError, APIError
from app.logging import get_logger, new_span
from app.logging.error_advisor import get_error_suggestion

logger = get_logger(__name__)

# ─── Timeouts configuráveis por tipo de job (segundos) ────────────────────────
JOB_TIMEOUTS: Dict[str, float] = {
    "transcribe_audio": 120.0,
    "describe_image": 90.0,
    "transcribe_video": 300.0,
    "analyze_document": 120.0,
    "analyze_sentiment": 60.0,
    "generate_summary": 120.0,
    "detect_contradictions": 120.0,
    "build_vector_store": 60.0,
    "extract_keywords": 90.0,
}

DEFAULT_JOB_TIMEOUT = 120.0

# Configuração de retry
MAX_RETRIES = 2
BACKOFF_BASE = 1.0  # segundos
BACKOFF_MULTIPLIER = 2.0


class JobType(str, Enum):
    TRANSCRIBE_AUDIO = "transcribe_audio"
    DESCRIBE_IMAGE = "describe_image"
    TRANSCRIBE_VIDEO = "transcribe_video"
    ANALYZE_DOCUMENT = "analyze_document"
    ANALYZE_SENTIMENT = "analyze_sentiment"
    GENERATE_SUMMARY = "generate_summary"
    DETECT_CONTRADICTIONS = "detect_contradictions"
    BUILD_VECTOR_STORE = "build_vector_store"
    EXTRACT_KEYWORDS = "extract_keywords"


@dataclass
class AgentJob:
    """Representa um job para ser processado por um agente"""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_type: JobType = JobType.ANALYZE_SENTIMENT
    conversation_id: str = ""
    message_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1=crítico, 10=baixo
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    callback: Optional[Callable] = None
    max_retries: int = MAX_RETRIES


@dataclass
class AgentResult:
    """Resultado do processamento de um agente"""
    job_id: str
    agent_id: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    tokens_used: int = 0
    retries_used: int = 0


class AIAgent:
    """
    Agente de IA individual.
    Cada agente mantém seu próprio contexto e pode processar
    jobs de forma independente e assíncrona com timeout e retry.
    """

    def __init__(self, agent_id: str, claude_service):
        self.agent_id = agent_id
        self.claude_service = claude_service
        self.is_busy = False
        self.current_job: Optional[AgentJob] = None
        self.jobs_completed = 0
        self.total_processing_time = 0.0
        self.errors = 0

    @property
    def avg_processing_time(self) -> float:
        if self.jobs_completed == 0:
            return 0.0
        return self.total_processing_time / self.jobs_completed

    async def process(self, job: AgentJob) -> AgentResult:
        """Processa um job com timeout e retry automático."""
        self.is_busy = True
        self.current_job = job
        try:
            with new_span(f"agent.process.{job.job_type.value}"):
                return await self._process_inner(job)
        finally:
            self.is_busy = False
            self.current_job = None

    async def _process_inner(self, job: AgentJob) -> AgentResult:
        """Lógica interna de processamento com retry."""
        start_time = time.time()
        timeout = JOB_TIMEOUTS.get(job.job_type.value, DEFAULT_JOB_TIMEOUT)
        retries_used = 0

        logger.info(
            "agent_job_started",
            event="agent.job.started",
            agent_id=self.agent_id,
            job_id=job.job_id,
            job_type=job.job_type.value,
            timeout=timeout,
        )

        last_error = None

        for attempt in range(job.max_retries + 1):
            try:
                # Executar com timeout
                result = await asyncio.wait_for(
                    self._execute_job(job),
                    timeout=timeout,
                )

                processing_time = time.time() - start_time
                self.jobs_completed += 1
                self.total_processing_time += processing_time

                logger.info(
                    "agent_job_completed",
                    event="agent.job.completed",
                    agent_id=self.agent_id,
                    job_id=job.job_id,
                    job_type=job.job_type.value,
                    duration_ms=round(processing_time * 1000, 2),
                    retries=retries_used,
                    tokens_used=result.get("tokens_used", 0) if result else 0,
                )

                return AgentResult(
                    job_id=job.job_id,
                    agent_id=self.agent_id,
                    success=True,
                    result=result,
                    processing_time=processing_time,
                    tokens_used=result.get("tokens_used", 0) if result else 0,
                    retries_used=retries_used,
                )

            except asyncio.TimeoutError:
                last_error = f"Timeout ({timeout}s) no job {job.job_type.value}"
                logger.warning(
                    f"[{self.agent_id}] Timeout no job {job.job_id[:8]}... (tentativa {attempt + 1}/{job.max_retries + 1})",
                    extra={"agent_id": self.agent_id, "job_id": job.job_id, "attempt": attempt + 1},
                )

            except Exception as e:
                last_error = str(e)
                # Verificar se é erro transiente (rate limit, conexão, etc.)
                is_transient = self._is_transient_error(e)

                if is_transient and attempt < job.max_retries:
                    retries_used += 1
                    backoff = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(
                        f"[{self.agent_id}] Erro transiente no job {job.job_id[:8]}... "
                        f"(tentativa {attempt + 1}/{job.max_retries + 1}), retry em {backoff:.1f}s: {e}",
                        extra={
                            "agent_id": self.agent_id,
                            "job_id": job.job_id,
                            "attempt": attempt + 1,
                            "backoff": backoff,
                        },
                    )
                    await asyncio.sleep(backoff)
                    continue
                else:
                    # Erro não-transiente ou último retry
                    break

            # Backoff para timeout retry
            if attempt < job.max_retries:
                retries_used += 1
                backoff = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
                await asyncio.sleep(backoff)

        # Todas as tentativas falharam
        processing_time = time.time() - start_time
        self.errors += 1

        logger.error(
            "agent_job_failed",
            event="agent.job.failed",
            agent_id=self.agent_id,
            job_id=job.job_id,
            job_type=job.job_type.value,
            duration_ms=round(processing_time * 1000, 2),
            retries=retries_used,
            error=last_error,
            **get_error_suggestion(exc=Exception(last_error) if last_error else Exception("unknown")),
        )

        return AgentResult(
            job_id=job.job_id,
            agent_id=self.agent_id,
            success=False,
            error=last_error,
            processing_time=processing_time,
            retries_used=retries_used,
        )

    def _is_transient_error(self, error: Exception) -> bool:
        """Determina se um erro é transiente e vale a pena fazer retry."""
        error_str = str(error).lower()
        transient_indicators = [
            "rate limit", "429", "timeout", "timed out",
            "connection", "connect", "temporary", "unavailable",
            "503", "502", "500", "overloaded", "capacity",
            "too many requests", "retry",
        ]
        return any(indicator in error_str for indicator in transient_indicators)

    async def _execute_job(self, job: AgentJob) -> Dict[str, Any]:
        """Executa o job baseado no tipo"""
        payload = job.payload

        if job.job_type == JobType.TRANSCRIBE_AUDIO:
            return await self.claude_service.transcribe_audio(
                file_path=payload["file_path"],
                media_metadata=payload.get("metadata", {})
            )

        elif job.job_type == JobType.DESCRIBE_IMAGE:
            return await self.claude_service.describe_image(
                file_path=payload["file_path"],
                media_metadata=payload.get("metadata", {})
            )

        elif job.job_type == JobType.TRANSCRIBE_VIDEO:
            return await self.claude_service.transcribe_video(
                file_path=payload["file_path"],
                media_metadata=payload.get("metadata", {})
            )

        elif job.job_type == JobType.ANALYZE_SENTIMENT:
            return await self.claude_service.analyze_sentiment(
                text=payload["text"],
                context=payload.get("context", "")
            )

        elif job.job_type == JobType.GENERATE_SUMMARY:
            return await self.claude_service.generate_summary(
                conversation_text=payload["conversation_text"],
                participants=payload.get("participants", [])
            )

        elif job.job_type == JobType.DETECT_CONTRADICTIONS:
            return await self.claude_service.detect_contradictions(
                conversation_text=payload["conversation_text"]
            )

        elif job.job_type == JobType.EXTRACT_KEYWORDS:
            return await self.claude_service.extract_keywords(
                conversation_text=payload["conversation_text"]
            )

        elif job.job_type == JobType.BUILD_VECTOR_STORE:
            return await self.claude_service.build_vector_store(
                conversation_id=payload["conversation_id"],
                messages=payload["messages"]
            )

        else:
            raise ValueError(f"Tipo de job desconhecido: {job.job_type}")


class AgentOrchestrator:
    """
    Orquestrador central que gerencia agentes de IA em paralelo.
    Implementa sistema de filas com prioridade, load balancing e error reporting.
    """

    def __init__(self, claude_service, max_agents: int = 20):
        self.max_agents = max_agents
        self.claude_service = claude_service
        self.agents: List[AIAgent] = []
        self.job_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.results: Dict[str, Optional[AgentResult]] = {}
        self._results_timestamps: Dict[str, float] = {}  # TTL para limpeza
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._progress_callbacks: Dict[str, List[Callable]] = {}
        self._job_counter = 0

        # Inicializar agentes
        self._initialize_agents()

        logger.info(f"Orquestrador inicializado com {max_agents} agentes")

    def _initialize_agents(self):
        """Cria todos os agentes"""
        self.agents = [
            AIAgent(f"agent-{i+1:02d}", self.claude_service)
            for i in range(self.max_agents)
        ]

    async def start(self):
        """Inicia todos os workers dos agentes"""
        if self._running:
            return

        self._running = True
        self._workers = [
            asyncio.create_task(self._worker_loop(agent))
            for agent in self.agents
        ]
        logger.info(f"{len(self._workers)} agentes iniciados e aguardando jobs")

    async def stop(self):
        """Para todos os agentes graciosamente"""
        self._running = False
        for _ in self.agents:
            self._job_counter += 1
            await self.job_queue.put((0, self._job_counter, None))  # Sentinel

        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers = []

        logger.info("Orquestrador parado")

    async def submit_job(self, job: AgentJob) -> str:
        """Submete um job para processamento."""
        self._job_counter += 1
        await self.job_queue.put((job.priority, self._job_counter, job))
        logger.debug(f"Job {job.job_id[:8]}... ({job.job_type}) adicionado à fila (prioridade: {job.priority})")
        return job.job_id

    async def submit_batch(self, jobs: List[AgentJob]) -> List[str]:
        """Submete múltiplos jobs de uma vez"""
        job_ids = []
        for job in jobs:
            job_id = await self.submit_job(job)
            job_ids.append(job_id)
        return job_ids

    async def wait_for_jobs(
        self,
        job_ids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: float = 600.0
    ) -> Dict[str, Optional[AgentResult]]:
        """
        Aguarda a conclusão de um conjunto de jobs.
        Retorna os resultados quando todos estiverem completos (ou timeout).
        """
        start_time = time.time()
        completed = set()
        total = len(job_ids)
        last_count = 0

        while len(completed) < total:
            if time.time() - start_time > timeout:
                timed_out = [jid for jid in job_ids if jid not in completed]
                logger.warning(
                    f"Timeout aguardando {len(timed_out)} jobs",
                    extra={"timed_out_jobs": len(timed_out), "total": total},
                )
                # Criar resultados de timeout para jobs pendentes
                for jid in timed_out:
                    if jid not in self.results:
                        self.results[jid] = AgentResult(
                            job_id=jid,
                            agent_id="timeout",
                            success=False,
                            error=f"Timeout global ({timeout}s) excedido",
                        )
                break

            for job_id in job_ids:
                if job_id not in completed and job_id in self.results:
                    completed.add(job_id)

            if progress_callback and len(completed) > 0 and len(completed) != last_count:
                last_count = len(completed)
                await progress_callback(len(completed), total)

            if len(completed) < total:
                await asyncio.sleep(0.5)

        # Coletar e limpar resultados
        collected = {jid: self.results.get(jid) for jid in job_ids if jid in self.results}
        for jid in job_ids:
            self.results.pop(jid, None)
            self._results_timestamps.pop(jid, None)
        return collected

    async def _worker_loop(self, agent: AIAgent):
        """Loop principal de um worker/agente"""
        while self._running:
            try:
                try:
                    priority, _counter, job = await asyncio.wait_for(
                        self.job_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Sentinel para parar
                if job is None:
                    self.job_queue.task_done()
                    break

                # Processar o job
                result = await agent.process(job)
                self.results[job.job_id] = result
                self._results_timestamps[job.job_id] = time.time()

                # Limpeza periódica de resultados órfãos (>10 min)
                self._cleanup_stale_results()

                # Executar callback se existir
                if job.callback:
                    try:
                        if asyncio.iscoroutinefunction(job.callback):
                            await job.callback(result)
                        else:
                            job.callback(result)
                    except Exception as e:
                        logger.error(f"Erro no callback do job {job.job_id[:8]}...: {e}")

                self.job_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{agent.agent_id}] Erro no worker loop: {e}", exc_info=True)

    def _cleanup_stale_results(self, max_age: float = 600.0) -> None:
        """Remove resultados órfãos com mais de max_age segundos."""
        now = time.time()
        stale = [
            jid for jid, ts in self._results_timestamps.items()
            if now - ts > max_age
        ]
        for jid in stale:
            self.results.pop(jid, None)
            self._results_timestamps.pop(jid, None)
        if stale:
            logger.debug(f"Limpeza: {len(stale)} resultados órfãos removidos")

    def get_status(self) -> Dict[str, Any]:
        """Retorna o status atual de todos os agentes"""
        active = sum(1 for a in self.agents if a.is_busy)
        total_completed = sum(a.jobs_completed for a in self.agents)
        total_errors = sum(a.errors for a in self.agents)

        return {
            "total_agents": len(self.agents),
            "active_agents": active,
            "idle_agents": len(self.agents) - active,
            "queue_size": self.job_queue.qsize(),
            "total_jobs_completed": total_completed,
            "total_errors": total_errors,
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "is_busy": a.is_busy,
                    "current_job": a.current_job.job_type.value if a.current_job else None,
                    "jobs_completed": a.jobs_completed,
                    "avg_processing_time": round(a.avg_processing_time, 2),
                    "errors": a.errors,
                }
                for a in self.agents
            ],
        }

    async def process_conversation_media(
        self,
        conversation_id: str,
        media_jobs: List[AgentJob],
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Optional[AgentResult]]:
        """
        Processa todos os arquivos de mídia de uma conversa usando
        todos os agentes em paralelo.
        """
        logger.info(f"Iniciando processamento paralelo de {len(media_jobs)} mídias para {conversation_id}")

        job_ids = await self.submit_batch(media_jobs)

        results = await self.wait_for_jobs(
            job_ids,
            progress_callback=progress_callback,
            timeout=600.0,
        )

        successes = sum(1 for r in results.values() if r and r.success)
        failures = len(results) - successes
        logger.info(f"Processamento concluído: {successes} sucessos, {failures} falhas")

        return results
