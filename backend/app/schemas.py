"""
Schemas Pydantic para validação e serialização
"""
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models import ProcessingStatus, MediaType, SentimentType


# ─── Sanitização Helper ───────────────────────────────────────────────────────

def _sanitize_string(value: str) -> str:
    """Remove caracteres de controle perigosos, mantém unicode legítimo."""
    # Remove null bytes e caracteres de controle (exceto newline e tab)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    return sanitized.strip()


# ─── Media Metadata ───────────────────────────────────────────────────────────
class MediaMetadata(BaseModel):
    file_size: Optional[int] = None          # bytes
    file_size_formatted: Optional[str] = Field(default=None, max_length=50)
    format: Optional[str] = Field(default=None, max_length=50)
    duration: Optional[float] = None         # segundos
    duration_formatted: Optional[str] = Field(default=None, max_length=50)
    resolution: Optional[str] = Field(default=None, max_length=20)  # "1920x1080"
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    codec: Optional[str] = Field(default=None, max_length=50)
    mime_type: Optional[str] = Field(default=None, max_length=100)


# ─── Message Schemas ──────────────────────────────────────────────────────────
class MessageBase(BaseModel):
    timestamp: datetime
    sender: str = Field(..., min_length=1, max_length=200)
    original_text: Optional[str] = Field(default=None, max_length=50000)
    media_type: MediaType = MediaType.TEXT

    @field_validator("sender")
    @classmethod
    def sanitize_sender(cls, v: str) -> str:
        return _sanitize_string(v)

    @field_validator("original_text")
    @classmethod
    def sanitize_original_text(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _sanitize_string(v)
        return v


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

    model_config = ConfigDict(from_attributes=True)


# ─── Conversation Schemas ─────────────────────────────────────────────────────
class ConversationCreate(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    original_filename: str = Field(..., min_length=1, max_length=255)
    upload_path: str = Field(..., min_length=1, max_length=500)

    @field_validator("original_filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        v = _sanitize_string(v)
        # Bloquear path traversal em filenames
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Nome de arquivo contém caracteres inválidos")
        return v


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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
    conversation_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=10000)
    include_context: bool = True

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "conv-abc123",
                    "message": "Quais foram os principais tópicos discutidos nesta conversa?",
                    "include_context": True,
                }
            ]
        }
    }

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        v = _sanitize_string(v)
        if len(v) < 1:
            raise ValueError("Mensagem não pode estar vazia após sanitização")
        return v

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("ID de conversa contém caracteres inválidos")
        return v


class ChatResponse(BaseModel):
    id: str
    role: str
    content: str
    tokens_used: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    conversation_id: str
    messages: List[ChatResponse]


# ─── Export Schemas ───────────────────────────────────────────────────────────
class ExportRequest(BaseModel):
    conversation_id: Optional[str] = Field(default=None, max_length=100)
    format: str = Field(..., pattern="^(pdf|docx|xlsx|csv|html|json)$")
    include_media_descriptions: bool = True
    include_sentiment_analysis: bool = True
    include_summary: bool = True
    include_statistics: bool = True

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "format": "pdf",
                    "include_media_descriptions": True,
                    "include_sentiment_analysis": True,
                    "include_summary": True,
                    "include_statistics": True,
                }
            ]
        }
    }

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("ID de conversa contém caracteres inválidos")
        return v


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


# ─── Search Schemas ──────────────────────────────────────────────────────────

class SearchMessageRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=500)
    conversation_id: Optional[str] = Field(default=None, max_length=100)
    sender: Optional[str] = Field(default=None, max_length=200)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    message_type: Optional[str] = Field(default=None, max_length=20)
    regex: bool = False
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
    sort_by: str = Field(default="relevance", pattern="^(relevance|chronological)$")

    @field_validator("conversation_id")
    @classmethod
    def validate_conv_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("ID de conversa contém caracteres inválidos")
        return v


class SearchResultItem(BaseModel):
    message_id: str
    conversation_id: str
    conversation_name: Optional[str] = None
    sequence_number: int
    timestamp: datetime
    sender: str
    text: Optional[str] = None
    highlighted_text: Optional[str] = None
    media_type: MediaType
    sentiment: Optional[SentimentType] = None
    score: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    query: str
    total: int
    offset: int
    limit: int
    results: List[SearchResultItem]


class SearchConversationItem(BaseModel):
    conversation_id: str
    conversation_name: Optional[str] = None
    participants: Optional[List[str]] = None
    total_messages: int
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    match_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SearchConversationsResponse(BaseModel):
    query: str
    total: int
    results: List[SearchConversationItem]


# ─── Template Schemas ────────────────────────────────────────────────────────

class TemplatePrompts(BaseModel):
    summary: Optional[str] = None
    entities: Optional[str] = None
    timeline: Optional[str] = None
    contradictions: Optional[str] = None
    sentiment: Optional[str] = None
    recommendations: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    prompts: Dict[str, str]


class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]


class TemplateAnalysisRequest(BaseModel):
    prompt_keys: Optional[List[str]] = None  # quais prompts executar, None = todos


class TemplateAnalysisResponse(BaseModel):
    template_id: str
    template_name: str
    conversation_id: str
    results: Dict[str, str]
    executed_prompts: List[str]
