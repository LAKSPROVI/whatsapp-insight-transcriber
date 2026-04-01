"""
Sistema de Agentes de IA - Orquestrador e Workers
20 agentes paralelos para processamento ultrarrápido
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Callable, Awaitable, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


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
    created_at: datetime = field(default_factory=datetime.utcnow)
    callback: Optional[Callable] = None


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


class AIAgent:
    """
    Agente de IA individual.
    Cada agente mantém seu próprio contexto e pode processar
    jobs de forma independente e assíncrona.
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
        """Processa um job e retorna o resultado"""
        self.is_busy = True
        self.current_job = job
        start_time = time.time()

        logger.debug(f"[{self.agent_id}] Iniciando job {job.job_id} ({job.job_type})")

        try:
            result = await self._execute_job(job)
            processing_time = time.time() - start_time
            self.jobs_completed += 1
            self.total_processing_time += processing_time

            logger.debug(f"[{self.agent_id}] Job {job.job_id} concluído em {processing_time:.2f}s")

            return AgentResult(
                job_id=job.job_id,
                agent_id=self.agent_id,
                success=True,
                result=result,
                processing_time=processing_time,
                tokens_used=result.get("tokens_used", 0) if result else 0,
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self.errors += 1
            logger.error(f"[{self.agent_id}] Erro no job {job.job_id}: {e}", exc_info=True)

            return AgentResult(
                job_id=job.job_id,
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                processing_time=processing_time,
            )

        finally:
            self.is_busy = False
            self.current_job = None

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
    Orquestrador central que gerencia 20 agentes de IA em paralelo.
    Implementa um sistema de filas com prioridade e load balancing.
    """

    def __init__(self, claude_service, max_agents: int = 20):
        self.max_agents = max_agents
        self.claude_service = claude_service
        self.agents: List[AIAgent] = []
        self.job_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.results: Dict[str, AgentResult] = {}
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._progress_callbacks: Dict[str, List[Callable]] = {}
        self._job_counter = 0  # Fix #1: contador para desempate no PriorityQueue

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
        logger.info(f"✅ {len(self._workers)} agentes iniciados e aguardando jobs")

    async def stop(self):
        """Para todos os agentes graciosamente"""
        self._running = False
        # Sinalizar fim para todos os workers
        for _ in self.agents:
            self._job_counter += 1
            await self.job_queue.put((0, self._job_counter, None))  # Sentinel

        # Aguardar conclusão
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers = []

        logger.info("Orquestrador parado")

    async def submit_job(self, job: AgentJob) -> str:
        """
        Submete um job para processamento.
        Retorna o job_id para rastreamento.
        """
        # PriorityQueue: menor número = maior prioridade
        self._job_counter += 1
        await self.job_queue.put((job.priority, self._job_counter, job))
        logger.debug(f"Job {job.job_id} ({job.job_type}) adicionado à fila (prioridade: {job.priority})")
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
    ) -> Dict[str, AgentResult]:
        """
        Aguarda a conclusão de um conjunto de jobs.
        Retorna os resultados quando todos estiverem completos.
        """
        start_time = time.time()
        completed = set()
        total = len(job_ids)
        last_count = 0  # Fix #3: evitar callbacks repetidos

        while len(completed) < total:
            if time.time() - start_time > timeout:
                logger.warning(f"Timeout aguardando {total - len(completed)} jobs")
                break

            for job_id in job_ids:
                if job_id not in completed and job_id in self.results:
                    completed.add(job_id)

            # Fix #3: só chamar callback quando count muda
            if progress_callback and len(completed) > 0 and len(completed) != last_count:
                last_count = len(completed)
                await progress_callback(len(completed), total)

            if len(completed) < total:
                await asyncio.sleep(0.5)  # Fix #3: polling menos agressivo

        # Fix #2: limpar resultados para evitar memory leak
        collected = {jid: self.results.get(jid) for jid in job_ids if jid in self.results}
        for jid in job_ids:
            self.results.pop(jid, None)
        return collected

    async def _worker_loop(self, agent: AIAgent):
        """Loop principal de um worker/agente"""
        while self._running:
            try:
                # Aguardar próximo job com timeout
                try:
                    priority, _counter, job = await asyncio.wait_for(
                        self.job_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Sentinel para parar
                if job is None:
                    self.job_queue.task_done()  # Fix #4: task_done para sentinel
                    break

                # Processar o job
                result = await agent.process(job)
                self.results[job.job_id] = result

                # Executar callback se existir
                if job.callback:
                    try:
                        await job.callback(result)
                    except Exception as e:
                        logger.error(f"Erro no callback do job {job.job_id}: {e}")

                self.job_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{agent.agent_id}] Erro no worker loop: {e}", exc_info=True)

    def get_status(self) -> Dict[str, Any]:
        """Retorna o status atual de todos os agentes"""
        active = sum(1 for a in self.agents if a.is_busy)
        return {
            "total_agents": len(self.agents),
            "active_agents": active,
            "idle_agents": len(self.agents) - active,
            "queue_size": self.job_queue.qsize(),
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "is_busy": a.is_busy,
                    "current_job": a.current_job.job_type if a.current_job else None,
                    "jobs_completed": a.jobs_completed,
                    "avg_processing_time": round(a.avg_processing_time, 2),
                    "errors": a.errors,
                }
                for a in self.agents
            ]
        }

    async def process_conversation_media(
        self,
        conversation_id: str,
        media_jobs: List[AgentJob],
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, AgentResult]:
        """
        Processa todos os arquivos de mídia de uma conversa usando
        todos os 20 agentes em paralelo.
        """
        logger.info(f"Iniciando processamento paralelo de {len(media_jobs)} mídias para {conversation_id}")

        # Submeter todos os jobs de uma vez
        job_ids = await self.submit_batch(media_jobs)

        # Aguardar com callback de progresso
        results = await self.wait_for_jobs(
            job_ids,
            progress_callback=progress_callback,
            timeout=600.0  # 10 minutos máximo
        )

        successes = sum(1 for r in results.values() if r and r.success)
        failures = len(results) - successes
        logger.info(f"Processamento concluído: {successes} sucessos, {failures} falhas")

        return results
