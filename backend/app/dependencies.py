"""
Dependency Injection - instâncias singleton dos serviços
"""
import asyncio
from typing import Optional
from app.services.claude_service import ClaudeService
from app.services.agent_orchestrator import AgentOrchestrator

# Singletons globais
_claude_service: Optional[ClaudeService] = None
_orchestrator: Optional[AgentOrchestrator] = None
_orchestrator_lock = asyncio.Lock()


def get_claude_service() -> ClaudeService:
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService()
    return _claude_service


def get_orchestrator_instance() -> Optional[AgentOrchestrator]:
    return _orchestrator


async def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is not None:
        return _orchestrator
    async with _orchestrator_lock:
        if _orchestrator is not None:
            return _orchestrator
        claude = get_claude_service()
        from app.config import settings
        _orchestrator = AgentOrchestrator(claude, max_agents=settings.MAX_AGENTS)
        await _orchestrator.start()
    return _orchestrator


async def shutdown_orchestrator():
    global _orchestrator
    if _orchestrator:
        await _orchestrator.stop()
        _orchestrator = None
