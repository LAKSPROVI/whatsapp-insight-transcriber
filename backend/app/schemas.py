"""
Schemas Pydantic para validação e serialização
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models import ProcessingStatus, MediaType, SentimentType


# ─── Media Metadata ───────────────────────────────────────────────────────────
class MediaMetadata(BaseModel):
    file_size: Optional[int] = None          # bytes
    file_size_formatted: Optional[str] = None
    format: Optional[str] = None
    duration: Optional[float] = None         # segundos
    duration_formatted: Optional[str] = None
    resolution: Optional[str] = None         # "1920x1080"
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    codec: Optional[str] = None
    mime_type: Optional[str] = None


# ─── Message Schemas ──────────────────────────────────────────────────────────
class MessageBase(BaseModel):
    timestamp: datetime
    sender: str
    original_text: Optional[str] = None
    media_type: MediaType = MediaType.TEXT


class MessageResponse(BaseModel):
    id: str
    sequence_number: int
    timestamp: datetime
    sender: str
    original_text: Optional[str] = None
    media_type: MediaType
    media_filename: Optional[str] = None
    media_url: Optional[str] = None
    media_metadata: Optional[MediaMetadata] = None
    transcription: Optional[str] = None
    description: Optional[str] = None
    ocr_text: Optional[str] = None
    sentiment: Optional[SentimentType] = None
    sentiment_score: Optional[float] = None
    is_key_moment: bool = False
    processing_status: ProcessingStatus

    class Config:
        from_attributes = True


# ─── Conversation Schemas ─────────────────────────────────────────────────────
class ConversationCreate(BaseModel):
    session_id: str
    original_filename: str
    upload_path: str


class ConversationResponse(BaseModel):
    id: str
    session_id: str
    original_filename: str
    status: ProcessingStatus
    progress: float
    progress_message: Optional[str] = None
    conversation_name: Optional[str] = None
    participants: Optional[List[str]] = None
    total_messages: int
    total_media: int
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    summary: Optional[str] = None
    sentiment_overall: Optional[SentimentType] = None
    sentiment_score: Optional[float] = None
    keywords: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    word_frequency: Optional[Dict[str, int]] = None
    key_moments: Optional[List[Dict]] = None
    contradictions: Optional[List[Dict]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    messages: Optional[List[MessageResponse]] = None

    class Config:
        from_attributes = True


class ConversationListItem(BaseModel):
    id: str
    session_id: str
    original_filename: str
    status: ProcessingStatus
    progress: float
    conversation_name: Optional[str] = None
    total_messages: int
    total_media: int
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Upload Response ──────────────────────────────────────────────────────────
class UploadResponse(BaseModel):
    session_id: str
    conversation_id: str
    message: str
    status: ProcessingStatus


# ─── Processing Progress ──────────────────────────────────────────────────────
class ProcessingProgress(BaseModel):
    session_id: str
    status: ProcessingStatus
    progress: float
    progress_message: Optional[str] = None
    total_messages: int = 0
    processed_messages: int = 0
    active_agents: int = 0


# ─── Chat RAG Schemas ─────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    include_context: bool = True


class ChatResponse(BaseModel):
    id: str
    role: str
    content: str
    tokens_used: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    conversation_id: str
    messages: List[ChatResponse]


# ─── Export Schemas ───────────────────────────────────────────────────────────
class ExportRequest(BaseModel):
    conversation_id: str
    format: str = Field(..., pattern="^(pdf|docx)$")
    include_media_descriptions: bool = True
    include_sentiment_analysis: bool = True
    include_summary: bool = True
    include_statistics: bool = True


class ExportResponse(BaseModel):
    download_url: str
    filename: str
    file_size: int
    format: str


# ─── Analytics ───────────────────────────────────────────────────────────────
class ParticipantStats(BaseModel):
    name: str
    total_messages: int
    total_media: int
    avg_sentiment: Optional[float] = None
    first_message: Optional[datetime] = None
    last_message: Optional[datetime] = None


class ConversationAnalytics(BaseModel):
    conversation_id: str
    participant_stats: List[ParticipantStats]
    message_timeline: List[Dict[str, Any]]
    sentiment_timeline: List[Dict[str, Any]]
    media_breakdown: Dict[str, int]
    hourly_activity: Dict[str, int]
    key_moments: List[Dict[str, Any]]
    contradictions: List[Dict[str, Any]]
    word_cloud_data: List[Dict[str, Any]]
    topics: List[str]


# ─── Agent Status ─────────────────────────────────────────────────────────────
class AgentStatus(BaseModel):
    agent_id: str
    is_busy: bool
    current_job: Optional[str] = None
    jobs_completed: int
    avg_processing_time: float


class OrchestratorStatus(BaseModel):
    total_agents: int
    active_agents: int
    idle_agents: int
    queue_size: int
    agents: List[AgentStatus]
