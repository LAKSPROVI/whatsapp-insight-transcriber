"""
Modelos SQLAlchemy para o banco de dados
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    String, Text, DateTime, Float, Integer, Boolean,
    ForeignKey, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    PARSING = "parsing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MediaType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    STICKER = "sticker"
    CONTACT = "contact"
    LOCATION = "location"
    DELETED = "deleted"


class SentimentType(str, enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class UserRole(str, enum.Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    AUDITOR = "auditor"
    ADMIN = "admin"


class Conversation(Base):
    """Representa uma conversa completa do WhatsApp"""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    upload_path: Mapped[str] = mapped_column(String(512))
    extract_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[ProcessingStatus] = mapped_column(
        SQLEnum(ProcessingStatus),
        default=ProcessingStatus.PENDING
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    progress_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadados da conversa
    conversation_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    participants: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_media: Mapped[int] = mapped_column(Integer, default=0)
    date_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    date_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Análises
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment_overall: Mapped[Optional[SentimentType]] = mapped_column(
        SQLEnum(SentimentType), nullable=True
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    keywords: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    topics: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    word_frequency: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    key_moments: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    contradictions: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)

    # RAG vector store path
    vector_store_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Multi-tenancy: dono da conversa
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )

    # LGPD fields
    consent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    retention_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pii_redacted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relacionamentos
    owner: Mapped[Optional["User"]] = relationship(
        "User", back_populates="conversations"
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.timestamp"
    )
    chat_history: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="conversation", cascade="all, delete-orphan"
    )
    agent_jobs: Mapped[List["AgentJob"]] = relationship(
        "AgentJob", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """Representa uma mensagem individual na conversa"""
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"))
    sequence_number: Mapped[int] = mapped_column(Integer, index=True)

    # Dados originais
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sender: Mapped[str] = mapped_column(String(255))
    original_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_type: Mapped[MediaType] = mapped_column(SQLEnum(MediaType), default=MediaType.TEXT)

    # Arquivo de mídia
    media_filename: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    media_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    media_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Metadados da mídia
    media_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # { file_size, duration, resolution, format, bitrate, fps, etc. }

    # Resultado da IA
    transcription: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Análise por mensagem
    sentiment: Mapped[Optional[SentimentType]] = mapped_column(SQLEnum(SentimentType), nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_key_moment: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status de processamento
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING
    )
    agent_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    processing_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # segundos
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class ChatMessage(Base):
    """Mensagens do chat RAG interno"""
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(20))  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="chat_history")


class AgentJob(Base):
    """Registro de jobs processados pelos agentes"""
    __tablename__ = "agent_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"))
    agent_id: Mapped[str] = mapped_column(String(50))
    message_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50))  # transcribe_audio, describe_image, etc.
    status: Mapped[ProcessingStatus] = mapped_column(SQLEnum(ProcessingStatus))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="agent_jobs")


class AuditLog(Base):
    """Trilha de auditoria para ações críticas do sistema."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    prev_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    user: Mapped[Optional["User"]] = relationship("User")


class User(Base):
    """Modelo de usuário para autenticação persistente"""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole), default=UserRole.ANALYST
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    privacy_policy_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    privacy_policy_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="owner"
    )


class CustodyChainRecord(Base):
    """Registro de cadeia de custódia - encadeado por hash (blockchain-like)."""
    __tablename__ = "custody_chain"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class IntegrityCertificate(Base):
    """Certificado de integridade para conversas importadas."""
    __tablename__ = "integrity_certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), index=True)
    cert_type: Mapped[str] = mapped_column(String(50), default="INTEGRITY")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    issuer_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    zip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    merkle_root: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_manifest: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    chain_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    signature: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    algorithm: Mapped[str] = mapped_column(String(20), default="SHA-256")
    cert_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON


class Tag(Base):
    """Tags personalizaveis para organizar mensagens."""
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#6C63FF")
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MessageTag(Base):
    """Tabela de juncao entre mensagens e tags."""
    __tablename__ = "message_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(String(36), ForeignKey("messages.id"), index=True)
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id"), index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class UserConsent(Base):
    """Registro de consentimento LGPD do usuario."""
    __tablename__ = "user_consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    consent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # upload_processing, data_retention, ai_analysis
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    consent_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User")


class MessageBookmark(Base):
    """Mensagens marcadas como favoritas pelo usuario."""
    __tablename__ = "message_bookmarks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(String(36), ForeignKey("messages.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
