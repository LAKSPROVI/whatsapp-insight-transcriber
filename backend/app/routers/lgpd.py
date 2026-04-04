"""
Router LGPD: consentimento, política de privacidade, retenção de dados.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database import get_db
from app.models import UserConsent, User
from app.auth import get_current_user, get_current_admin, UserInfo
from app.services.data_retention import purge_expired_conversations
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/lgpd", tags=["lgpd"])

PRIVACY_POLICY_VERSION = "1.0.0"


# ── Schemas ──────────────────────────────────────────────────────────────

class ConsentRequest(BaseModel):
    consent_types: List[str] = Field(..., min_length=1)
    # Valid types: upload_processing, data_retention, ai_analysis, privacy_policy


class ConsentResponse(BaseModel):
    id: str
    consent_type: str
    granted: bool
    created_at: str


class ConsentListResponse(BaseModel):
    consents: List[ConsentResponse]
    privacy_policy_version: str
    privacy_policy_accepted: bool


class PrivacyPolicyResponse(BaseModel):
    version: str
    effective_date: str
    content: str
    sections: List[dict]


class DataExportResponse(BaseModel):
    user_id: str
    username: str
    conversations_count: int
    messages_count: int
    consents: List[dict]
    export_date: str


class RetentionPurgeResponse(BaseModel):
    purged: int
    retention_days: int
    cutoff_date: str
    errors: int


# ── Política de Privacidade ──────────────────────────────────────────

@router.get("/privacy-policy", response_model=PrivacyPolicyResponse)
async def get_privacy_policy():
    """
    Retorna a política de privacidade atual.
    Não requer autenticação.
    """
    return PrivacyPolicyResponse(
        version=PRIVACY_POLICY_VERSION,
        effective_date="2026-04-04",
        content="""
POLÍTICA DE PRIVACIDADE - WhatsApp Insight Transcriber

Esta política descreve como coletamos, usamos, armazenamos e protegemos seus dados pessoais
em conformidade com a Lei Geral de Proteção de Dados (LGPD - Lei 13.709/2018).

1. CONTROLADOR DOS DADOS
O controlador responsável pelo tratamento dos seus dados pessoais é o operador da
plataforma WhatsApp Insight Transcriber.

2. DADOS COLETADOS
- Dados de cadastro: nome de usuário, senha (armazenada com hash criptográfico)
- Conversas do WhatsApp: textos, áudios, imagens e vídeos enviados para análise
- Dados de uso: logs de acesso, endereço IP, agente do navegador
- Dados gerados pela IA: transcrições, análises de sentimento, resumos

3. FINALIDADE DO TRATAMENTO
Os dados são tratados para:
- Transcrever e analisar conversas do WhatsApp
- Gerar insights e relatórios analíticos
- Manter a segurança e integridade da plataforma

4. BASE LEGAL
O tratamento é baseado no consentimento explícito do usuário (Art. 7°, I, LGPD).

5. TRANSFERÊNCIA INTERNACIONAL
Textos são enviados à API Anthropic (EUA) para processamento por IA.
Dados pessoais identificáveis (PII) são redactados antes do envio.

6. RETENÇÃO DE DADOS
Conversas são retidas por no máximo 90 dias após o upload, sendo
automaticamente excluídas após este período.

7. DIREITOS DO TITULAR
Você tem direito a:
- Acessar seus dados pessoais
- Corrigir dados incompletos ou inexatos
- Solicitar exclusão dos seus dados
- Revogar consentimento a qualquer momento
- Solicitar portabilidade dos dados
- Obter informações sobre compartilhamento

8. SEGURANÇA
Adotamos medidas técnicas e organizacionais:
- Comunicação criptografada (TLS/HTTPS)
- Autenticação JWT com tokens de curta duração
- Controle de acesso baseado em papéis (RBAC)
- Cadeia de custódia com hash criptográfico
- Redacão de PII em logs e antes de envio a terceiros
- Backups automatizados com criptografia

9. CONTATO DO DPO
Para exercer seus direitos ou esclarecer dúvidas sobre o tratamento de dados,
entre em contato pelo email: dpo@whatsapp-insight.com
""",
        sections=[
            {"id": "controller", "title": "Controlador dos Dados"},
            {"id": "data_collected", "title": "Dados Coletados"},
            {"id": "purpose", "title": "Finalidade do Tratamento"},
            {"id": "legal_basis", "title": "Base Legal"},
            {"id": "international_transfer", "title": "Transferência Internacional"},
            {"id": "retention", "title": "Retenção de Dados"},
            {"id": "rights", "title": "Direitos do Titular"},
            {"id": "security", "title": "Segurança"},
            {"id": "dpo", "title": "Contato do DPO"},
        ]
    )


# ── Consentimento ──────────────────────────────────────────────────

@router.post("/consent", response_model=List[ConsentResponse])
async def grant_consent(
    body: ConsentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Registra consentimento do usuário para os tipos especificados.
    Tipos válidos: upload_processing, data_retention, ai_analysis, privacy_policy
    """
    valid_types = {"upload_processing", "data_retention", "ai_analysis", "privacy_policy"}
    for ct in body.consent_types:
        if ct not in valid_types:
            raise HTTPException(400, f"Tipo de consentimento inválido: {ct}. Válidos: {valid_types}")

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:500]
    results = []

    for consent_type in body.consent_types:
        consent = UserConsent(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            consent_type=consent_type,
            granted=True,
            ip_address=ip,
            user_agent=ua,
            consent_text=f"Consentimento para {consent_type} concedido via plataforma.",
        )
        db.add(consent)
        results.append(ConsentResponse(
            id=consent.id,
            consent_type=consent_type,
            granted=True,
            created_at=consent.created_at.isoformat() if consent.created_at else datetime.now(timezone.utc).isoformat(),
        ))

    # Se inclui privacy_policy, atualizar usuário
    if "privacy_policy" in body.consent_types:
        stmt = select(User).where(User.id == current_user.id)
        user_result = await db.execute(stmt)
        user = user_result.scalar_one_or_none()
        if user:
            user.privacy_policy_accepted_at = datetime.now(timezone.utc)
            user.privacy_policy_version = PRIVACY_POLICY_VERSION

    await db.commit()

    logger.info(
        "lgpd.consent.granted",
        user_id=current_user.id,
        consent_types=body.consent_types,
        ip_address=ip,
    )
    return results


@router.get("/consent", response_model=ConsentListResponse)
async def list_consents(
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Lista todos os consentimentos ativos do usuário."""
    stmt = select(UserConsent).where(
        UserConsent.user_id == current_user.id,
        UserConsent.revoked_at.is_(None),
    )
    result = await db.execute(stmt)
    consents = result.scalars().all()

    # Verificar aceite da política de privacidade
    user_stmt = select(User).where(User.id == current_user.id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    return ConsentListResponse(
        consents=[
            ConsentResponse(
                id=c.id,
                consent_type=c.consent_type,
                granted=c.granted,
                created_at=c.created_at.isoformat() if c.created_at else "",
            )
            for c in consents
        ],
        privacy_policy_version=PRIVACY_POLICY_VERSION,
        privacy_policy_accepted=bool(
            user and user.privacy_policy_accepted_at
            and getattr(user, 'privacy_policy_version', '') == PRIVACY_POLICY_VERSION
        ),
    )


@router.delete("/consent/{consent_type}")
async def revoke_consent(
    consent_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Revoga um consentimento específico."""
    stmt = select(UserConsent).where(
        UserConsent.user_id == current_user.id,
        UserConsent.consent_type == consent_type,
        UserConsent.revoked_at.is_(None),
    )
    result = await db.execute(stmt)
    consents = result.scalars().all()

    if not consents:
        raise HTTPException(404, "Consentimento não encontrado ou já revogado")

    now = datetime.now(timezone.utc)
    for c in consents:
        c.revoked_at = now

    await db.commit()
    logger.info("lgpd.consent.revoked", user_id=current_user.id, consent_type=consent_type)
    return {"message": f"Consentimento '{consent_type}' revogado com sucesso"}


# ── Direito à exclusão (Right to Erasure) ───────────────────────────

@router.post("/data-export")
async def export_user_data(
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Exporta todos os dados do usuário (direito à portabilidade, Art. 18-V LGPD)."""
    from app.models import Conversation, Message

    # Contar conversas e mensagens
    conv_stmt = select(Conversation).where(Conversation.owner_id == current_user.id)
    conv_result = await db.execute(conv_stmt)
    conversations = conv_result.scalars().all()

    total_messages = 0
    for conv in conversations:
        msg_stmt = select(Message).where(Message.conversation_id == conv.id)
        msg_result = await db.execute(msg_stmt)
        total_messages += len(msg_result.scalars().all())

    # Consentimentos
    consent_stmt = select(UserConsent).where(UserConsent.user_id == current_user.id)
    consent_result = await db.execute(consent_stmt)
    consents = consent_result.scalars().all()

    return DataExportResponse(
        user_id=current_user.id,
        username=current_user.username,
        conversations_count=len(conversations),
        messages_count=total_messages,
        consents=[
            {
                "type": c.consent_type,
                "granted": c.granted,
                "created_at": c.created_at.isoformat() if c.created_at else "",
                "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            }
            for c in consents
        ],
        export_date=datetime.now(timezone.utc).isoformat(),
    )


@router.delete("/my-data")
async def delete_all_user_data(
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Exclui TODOS os dados do usuário (direito à exclusão, Art. 18-VI LGPD)."""
    import os, shutil
    from app.models import Conversation

    conv_stmt = select(Conversation).where(Conversation.owner_id == current_user.id)
    conv_result = await db.execute(conv_stmt)
    conversations = conv_result.scalars().all()

    deleted_count = 0
    for conv in conversations:
        # Limpar arquivos
        if conv.extract_path and os.path.exists(conv.extract_path):
            shutil.rmtree(conv.extract_path, ignore_errors=True)
        if conv.upload_path and os.path.exists(conv.upload_path):
            try:
                os.remove(conv.upload_path)
            except OSError:
                pass
        await db.delete(conv)
        deleted_count += 1

    # Revogar todos os consentimentos
    consent_stmt = select(UserConsent).where(
        UserConsent.user_id == current_user.id,
        UserConsent.revoked_at.is_(None),
    )
    consent_result = await db.execute(consent_stmt)
    for c in consent_result.scalars().all():
        c.revoked_at = datetime.now(timezone.utc)

    await db.commit()

    logger.info(
        "lgpd.data_deleted",
        user_id=current_user.id,
        conversations_deleted=deleted_count,
    )
    return {
        "message": f"Todos os dados foram excluídos: {deleted_count} conversas removidas.",
        "conversations_deleted": deleted_count,
    }


# ── Admin: Data Retention Purge ───────────────────────────────────

@router.post("/admin/purge", response_model=RetentionPurgeResponse)
async def admin_purge_expired(
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_admin),
):
    """(Admin) Executa purga manual de conversas expiradas."""
    result = await purge_expired_conversations(db)
    return RetentionPurgeResponse(**result)
