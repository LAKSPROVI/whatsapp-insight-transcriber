"""
Testes para o sistema de orquestração de agentes de IA.
Cobre AgentJob, AgentResult, AIAgent e AgentOrchestrator.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.agent_orchestrator import (
    AgentJob,
    AgentResult,
    AIAgent,
    AgentOrchestrator,
    JobType,
)


# ─── AgentJob dataclass ─────────────────────────────────────────────────────


class TestAgentJob:
    def test_default_values(self):
        """Default job_id é UUID e created_at é preenchido automaticamente."""
        job = AgentJob()
        assert job.job_id  # não vazio
        uuid.UUID(job.job_id)  # válido como UUID
        assert isinstance(job.created_at, datetime)
        assert job.priority == 5
        assert job.payload == {}
        assert job.job_type == JobType.ANALYZE_SENTIMENT

    def test_job_type_enum_values(self):
        """JobType possui todos os valores esperados."""
        expected = {
            "transcribe_audio",
            "describe_image",
            "transcribe_video",
            "analyze_document",
            "analyze_sentiment",
            "generate_summary",
            "detect_contradictions",
            "build_vector_store",
            "extract_keywords",
        }
        actual = {member.value for member in JobType}
        assert actual == expected

    def test_custom_fields(self):
        """Campos customizados são atribuídos corretamente."""
        job = AgentJob(
            job_id="custom-id",
            job_type=JobType.TRANSCRIBE_AUDIO,
            conversation_id="conv-123",
            message_id="msg-456",
            payload={"file_path": "/tmp/audio.opus"},
            priority=1,
        )
        assert job.job_id == "custom-id"
        assert job.job_type == JobType.TRANSCRIBE_AUDIO
        assert job.conversation_id == "conv-123"
        assert job.message_id == "msg-456"
        assert job.payload == {"file_path": "/tmp/audio.opus"}
        assert job.priority == 1


# ─── AgentResult dataclass ───────────────────────────────────────────────────


class TestAgentResult:
    def test_success_result(self):
        """Resultado de sucesso contém os campos corretos."""
        result = AgentResult(
            job_id="job-1",
            agent_id="agent-01",
            success=True,
            result={"text": "transcribed"},
            processing_time=1.5,
            tokens_used=100,
        )
        assert result.success is True
        assert result.result == {"text": "transcribed"}
        assert result.error is None
        assert result.processing_time == 1.5
        assert result.tokens_used == 100
        assert result.retries_used == 0

    def test_error_result(self):
        """Resultado de erro contém mensagem de erro e success=False."""
        result = AgentResult(
            job_id="job-2",
            agent_id="agent-02",
            success=False,
            error="Timeout",
            retries_used=2,
        )
        assert result.success is False
        assert result.error == "Timeout"
        assert result.result is None
        assert result.retries_used == 2


# ─── AIAgent ─────────────────────────────────────────────────────────────────


class TestAIAgent:
    def _make_mock_claude(self):
        mock = MagicMock()
        mock.model = "test"
        return mock

    def test_initializes_with_correct_id(self):
        """Agente é criado com o id fornecido."""
        agent = AIAgent("agent-01", self._make_mock_claude())
        assert agent.agent_id == "agent-01"

    def test_starts_not_busy(self):
        """Agente começa sem estar ocupado."""
        agent = AIAgent("agent-01", self._make_mock_claude())
        assert agent.is_busy is False
        assert agent.current_job is None

    def test_avg_processing_time_zero_no_jobs(self):
        """Tempo médio é 0 quando nenhum job foi processado."""
        agent = AIAgent("agent-01", self._make_mock_claude())
        assert agent.avg_processing_time == 0.0

    @pytest.mark.asyncio
    async def test_process_sets_and_resets_busy(self):
        """process() define is_busy=True durante execução e reseta após."""
        agent = AIAgent("agent-01", self._make_mock_claude())
        job = AgentJob(job_type=JobType.ANALYZE_SENTIMENT, payload={"text": "oi"})

        busy_during = None

        async def fake_process_inner(j):
            nonlocal busy_during
            busy_during = agent.is_busy
            return AgentResult(
                job_id=j.job_id,
                agent_id=agent.agent_id,
                success=True,
                result={"sentiment": "positive"},
            )

        agent._process_inner = fake_process_inner

        result = await agent.process(job)

        assert busy_during is True
        assert agent.is_busy is False
        assert agent.current_job is None
        assert result.success is True

    @pytest.mark.asyncio
    async def test_process_resets_busy_on_exception(self):
        """is_busy é resetado mesmo se _process_inner levantar exceção."""
        agent = AIAgent("agent-01", self._make_mock_claude())
        job = AgentJob(job_type=JobType.ANALYZE_SENTIMENT, payload={"text": "oi"})

        async def failing_inner(j):
            raise RuntimeError("boom")

        agent._process_inner = failing_inner

        with pytest.raises(RuntimeError, match="boom"):
            await agent.process(job)

        assert agent.is_busy is False
        assert agent.current_job is None


# ─── AgentOrchestrator ───────────────────────────────────────────────────────


class TestAgentOrchestrator:
    def _make_mock_claude(self):
        mock = MagicMock()
        mock.model = "test"
        return mock

    def test_initializes_correct_number_of_agents(self):
        """Orquestrador cria a quantidade correta de agentes."""
        orch = AgentOrchestrator(self._make_mock_claude(), max_agents=5)
        assert len(orch.agents) == 5
        assert orch.max_agents == 5

    def test_get_status_structure(self):
        """get_status retorna a estrutura esperada."""
        orch = AgentOrchestrator(self._make_mock_claude(), max_agents=3)
        status = orch.get_status()

        assert status["total_agents"] == 3
        assert status["active_agents"] == 0
        assert status["idle_agents"] == 3
        assert status["queue_size"] == 0
        assert status["total_jobs_completed"] == 0
        assert status["total_errors"] == 0
        assert len(status["agents"]) == 3

        agent_info = status["agents"][0]
        assert "agent_id" in agent_info
        assert "is_busy" in agent_info
        assert "jobs_completed" in agent_info
        assert "avg_processing_time" in agent_info

    @pytest.mark.asyncio
    async def test_submit_job_adds_to_queue(self):
        """submit_job coloca o job na fila e retorna o job_id."""
        orch = AgentOrchestrator(self._make_mock_claude(), max_agents=2)
        job = AgentJob(job_type=JobType.ANALYZE_SENTIMENT, payload={"text": "oi"})

        returned_id = await orch.submit_job(job)

        assert returned_id == job.job_id
        assert orch.job_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        """start() inicia workers e stop() encerra sem erros."""
        orch = AgentOrchestrator(self._make_mock_claude(), max_agents=2)
        assert orch._running is False

        await orch.start()
        assert orch._running is True
        assert len(orch._workers) == 2

        # stop() envia sentinels e aguarda workers — use timeout to avoid hang
        await asyncio.wait_for(orch.stop(), timeout=5.0)
        assert orch._running is False
        assert len(orch._workers) == 0

    @pytest.mark.asyncio
    async def test_submit_batch(self):
        """submit_batch submete múltiplos jobs e retorna todos os ids."""
        orch = AgentOrchestrator(self._make_mock_claude(), max_agents=2)
        jobs = [
            AgentJob(job_type=JobType.ANALYZE_SENTIMENT, payload={"text": "a"}),
            AgentJob(job_type=JobType.EXTRACT_KEYWORDS, payload={"conversation_text": "b"}),
        ]

        ids = await orch.submit_batch(jobs)

        assert len(ids) == 2
        assert ids[0] == jobs[0].job_id
        assert ids[1] == jobs[1].job_id
        assert orch.job_queue.qsize() == 2
