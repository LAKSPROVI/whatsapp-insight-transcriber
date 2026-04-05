"""
Serviço de retenção de dados (auto-purge LGPD).
Executa purga automática de conversas expiradas baseado em DATA_RETENTION_DAYS.
"""
import os
import shutil
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Conversation, ProcessingStatus
from app.logging import get_logger

logger = get_logger(__name__)


async def purge_expired_conversations(db: AsyncSession) -> dict:
    """
    Remove conversas cuja retenção expirou.
    
    Usa dois critérios:
    1. retention_expires_at < now (se definido)
    2. created_at + DATA_RETENTION_DAYS < now (fallback)
    
    Returns:
        Dict com estatisticas da purge
    """
    if settings.DATA_RETENTION_DAYS <= 0:
        logger.info("data_retention.disabled", reason="DATA_RETENTION_DAYS=0")
        return {"purged": 0, "reason": "disabled"}
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.DATA_RETENTION_DAYS)
    
    # Buscar conversas expiradas
    # Criterio 1: retention_expires_at definido e expirado
    # Criterio 2: created_at + DATA_RETENTION_DAYS (fallback)
    from sqlalchemy import or_
    stmt = select(Conversation).where(
        or_(
            Conversation.retention_expires_at < now,
            Conversation.created_at < cutoff,
        ),
        Conversation.status != ProcessingStatus.PROCESSING,  # N\u00e3o purgar em processamento
    )
    
    result = await db.execute(stmt)
    expired = result.scalars().all()
    
    purged_count = 0
    errors = []
    
    for conv in expired:
        # Store file paths before DB deletion
        extract_path = conv.extract_path
        upload_path = conv.upload_path
        conv_id = conv.id
        conv_session_id = conv.session_id
        conv_created_at = conv.created_at

        try:
            # 1. Delete from DB first and commit
            await db.delete(conv)
            await db.commit()
            purged_count += 1

            # 2. Then delete files on disk (after successful DB commit)
            if extract_path and os.path.exists(extract_path):
                shutil.rmtree(extract_path, ignore_errors=True)
            if upload_path and os.path.exists(upload_path):
                try:
                    os.remove(upload_path)
                except OSError:
                    pass
            
            logger.info(
                "data_retention.conversation_purged",
                conversation_id=conv_id,
                session_id=conv_session_id,
                created_at=conv_created_at.isoformat() if conv_created_at else None,
                age_days=(now - conv_created_at).days if conv_created_at else None,
            )
            
        except Exception as e:
            await db.rollback()
            errors.append({"conversation_id": conv_id, "error": str(e)})
            logger.error(
                "data_retention.purge_error",
                conversation_id=conv_id,
                error=str(e),
            )
    
    result_info = {
        "purged": purged_count,
        "retention_days": settings.DATA_RETENTION_DAYS,
        "cutoff_date": cutoff.isoformat(),
        "errors": len(errors),
    }
    
    logger.info("data_retention.purge_completed", **result_info)
    return result_info


async def set_retention_expiry(db: AsyncSession, conversation_id: str, days: int = None):
    """
    Define a data de expiração de retenção para uma conversa específica.
    """
    retention_days = days or settings.DATA_RETENTION_DAYS
    if retention_days <= 0:
        return
    
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    
    if conv:
        conv.retention_expires_at = datetime.now(timezone.utc) + timedelta(days=retention_days)
        await db.commit()
