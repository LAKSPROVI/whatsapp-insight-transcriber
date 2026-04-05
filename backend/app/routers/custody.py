"""
API Endpoints - Cadeia de Custódia, Auditoria e Certificação.
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from sqlalchemy import select

from app.database import get_db
from app.auth import get_current_user, get_current_admin, UserInfo
from app.models import Conversation
from app.services.custody_service import CustodyChainService, CertificationService, AuditService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/custody", tags=["custody"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CustodyRecordResponse(BaseModel):
    id: str
    event_type: str
    actor_id: Optional[str] = None
    description: Optional[str] = None
    prev_hash: str
    current_hash: str
    evidence: Optional[dict] = None
    created_at: Optional[str] = None


class CustodyChainResponse(BaseModel):
    conversation_id: str
    records: List[CustodyRecordResponse]
    total: int


class ChainVerificationResponse(BaseModel):
    valid: bool
    records_checked: int
    error: Optional[str] = None
    first_hash: Optional[str] = None
    last_hash: Optional[str] = None


class CertificateResponse(BaseModel):
    certificate_id: str
    signature: str
    chain_valid: bool
    zip_hash: str
    merkle_root: str
    issued_at: str
    file_count: int
    message_count: int
    conversation_name: str


class CertificateVerificationResponse(BaseModel):
    valid: bool
    signature_valid: bool
    chain_valid: bool
    certificate_id: str
    conversation_id: Optional[str] = None
    issued_at: Optional[str] = None
    chain_records: int = 0


class AuditEventResponse(BaseModel):
    id: str
    action: str
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    prev_hash: Optional[str] = None
    event_hash: Optional[str] = None
    created_at: Optional[str] = None


class AuditEventsResponse(BaseModel):
    events: List[AuditEventResponse]
    total: int


# ─── Custody Chain Endpoints ─────────────────────────────────────────────────

@router.get("/{conversation_id}/chain", response_model=CustodyChainResponse)
async def get_custody_chain(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Retorna a cadeia de custódia completa de uma conversa."""
    conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
    if not current_user.is_admin:
        conv_stmt = conv_stmt.where(Conversation.owner_id == current_user.id)
    result = await db.execute(conv_stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")

    service = CustodyChainService(db)
    records = await service.get_chain(conversation_id)
    return CustodyChainResponse(
        conversation_id=conversation_id,
        records=[CustodyRecordResponse(**r) for r in records],
        total=len(records),
    )


@router.get("/{conversation_id}/verify", response_model=ChainVerificationResponse)
async def verify_custody_chain(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Verifica a integridade da cadeia de custódia."""
    conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
    if not current_user.is_admin:
        conv_stmt = conv_stmt.where(Conversation.owner_id == current_user.id)
    result = await db.execute(conv_stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")

    service = CustodyChainService(db)
    result = await service.verify_chain(conversation_id)

    # Log the verification event
    audit = AuditService(db)
    await audit.log_event(
        action="custody.verified",
        user_id=current_user.id,
        resource_type="conversation",
        resource_id=conversation_id,
        details={"result": result["valid"]},
    )
    await db.commit()

    return ChainVerificationResponse(**result)


# ─── Certification Endpoints ─────────────────────────────────────────────────

@router.post("/{conversation_id}/certificate", response_model=CertificateResponse)
async def generate_certificate(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Gera um certificado de integridade para uma conversa."""
    conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
    if not current_user.is_admin:
        conv_stmt = conv_stmt.where(Conversation.owner_id == current_user.id)
    result = await db.execute(conv_stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")

    service = CertificationService(db)
    try:
        result = await service.generate_certificate(
            conversation_id=conversation_id,
            issuer_id=current_user.id,
        )
        # Log audit event
        audit = AuditService(db)
        await audit.log_event(
            action="certificate.generated",
            user_id=current_user.id,
            resource_type="conversation",
            resource_id=conversation_id,
            details={"certificate_id": result["certificate_id"]},
        )
        await db.commit()
        return CertificateResponse(**result)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/certificate/{certificate_id}/verify", response_model=CertificateVerificationResponse)
async def verify_certificate(
    certificate_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Verifica um certificado de integridade (endpoint público)."""
    service = CertificationService(db)
    result = await service.verify_certificate(certificate_id)
    return CertificateVerificationResponse(**result)


# ─── Audit Endpoints ─────────────────────────────────────────────────────────

@router.get("/audit/events", response_model=AuditEventsResponse)
async def get_audit_events(
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_admin),
):
    """Lista eventos de auditoria (somente admin)."""
    service = AuditService(db)
    events = await service.get_events(
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    return AuditEventsResponse(events=[AuditEventResponse(**e) for e in events], total=len(events))


@router.get("/audit/{conversation_id}", response_model=AuditEventsResponse)
async def get_conversation_audit(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Lista eventos de auditoria de uma conversa específica."""
    conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
    if not current_user.is_admin:
        conv_stmt = conv_stmt.where(Conversation.owner_id == current_user.id)
    result = await db.execute(conv_stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")

    service = AuditService(db)
    events = await service.get_events(
        resource_type="conversation",
        resource_id=conversation_id,
        limit=limit,
        offset=offset,
    )
    return AuditEventsResponse(events=[AuditEventResponse(**e) for e in events], total=len(events))
