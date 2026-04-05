import type {
  UploadResponse,
  ProcessingProgress,
  ConversationListItem,
  Conversation,
  Message,
  ChatHistoryResponse,
  ConversationAnalytics,
  ExportOptions,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  SearchParams,
  SearchResponse,
  SearchConversationsResponse,
  TemplateListResponse,
  TemplateAnalysisResult,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// ─── APIError ───────────────────────────────────────────────────────────────

export class APIError extends Error {
  status: number;
  statusText: string;
  data: string;

  constructor(status: number, statusText: string, data: string) {
    const message = getHTTPErrorMessage(status, data);
    super(message);
    this.name = "APIError";
    this.status = status;
    this.statusText = statusText;
    this.data = data;
  }
}

function getHTTPErrorMessage(status: number, data: string): string {
  switch (status) {
    case 400:
      return `Requisição inválida: ${data || "verifique os dados enviados."}`;
    case 401:
      return "Sessão expirada. Faça login novamente.";
    case 403:
      return "Acesso negado. Você não tem permissão para esta ação.";
    case 404:
      return "Recurso não encontrado.";
    case 409:
      return data.includes("already exists") ? "Este recurso já existe." : `Conflito: ${data}`;
    case 413:
      return "Arquivo muito grande para o servidor processar.";
    case 422:
      return `Dados inválidos: ${data || "verifique os campos."}`;
    case 429:
      return "Muitas requisições. Aguarde um momento e tente novamente.";
    case 500:
      return "Erro interno do servidor. Tente novamente em instantes.";
    case 502:
      return "Servidor indisponível. Tente novamente em instantes.";
    case 503:
      return "Serviço temporariamente indisponível. Tente novamente em instantes.";
    case 504:
      return "O servidor demorou para responder. Tente novamente.";
    default:
      return `Erro do servidor (${status}): ${data || "erro desconhecido."}`;
  }
}

// ─── Token Management ───────────────────────────────────────────────────────

const TOKEN_KEY = "wit_auth_token";


export function buildApiUrl(path: string): string {
  if (!API_BASE) return path;
  return `${API_BASE}${path}`;
}


export function buildAuthenticatedMediaUrl(path: string): string {
  const token = getToken();
  const url = new URL(buildApiUrl(path), typeof window !== "undefined" ? window.location.origin : "http://localhost");
  if (token) {
    url.searchParams.set("token", token);
  }
  if (!API_BASE && typeof window !== "undefined") {
    return `${url.pathname}${url.search}`;
  }
  return url.toString();
}


export function buildWebSocketUrl(path: string): string {
  if (typeof window !== "undefined" && !API_BASE) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${path}`;
  }

  return `${API_BASE.replace(/^http/, "ws")}${path}`;
}


/**
 * Fetches media as a blob and returns an object URL.
 * Callers MUST call `revoke()` when done to avoid memory leaks.
 */
export async function fetchMediaBlob(path: string): Promise<{ url: string; revoke: () => void }> {
  const token = getToken();
  const response = await fetch(buildApiUrl(path), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new APIError(response.status, response.statusText, body);
  }

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  return { url: blobUrl, revoke: () => URL.revokeObjectURL(blobUrl) };
}

export function setToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

export function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem(TOKEN_KEY);
  }
  return null;
}

export function removeToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// ─── Auth Redirect ──────────────────────────────────────────────────────────

let onUnauthorized: (() => void) | null = null;

export function setOnUnauthorized(callback: () => void): void {
  onUnauthorized = callback;
}

// ─── Core Fetch with Retry ──────────────────────────────────────────────────

function authHeaders(init?: RequestInit): RequestInit {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return { ...init, headers };
}

const DEFAULT_TIMEOUT = 30_000;
const PROCESSING_TIMEOUT = 120_000;
const MAX_RETRIES = 3;
const RETRY_BASE_DELAY = 1000;

function isRetryableStatus(status: number): boolean {
  return status >= 500 && status <= 599;
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT,
  retries: number = MAX_RETRIES
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const opts = authHeaders(init);
      const res = await fetch(buildApiUrl(path), {
        ...opts,
        signal: init?.signal ?? controller.signal,
      });
      clearTimeout(timeout);

      if (res.status === 401) {
        removeToken();
        onUnauthorized?.();
        throw new APIError(401, res.statusText, "");
      }

      if (!res.ok) {
        const body = await res.text().catch(() => "");
        const apiError = new APIError(res.status, res.statusText, body);

        // Retry apenas para erros 5xx
        if (isRetryableStatus(res.status) && attempt < retries) {
          lastError = apiError;
          const delay = RETRY_BASE_DELAY * Math.pow(2, attempt);
          console.warn(
            `[API] Retry ${attempt + 1}/${retries} para ${path} após ${delay}ms (status ${res.status})`
          );
          await sleep(delay);
          continue;
        }

        throw apiError;
      }

      return res.json() as Promise<T>;
    } catch (err: unknown) {
      clearTimeout(timeout);

      if (err instanceof APIError) {
        throw err;
      }

      const error = err instanceof Error ? err : new Error(String(err));

      if (error.name === "AbortError") {
        throw new Error("Tempo limite excedido. Verifique sua conexão e tente novamente.");
      }

      // Retry para erros de rede
      if (attempt < retries && error.message.includes("fetch")) {
        lastError = error;
        const delay = RETRY_BASE_DELAY * Math.pow(2, attempt);
        console.warn(
          `[API] Retry ${attempt + 1}/${retries} para ${path} após ${delay}ms (erro de rede)`
        );
        await sleep(delay);
        continue;
      }

      throw error;
    }
  }

  throw lastError ?? new Error("Erro inesperado na requisição.");
}

// ─── Authentication ─────────────────────────────────────────────────────────

export async function login(username: string, password: string): Promise<LoginResponse> {
  const body: LoginRequest = { username, password };
  const res = await apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  setToken(res.access_token);
  return res;
}

export async function register(username: string, password: string): Promise<RegisterResponse> {
  const body: RegisterRequest = { username, password };
  return apiFetch<RegisterResponse>("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function logout(): void {
  removeToken();
  onUnauthorized?.();
}

export async function getCurrentUser(): Promise<import("@/types").User> {
  return apiFetch<import("@/types").User>("/api/auth/me");
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

// ─── Admin User Management ──────────────────────────────────────────────────

export async function adminListUsers(): Promise<import("@/types").UserDetail[]> {
  return apiFetch<import("@/types").UserDetail[]>("/api/auth/admin/users");
}

export async function adminCreateUser(
  username: string,
  password: string,
  fullName: string = ""
): Promise<import("@/types").UserDetail> {
  return apiFetch<import("@/types").UserDetail>("/api/auth/admin/users/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, full_name: fullName }),
  });
}

export async function adminUpdateUser(
  userId: string,
  data: import("@/types").UserUpdateRequest
): Promise<import("@/types").UserDetail> {
  return apiFetch<import("@/types").UserDetail>(`/api/auth/admin/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function adminResetPassword(
  userId: string,
  newPassword: string
): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/api/auth/admin/users/${userId}/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export async function adminDeleteUser(userId: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/api/auth/admin/users/${userId}`, {
    method: "DELETE",
  });
}

// ─── Conversations ──────────────────────────────────────────────────────────

export async function uploadConversation(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  // Timeout maior para upload de arquivos grandes (5 minutos), sem retry
  return apiFetch<UploadResponse>(
    "/api/conversations/upload",
    { method: "POST", body: form },
    300_000,
    0
  );
}

export async function getProgress(sessionId: string): Promise<ProcessingProgress> {
  return apiFetch<ProcessingProgress>(
    `/api/conversations/progress/${sessionId}`,
    undefined,
    DEFAULT_TIMEOUT
  );
}

export async function listConversations(
  skip = 0,
  limit = 20
): Promise<ConversationListItem[]> {
  return apiFetch<ConversationListItem[]>(
    `/api/conversations/?skip=${skip}&limit=${limit}`
  );
}

export async function getConversation(id: string): Promise<Conversation> {
  return apiFetch<Conversation>(`/api/conversations/${id}`);
}

export async function deleteConversation(id: string): Promise<void> {
  await apiFetch<unknown>(`/api/conversations/${id}`, { method: "DELETE" });
}

export async function getMessages(
  conversationId: string,
  skip = 0,
  limit = 100,
  mediaOnly = false,
  sender?: string
): Promise<Message[]> {
  const params = new URLSearchParams({
    skip: String(skip),
    limit: String(limit),
    media_only: String(mediaOnly),
  });
  if (sender) params.set("sender", sender);
  return apiFetch<Message[]>(
    `/api/conversations/${conversationId}/messages?${params}`
  );
}

// ─── Chat ───────────────────────────────────────────────────────────────────

export function createChatStream(
  conversationId: string,
  message: string,
  onChunk: (chunk: string) => void,
  onDone: () => void,
  onError?: (err: Error) => void
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const token = getToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(
        `${API_BASE}/api/chat/${conversationId}/message`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ message }),
          signal: controller.signal,
        }
      );

      if (res.status === 401) {
        removeToken();
        onUnauthorized?.();
        onError?.(new APIError(401, "Unauthorized", ""));
        return;
      }

      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new APIError(res.status, res.statusText, body);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("Resposta sem corpo de dados.");

      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        onChunk(decoder.decode(value, { stream: true }));
      }
      onDone();
    } catch (err: unknown) {
      const error = err instanceof Error ? err : new Error(String(err));
      if (error.name !== "AbortError") {
        onError?.(error);
      }
    }
  })();

  return () => controller.abort();
}

export async function getChatHistory(
  conversationId: string
): Promise<ChatHistoryResponse> {
  return apiFetch<ChatHistoryResponse>(
    `/api/chat/${conversationId}/history`
  );
}

export async function clearChatHistory(
  conversationId: string
): Promise<void> {
  await apiFetch<unknown>(`/api/chat/${conversationId}/history`, {
    method: "DELETE",
  });
}

// ─── Analytics ──────────────────────────────────────────────────────────────

export async function getAnalytics(
  conversationId: string
): Promise<ConversationAnalytics> {
  return apiFetch<ConversationAnalytics>(
    `/api/chat/${conversationId}/analytics`,
    undefined,
    PROCESSING_TIMEOUT
  );
}

// ─── Export ─────────────────────────────────────────────────────────────────

export async function exportConversation(
  conversationId: string,
  options: ExportOptions
): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(
    `${API_BASE}/api/conversations/${conversationId}/export`,
    {
      method: "POST",
      headers,
      body: JSON.stringify(options),
    }
  );

  if (res.status === 401) {
    removeToken();
    onUnauthorized?.();
    throw new APIError(401, "Unauthorized", "");
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new APIError(res.status, res.statusText, body);
  }

  const contentType = res.headers.get("content-type") || "";
  let blob: Blob;

  if (contentType.includes("application/json")) {
    const data: { download_url?: string } = await res.json();
    if (data.download_url) {
      const fileHeaders: Record<string, string> = {};
      if (token) {
        fileHeaders["Authorization"] = `Bearer ${token}`;
      }
      const fileRes = await fetch(data.download_url, { headers: fileHeaders });
      if (!fileRes.ok) throw new Error("Falha ao baixar o arquivo exportado.");
      blob = await fileRes.blob();
    } else {
      throw new Error("Resposta de exportação inválida.");
    }
  } else {
    blob = await res.blob();
  }

  const extMap: Record<string, string> = {
    pdf: "pdf", docx: "docx", xlsx: "xlsx", csv: "csv", html: "html", json: "json",
  };
  const ext = extMap[options.format] || options.format;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `relatorio_conversa.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Search ─────────────────────────────────────────────────────────────────

export async function searchMessages(params: SearchParams): Promise<SearchResponse> {
  const qs = new URLSearchParams();
  qs.set("q", params.q);
  if (params.conversation_id) qs.set("conversation_id", params.conversation_id);
  if (params.sender) qs.set("sender", params.sender);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  if (params.type) qs.set("type", params.type);
  if (params.regex) qs.set("regex", "true");
  if (params.offset) qs.set("offset", String(params.offset));
  if (params.limit) qs.set("limit", String(params.limit));
  return apiFetch<SearchResponse>(`/api/search/messages?${qs}`);
}

export async function searchConversations(
  q: string,
  dateFrom?: string,
  dateTo?: string
): Promise<SearchConversationsResponse> {
  const qs = new URLSearchParams({ q });
  if (dateFrom) qs.set("date_from", dateFrom);
  if (dateTo) qs.set("date_to", dateTo);
  return apiFetch<SearchConversationsResponse>(`/api/search/conversations?${qs}`);
}

// ─── Custody & Audit ─────────────────────────────────────────────────────────

export interface CustodyRecord {
  id: string;
  event_type: string;
  actor_id?: string;
  description?: string;
  prev_hash: string;
  current_hash: string;
  evidence?: Record<string, unknown>;
  created_at?: string;
}

export interface CustodyChainResponse {
  conversation_id: string;
  records: CustodyRecord[];
  total: number;
}

export interface ChainVerificationResponse {
  valid: boolean;
  records_checked: number;
  error?: string;
  first_hash?: string;
  last_hash?: string;
}

export interface CertificateResponse {
  certificate_id: string;
  signature: string;
  chain_valid: boolean;
  zip_hash: string;
  merkle_root: string;
  issued_at: string;
  file_count: number;
  message_count: number;
  conversation_name: string;
}

export interface AuditEvent {
  id: string;
  action: string;
  user_id?: string;
  resource_type?: string;
  resource_id?: string;
  details?: Record<string, unknown>;
  ip_address?: string;
  user_agent?: string;
  prev_hash?: string;
  event_hash?: string;
  created_at?: string;
}

export interface AuditEventsResponse {
  events: AuditEvent[];
  total: number;
}

export async function getCustodyChain(conversationId: string): Promise<CustodyChainResponse> {
  return apiFetch<CustodyChainResponse>(`/api/custody/${conversationId}/chain`);
}

export async function verifyCustodyChain(conversationId: string): Promise<ChainVerificationResponse> {
  return apiFetch<ChainVerificationResponse>(`/api/custody/${conversationId}/verify`);
}

export async function generateCertificate(conversationId: string): Promise<CertificateResponse> {
  return apiFetch<CertificateResponse>(`/api/custody/${conversationId}/certificate`, {
    method: "POST",
  });
}

export async function verifyCertificate(certificateId: string): Promise<{ valid: boolean; signature_valid: boolean; chain_valid: boolean }> {
  return apiFetch(`/api/custody/certificate/${certificateId}/verify`);
}

export async function getAuditEvents(
  conversationId: string,
  limit = 100,
  offset = 0
): Promise<AuditEventsResponse> {
  return apiFetch<AuditEventsResponse>(
    `/api/custody/audit/${conversationId}?limit=${limit}&offset=${offset}`
  );
}

// ─── Semantic Search ───────────────────────────────────────────────────

export interface SemanticSearchResult {
  message_id: string;
  content: string;
  score: number;
}

export async function semanticSearch(
  conversationId: string,
  query: string,
  limit = 10
): Promise<SemanticSearchResult[]> {
  const qs = new URLSearchParams({ conversation_id: conversationId, q: query, limit: String(limit) });
  return apiFetch<SemanticSearchResult[]>(`/api/search/semantic?${qs}`);
}

// ─── Agent Status ──────────────────────────────────────────────────────

export async function getAgentStatus(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/api/agents/status");
}

// ─── Dashboard ─────────────────────────────────────────────────────────

export async function getDashboardUsage(days = 30): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>(`/api/dashboard/usage?days=${days}`);
}

// ─── Tags & Bookmarks ─────────────────────────────────────────────────

export interface UserTag {
  id: string;
  name: string;
  color: string;
  owner_id?: string;
  created_at?: string;
}

export interface BookmarkEntry {
  id: string;
  message_id: string;
  conversation_id: string;
  user_id: string;
  note?: string;
  created_at?: string;
}

export async function getTags(): Promise<{ tags: UserTag[] }> {
  return apiFetch<{ tags: UserTag[] }>("/api/tags/");
}

export async function createTag(name: string, color: string): Promise<UserTag> {
  return apiFetch<UserTag>("/api/tags/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, color }),
  });
}

export async function deleteTag(tagId: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/api/tags/${tagId}`, { method: "DELETE" });
}

export async function getBookmarks(conversationId: string): Promise<{ bookmarks: BookmarkEntry[] }> {
  return apiFetch<{ bookmarks: BookmarkEntry[] }>(`/api/tags/bookmarks/${conversationId}`);
}

export async function createBookmark(
  messageId: string,
  conversationId: string,
  note?: string
): Promise<BookmarkEntry> {
  return apiFetch<BookmarkEntry>("/api/tags/bookmarks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: messageId, conversation_id: conversationId, note }),
  });
}

export async function deleteBookmark(bookmarkId: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/api/tags/bookmarks/${bookmarkId}`, { method: "DELETE" });
}

// ─── Templates ──────────────────────────────────────────────────────────────

export async function getTemplates(): Promise<TemplateListResponse> {
  return apiFetch<TemplateListResponse>("/api/templates");
}

export async function analyzeWithTemplate(
  templateId: string,
  conversationId: string,
  promptKeys?: string[]
): Promise<TemplateAnalysisResult> {
  return apiFetch<TemplateAnalysisResult>(
    `/api/templates/${templateId}/analyze/${conversationId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(promptKeys ? { prompt_keys: promptKeys } : {}),
    },
    PROCESSING_TIMEOUT,
    0
  );
}
