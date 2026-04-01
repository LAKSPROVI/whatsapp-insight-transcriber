import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {
  listConversations,
  getConversation,
  getMessages,
  uploadConversation,
  deleteConversation,
  exportConversation,
  getProgress,
  getChatHistory,
  clearChatHistory,
  getAnalytics,
} from "@/lib/api";
import type {
  ConversationListItem,
  Conversation,
  Message,
  UploadResponse,
  ExportOptions,
  ConversationAnalytics,
  ChatHistoryResponse,
} from "@/types";

// ─── Query Keys ─────────────────────────────────────────────────────────────

export const queryKeys = {
  conversations: ["conversations"] as const,
  conversationList: (skip: number, limit: number) =>
    ["conversations", "list", skip, limit] as const,
  conversation: (id: string) => ["conversations", id] as const,
  messages: (conversationId: string, skip: number, limit: number, sender?: string) =>
    ["messages", conversationId, skip, limit, sender] as const,
  progress: (sessionId: string) => ["progress", sessionId] as const,
  chatHistory: (conversationId: string) =>
    ["chat", conversationId, "history"] as const,
  analytics: (conversationId: string) =>
    ["analytics", conversationId] as const,
};

// ─── Queries ────────────────────────────────────────────────────────────────

export function useConversations(skip = 0, limit = 10, enabled = true) {
  return useQuery<ConversationListItem[]>({
    queryKey: queryKeys.conversationList(skip, limit),
    queryFn: () => listConversations(skip, limit),
    enabled,
  });
}

export function useConversation(id: string, enabled = true) {
  return useQuery<Conversation>({
    queryKey: queryKeys.conversation(id),
    queryFn: () => getConversation(id),
    enabled: !!id && enabled,
  });
}

export function useMessages(
  conversationId: string,
  skip = 0,
  limit = 100,
  sender?: string,
  enabled = true
) {
  return useQuery<Message[]>({
    queryKey: queryKeys.messages(conversationId, skip, limit, sender),
    queryFn: () => getMessages(conversationId, skip, limit, false, sender),
    enabled: !!conversationId && enabled,
  });
}

export function useProgress(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.progress(sessionId),
    queryFn: () => getProgress(sessionId),
    enabled: !!sessionId && enabled,
    refetchInterval: 2000, // Poll every 2 seconds
    staleTime: 0,
  });
}

export function useChatHistory(conversationId: string, enabled = true) {
  return useQuery<ChatHistoryResponse>({
    queryKey: queryKeys.chatHistory(conversationId),
    queryFn: () => getChatHistory(conversationId),
    enabled: !!conversationId && enabled,
  });
}

export function useAnalytics(conversationId: string, enabled = true) {
  return useQuery<ConversationAnalytics>({
    queryKey: queryKeys.analytics(conversationId),
    queryFn: () => getAnalytics(conversationId),
    enabled: !!conversationId && enabled,
    staleTime: 10 * 60 * 1000, // 10 min
  });
}

// ─── Mutations ──────────────────────────────────────────────────────────────

export function useUploadConversation() {
  const qc = useQueryClient();
  return useMutation<UploadResponse, Error, File>({
    mutationFn: (file: File) => uploadConversation(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.conversations });
    },
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.conversations });
    },
  });
}

export function useExportConversation() {
  return useMutation<
    void,
    Error,
    { conversationId: string; options: ExportOptions }
  >({
    mutationFn: ({ conversationId, options }) =>
      exportConversation(conversationId, options),
  });
}

export function useClearChatHistory() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (conversationId: string) => clearChatHistory(conversationId),
    onSuccess: (_data, conversationId) => {
      qc.invalidateQueries({
        queryKey: queryKeys.chatHistory(conversationId),
      });
    },
  });
}
