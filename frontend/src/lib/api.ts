import type {
  UploadResponse,
  ProcessingProgress,
  ConversationListItem,
  Conversation,
  Message,
  ChatHistoryResponse,
  ConversationAnalytics,
  ExportOptions,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8020";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ─── Conversations ──────────────────────────────────────────────────────────

export async function uploadConversation(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<UploadResponse>("/api/conversations/upload", {
    method: "POST",
    body: form,
  });
}

export async function getProgress(sessionId: string): Promise<ProcessingProgress> {
  return apiFetch<ProcessingProgress>(`/api/conversations/progress/${sessionId}`);
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
      const res = await fetch(
        `${API_BASE}/api/chat/${conversationId}/message`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
          signal: controller.signal,
        }
      );

      if (!res.ok) throw new Error(`Chat API ${res.status}`);

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No reader");

      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        onChunk(decoder.decode(value, { stream: true }));
      }
      onDone();
    } catch (err: any) {
      if (err.name !== "AbortError") {
        onError?.(err);
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
    `/api/chat/${conversationId}/analytics`
  );
}

// ─── Export ─────────────────────────────────────────────────────────────────

export async function exportConversation(
  conversationId: string,
  options: ExportOptions
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/conversations/${conversationId}/export`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options),
    }
  );
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);

  const blob = await res.blob();
  const ext = options.format === "pdf" ? "pdf" : "docx";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `relatorio_conversa.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}
