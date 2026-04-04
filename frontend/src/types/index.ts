// ─── API Types ──────────────────────────────────────────────────────────────

export type ProcessingStatus =
  | "pending"
  | "uploading"
  | "parsing"
  | "processing"
  | "completed"
  | "failed";

export type MediaType =
  | "text"
  | "image"
  | "audio"
  | "video"
  | "document"
  | "sticker"
  | "contact"
  | "location"
  | "deleted";

export type SentimentType = "positive" | "negative" | "neutral" | "mixed";

// ─── Media ──────────────────────────────────────────────────────────────────

export interface MediaMetadata {
  file_size?: number;
  file_size_formatted?: string;
  format?: string;
  duration?: number;
  duration_formatted?: string;
  resolution?: string;
  width?: number;
  height?: number;
  fps?: number;
  bitrate?: number;
  sample_rate?: number;
  channels?: number;
  codec?: string;
  mime_type?: string;
}

// ─── Message ─────────────────────────────────────────────────────────────────

export interface Message {
  id: string;
  sequence_number: number;
  timestamp: string;
  sender: string;
  original_text?: string;
  media_type: MediaType;
  media_filename?: string;
  media_url?: string;
  media_metadata?: MediaMetadata;
  transcription?: string;
  description?: string;
  ocr_text?: string;
  sentiment?: SentimentType;
  sentiment_score?: number;
  is_key_moment: boolean;
  processing_status: ProcessingStatus;
}

// ─── Conversation ─────────────────────────────────────────────────────────────

export interface Conversation {
  id: string;
  session_id: string;
  original_filename: string;
  status: ProcessingStatus;
  progress: number;
  progress_message?: string;
  conversation_name?: string;
  participants?: string[];
  total_messages: number;
  total_media: number;
  date_start?: string;
  date_end?: string;
  summary?: string;
  sentiment_overall?: SentimentType;
  sentiment_score?: number;
  keywords?: string[];
  topics?: string[];
  word_frequency?: Record<string, number>;
  key_moments?: KeyMoment[];
  contradictions?: Contradiction[];
  created_at: string;
  updated_at: string;
  completed_at?: string;
  messages?: Message[];
}

export interface ConversationListItem {
  id: string;
  session_id: string;
  original_filename: string;
  status: ProcessingStatus;
  progress: number;
  conversation_name?: string;
  total_messages: number;
  total_media: number;
  date_start?: string;
  date_end?: string;
  created_at: string;
}

export interface KeyMoment {
  timestamp_approx?: string;
  description: string;
}

export interface Contradiction {
  description: string;
  statement_1?: string;
  statement_2?: string;
  participant?: string;
  severity?: "high" | "medium" | "low";
}

// ─── Upload ───────────────────────────────────────────────────────────────────

export interface UploadResponse {
  session_id: string;
  conversation_id: string;
  message: string;
  status: ProcessingStatus;
}

export interface ProcessingProgress {
  session_id: string;
  status: ProcessingStatus;
  progress: number;
  progress_message?: string;
  total_messages: number;
  processed_messages: number;
  active_agents: number;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tokens_used?: number;
  created_at: string;
}

export interface ChatHistoryResponse {
  conversation_id: string;
  messages: ChatMessage[];
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export interface ParticipantStats {
  name: string;
  total_messages: number;
  total_media: number;
  avg_sentiment?: number;
  first_message?: string;
  last_message?: string;
}

export interface ConversationAnalytics {
  conversation_id: string;
  participant_stats: ParticipantStats[];
  message_timeline: { date: string; count: number }[];
  sentiment_timeline: { timestamp: string; sender: string; score: number }[];
  media_breakdown: Record<string, number>;
  hourly_activity: Record<string, number>;
  key_moments: KeyMoment[];
  contradictions: Contradiction[];
  word_cloud_data: { text: string; value: number }[];
  topics: string[];
}

// ─── Agent ───────────────────────────────────────────────────────────────────

export interface AgentStatus {
  agent_id: string;
  is_busy: boolean;
  current_job?: string;
  jobs_completed: number;
  avg_processing_time: number;
  errors?: number;
}

export interface OrchestratorStatus {
  total_agents: number;
  active_agents: number;
  idle_agents: number;
  queue_size: number;
  agents: AgentStatus[];
}

// ─── Export ───────────────────────────────────────────────────────────────────

export interface ExportOptions {
  format: "pdf" | "docx" | "xlsx" | "csv" | "html" | "json";
  include_media_descriptions: boolean;
  include_sentiment_analysis: boolean;
  include_summary: boolean;
  include_statistics: boolean;
}

// ─── Authentication ──────────────────────────────────────────────────────────

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  full_name?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
}

export interface RegisterResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
}

export interface User {
  id: string;
  username: string;
  full_name: string;
  is_admin: boolean;
}

export interface UserDetail {
  id: string;
  username: string;
  full_name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserUpdateRequest {
  full_name?: string;
  is_active?: boolean;
  is_admin?: boolean;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface AdminResetPasswordRequest {
  new_password: string;
}

// ─── Search ──────────────────────────────────────────────────────────────────

export interface SearchParams {
  q: string;
  conversation_id?: string;
  sender?: string;
  date_from?: string;
  date_to?: string;
  type?: MediaType;
  regex?: boolean;
  offset?: number;
  limit?: number;
}

export interface SearchResultItem {
  message_id: string;
  conversation_id: string;
  conversation_name?: string;
  sequence_number: number;
  timestamp: string;
  sender: string;
  text?: string;
  highlighted_text?: string;
  media_type: MediaType;
  sentiment?: SentimentType;
  score: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  offset: number;
  limit: number;
  results: SearchResultItem[];
}

export interface SearchConversationItem {
  conversation_id: string;
  conversation_name?: string;
  participants?: string[];
  total_messages: number;
  date_start?: string;
  date_end?: string;
  match_count: number;
}

export interface SearchConversationsResponse {
  query: string;
  total: number;
  results: SearchConversationItem[];
}

// ─── Templates ──────────────────────────────────────────────────────────────

export interface Template {
  id: string;
  name: string;
  description: string;
  prompts: Record<string, string>;
}

export interface TemplateListResponse {
  templates: Template[];
}

export interface TemplateAnalysisResult {
  template_id: string;
  template_name: string;
  conversation_id: string;
  results: Record<string, string>;
  executed_prompts: string[];
}

// ─── UI State ─────────────────────────────────────────────────────────────────

export type AppView = "home" | "processing" | "conversation" | "history";

export interface UIState {
  currentView: AppView;
  selectedConversationId?: string;
  sessionId?: string;
}
