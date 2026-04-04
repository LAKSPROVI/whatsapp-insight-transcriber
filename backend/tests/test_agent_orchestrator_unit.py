"""
Testes unitários para AgentOrchestrator e AIAgent — inicialização, filas,
prioridade, timeout, retry, limpeza de resultados e ciclo de vida.
"""
import asyncio
import time
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent_orchestrator import (
    AgentOrchestrator,
    AIAgent,
    AgentJob,
    AgentResult,
    JobType,
    MAX_RETRIES,
    BACKOFF_BASE,
    BACKOFF_MULTIPLIER,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_claude():
    """Mock do ClaudeService."""
    mock = MagicMock()
    mock.transcribe_audio = AsyncMock(return_value={"transcription": "hello", "tokens_used": 50})
    mock.describe_image = AsyncMock(return_value={"description": "a photo", "tokens_used": 30})
    mock.analyze_sentiment = AsyncMock(return_value={"sentiment": "positive", "tokens_used": 10})
    mock.generate_summary = AsyncMock(return_value={"summary": "test", "tokens_used": 100})
    mock.detect_contradictions = AsyncMock(return_value={"contradictions": [], "tokens_used": 20})
    mock.extract_keywords = AsyncMock(return_value={"keywords": ["test"], "tokens_used": 15})
    mock.build_vector_store = AsyncMock(return_value={"status": "indexed", "tokens_used": 0})
    return mock


@pytest.fixture
def orchestrator(mock_claude):
    return AgentOrchestrator(mock_claude, max_agents=3)


@pytest.fixture
def agent(mock_claude):
    return AIAgent("agent-test-01", mock_claude)


# ─── Testes de inicialização ─────────────────────────────────────────────────

class TestOrchestratorInit:
    def test_creates_correct_number_of_agents(self, mock_claude):
        orch = AgentOrchestrator(mock_claude, max_agents=5)
        assert len(orch.agents) == 5

    def test_agents_have_sequential_ids(self, orchestrator):
        ids = [a.agent_id for a in orchestrator.agents]
        assert ids == ["agent-01", "agent-02", "agent-03"]

    def test_initial_state(self, orchestrator):
        assert orchestrator._running is False
        assert orchestrator.job_queue.qsize() == 0
        assert len(orchestrator.results) == 0


# ─── Testes de submissão de jobs ─────────────────────────────────────────────

class TestSubmitJob:
    @pytest.mark.asyncio
    async def test_submit_job_returns_id(self, orchestrator):
        job = AgentJob(job_type=JobType.ANALYZE_SENTIMENT, payload={"text": "hello"})
        job_id = await orchestrator.submit_job(job)
        assert job_id == job.job_id
        assert orchestrator.job_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_submit_batch(self, orchestrator):
        jobs = [
            AgentJob(job_type=JobType.ANALYZE_SENTIMENT, payload={"text": f"msg {i}"})
            for i in range(5)
        ]
        ids = await orchestrator.submit_batch(jobs)
        assert len(ids) == 5
        assert orchestrator.job_queue.qsize() == 5


# ─── Testes de prioridade ───────────────────────────────────────────────────

class TestJobPrioritization:
    @pytest.mark.asyncio
    async def test_higher_priority_dequeued_first(self, orchestrator):
        low = AgentJob(job_type=JobType.ANALYZE_SENTIMENT, payload={"text": "low"}, priority=10)
        high = AgentJob(job_type=JobType.ANALYZE_SENTIMENT, payload={"text": "high"}, priority=1)

        await orchestrator.submit_job(low)
        await orchestrator.submit_job(high)

        # Dequeue and check ordering
        _, _, first_job = await orchestrator.job_queue.get()
        _, _, second_job = await orchestrator.job_queue.get()
        assert first_job.priority == 1
        assert second_job.priority == 10


# ─── Testes de processamento concorrente ─────────────────────────────────────

class TestConcurrentProcessing:
    @pytest.mark.asyncio
    async def test_concurrent_jobs_processed(self, orchestrator, mock_claude):
        await orchestrator.start()
        try:
            jobs = [
                AgentJob(
                    job_type=JobType.ANALYZE_SENTIMENT,
                    payload={"text": f"msg {i}", "context": ""},
                    priority=5,
                )
                for i in range(5)
            ]
            job_ids = await orchestrator.submit_batch(jobs)
            results = await orchestrator.wait_for_jobs(job_ids, timeout=10.0)

            assert len(results) == 5
            successes = sum(1 for r in results.values() if r and r.success)
            assert successes == 5
        finally:
            await orchestrator.stop()


# ─── Testes de timeout de job ────────────────────────────────────────────────

class TestJobTimeout:
    @pytest.mark.asyncio
    async def test_job_timeout_returns_failure(self, agent, mock_claude):
        async def slow_func(*args, **kwargs):
            await asyncio.sleep(999)

        mock_claude.analyze_sentiment = slow_func
        job = AgentJob(
            job_type=JobType.ANALYZE_SENTIMENT,
            payload={"text": "test", "context": ""},
            max_retries=0,
        )

        with patch("app.services.agent_orchestrator.JOB_TIMEOUTS", {"analyze_sentiment": 0.1}):
            result = await agent.process(job)

        assert result.success is False
        assert "Timeout" in result.error


# ─── Testes de retry em erro transiente ──────────────────────────────────────

class TestRetryOnTransient:
    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self, agent, mock_claude):
        call_count = 0

        async def failing_then_ok(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise Exception("rate limit exceeded")
            return {"sentiment": "positive", "tokens_used": 10}

        mock_claude.analyze_sentiment = failing_then_ok
        job = AgentJob(
            job_type=JobType.ANALYZE_SENTIMENT,
            payload={"text": "test", "context": ""},
            max_retries=2,
        )

        with patch("app.services.agent_orchestrator.asyncio.sleep", new_callable=AsyncMock):
            result = await agent.process(job)

        assert result.success is True
        assert result.retries_used == 1

    def test_is_transient_error_detection(self, agent):
        assert agent._is_transient_error(Exception("rate limit exceeded"))
        assert agent._is_transient_error(Exception("connection refused"))
        assert agent._is_transient_error(Exception("503 service unavailable"))
        assert not agent._is_transient_error(Exception("invalid input"))


# ─── Testes de limpeza de resultados órfãos ──────────────────────────────────

class TestStaleResultCleanup:
    def test_cleanup_removes_old_results(self, orchestrator):
        orchestrator.results["old-job"] = AgentResult(
            job_id="old-job", agent_id="agent-01", success=True
        )
        orchestrator._results_timestamps["old-job"] = time.time() - 700  # >600s

        orchestrator._cleanup_stale_results(max_age=600.0)
        assert "old-job" not in orchestrator.results

    def test_cleanup_keeps_recent_results(self, orchestrator):
        orchestrator.results["new-job"] = AgentResult(
            job_id="new-job", agent_id="agent-01", success=True
        )
        orchestrator._results_timestamps["new-job"] = time.time()

        orchestrator._cleanup_stale_results(max_age=600.0)
        assert "new-job" in orchestrator.results


# ─── Testes de ciclo de vida start/stop ──────────────────────────────────────

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_workers(self, orchestrator):
        await orchestrator.start()
        assert orchestrator._running is True
        assert len(orchestrator._workers) == 3
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_workers(self, orchestrator):
        await orchestrator.start()
        await orchestrator.stop()
        assert orchestrator._running is False
        assert len(orchestrator._workers) == 0

    @pytest.mark.asyncio
    async def test_double_start_is_noop(self, orchestrator):
        await orchestrator.start()
        workers_count = len(orchestrator._workers)
        await orchestrator.start()  # should be a no-op
        assert len(orchestrator._workers) == workers_count
        await orchestrator.stop()


# ─── Testes de get_status ────────────────────────────────────────────────────

class TestGetStatus:
    def test_status_returns_correct_agent_counts(self, orchestrator):
        status = orchestrator.get_status()
        assert status["total_agents"] == 3
        assert status["active_agents"] == 0
        assert status["idle_agents"] == 3
        assert status["queue_size"] == 0
        assert status["total_jobs_completed"] == 0
        assert len(status["agents"]) == 3
