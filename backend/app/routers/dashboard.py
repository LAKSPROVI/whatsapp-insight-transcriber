"""
Router de dashboard de custos e uso por tenant.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import List, Dict

from app.database import get_db
from app.models import Conversation, AgentJob, ChatMessage, ProcessingStatus
from app.auth import get_current_user, UserInfo
from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class UsageStats(BaseModel):
    total_conversations: int
    total_messages: int
    total_media: int
    total_chat_messages: int
    conversations_by_status: Dict[str, int]
    total_tokens_used: int
    estimated_cost_usd: float
    active_period_days: int
    avg_messages_per_conversation: float


class CostBreakdown(BaseModel):
    period: str
    tokens_input: int
    tokens_output: int
    total_tokens: int
    estimated_cost_usd: float
    conversations_processed: int
    jobs_completed: int


class DashboardResponse(BaseModel):
    usage: UsageStats
    cost_breakdown: List[CostBreakdown]
    retention_info: Dict[str, str]


# Pricing (approx per 1M tokens)
PRICING = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-20250414": {"input": 0.25, "output": 1.25},
}
DEFAULT_PRICE = {"input": 3.0, "output": 15.0}  # Sonnet as default


@router.get("/usage", response_model=DashboardResponse)
async def get_usage_dashboard(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Retorna dashboard de uso e custos estimados do usuário.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Total conversations
    conv_stmt = select(Conversation).where(
        Conversation.owner_id == current_user.id
    )
    conv_result = await db.execute(conv_stmt)
    conversations = conv_result.scalars().all()

    total_messages = sum(c.total_messages or 0 for c in conversations)
    total_media = sum(c.total_media or 0 for c in conversations)

    # Status breakdown
    status_counts: Dict[str, int] = {}
    for c in conversations:
        status = c.status.value if c.status else "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    # Token usage from agent jobs
    jobs_stmt = select(func.sum(AgentJob.tokens_used)).where(
        AgentJob.conversation_id.in_([c.id for c in conversations]),
    )
    jobs_result = await db.execute(jobs_stmt)
    total_tokens = jobs_result.scalar() or 0

    # Chat messages count
    chat_stmt = select(func.count(ChatMessage.id)).where(
        ChatMessage.conversation_id.in_([c.id for c in conversations]),
    )
    chat_result = await db.execute(chat_stmt)
    total_chat = chat_result.scalar() or 0

    # Chat tokens
    chat_tokens_stmt = select(func.sum(ChatMessage.tokens_used)).where(
        ChatMessage.conversation_id.in_([c.id for c in conversations]),
    )
    chat_tokens_result = await db.execute(chat_tokens_stmt)
    chat_tokens = chat_tokens_result.scalar() or 0

    all_tokens = total_tokens + chat_tokens

    # Estimated cost (using blended rate)
    price = DEFAULT_PRICE
    estimated_cost = (all_tokens / 1_000_000) * ((price["input"] + price["output"]) / 2)

    # Active period
    if conversations:
        dates = [c.created_at for c in conversations if c.created_at]
        active_days = (max(dates) - min(dates)).days + 1 if len(dates) >= 2 else 1
    else:
        active_days = 0

    avg_messages = total_messages / len(conversations) if conversations else 0

    # Recent cost breakdown (last N days, grouped by week)
    cost_breakdown = []
    for week in range(min(days // 7, 12)):
        week_start = datetime.now(timezone.utc) - timedelta(weeks=week + 1)
        week_end = datetime.now(timezone.utc) - timedelta(weeks=week)

        week_convs = [c for c in conversations if c.created_at and week_start <= c.created_at <= week_end]

        week_jobs_stmt = select(func.sum(AgentJob.tokens_used), func.count(AgentJob.id)).where(
            AgentJob.conversation_id.in_([c.id for c in week_convs]),
        )
        week_result = await db.execute(week_jobs_stmt)
        row = week_result.one_or_none()
        week_tokens = (row[0] or 0) if row else 0
        week_jobs_count = (row[1] or 0) if row else 0
        week_cost = (week_tokens / 1_000_000) * ((price["input"] + price["output"]) / 2)

        cost_breakdown.append(CostBreakdown(
            period=f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}",
            tokens_input=int(week_tokens * 0.7),  # Estimate 70% input
            tokens_output=int(week_tokens * 0.3),
            total_tokens=week_tokens,
            estimated_cost_usd=round(week_cost, 4),
            conversations_processed=len(week_convs),
            jobs_completed=week_jobs_count,
        ))

    return DashboardResponse(
        usage=UsageStats(
            total_conversations=len(conversations),
            total_messages=total_messages,
            total_media=total_media,
            total_chat_messages=total_chat,
            conversations_by_status=status_counts,
            total_tokens_used=all_tokens,
            estimated_cost_usd=round(estimated_cost, 4),
            active_period_days=active_days,
            avg_messages_per_conversation=round(avg_messages, 1),
        ),
        cost_breakdown=cost_breakdown,
        retention_info={
            "retention_days": str(settings.DATA_RETENTION_DAYS),
            "auto_purge_enabled": str(settings.DATA_RETENTION_DAYS > 0),
        },
    )
