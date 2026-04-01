import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import type {
  ProcessingProgress,
  ConversationListItem,
  ChatMessage,
  AppView,
  UIState,
} from "@/types";
import {
  isAuthenticated as checkAuth,
  logout as apiLogout,
  login as apiLogin,
  setOnUnauthorized,
} from "@/lib/api";

// ─── Auth Slice ─────────────────────────────────────────────────────────────

interface AuthSlice {
  isAuthenticated: boolean | null;
  checkAuthentication: () => void;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  setAuthenticated: (value: boolean | null) => void;
}

// ─── UI Slice ───────────────────────────────────────────────────────────────

interface UISlice {
  uiState: UIState;
  setUIState: (state: UIState) => void;
  navigateHome: () => void;
  navigateToProcessing: (sessionId: string) => void;
  navigateToConversation: (conversationId: string) => void;
}

// ─── Processing Slice ───────────────────────────────────────────────────────

interface ProcessingSlice {
  isUploading: boolean;
  setIsUploading: (value: boolean) => void;
  progress: ProcessingProgress | null;
  setProgress: (progress: ProcessingProgress | null) => void;
}

// ─── Conversations Slice ────────────────────────────────────────────────────

interface ConversationsSlice {
  recentConversations: ConversationListItem[];
  setRecentConversations: (convs: ConversationListItem[]) => void;
  removeConversation: (id: string) => void;
}

// ─── Chat Slice ─────────────────────────────────────────────────────────────

interface ChatSlice {
  chatMessages: ChatMessage[];
  setChatMessages: (msgs: ChatMessage[]) => void;
  addChatMessage: (msg: ChatMessage) => void;
  clearChatMessages: () => void;
}

// ─── Combined Store ─────────────────────────────────────────────────────────

export type AppStore = AuthSlice &
  UISlice &
  ProcessingSlice &
  ConversationsSlice &
  ChatSlice;

export const useAppStore = create<AppStore>()(
  devtools(
    persist(
      (set, get) => ({
        // ── Auth ──────────────────────────────────────────────────────
        isAuthenticated: null,

        checkAuthentication: () => {
          const authed = checkAuth();
          set({ isAuthenticated: authed });
          setOnUnauthorized(() => {
            set({ isAuthenticated: false });
          });
        },

        login: async (username: string, password: string) => {
          await apiLogin(username, password);
          set({ isAuthenticated: true });
        },

        logout: () => {
          apiLogout();
          set({
            isAuthenticated: false,
            uiState: { currentView: "home" },
            recentConversations: [],
            progress: null,
            isUploading: false,
            chatMessages: [],
          });
        },

        setAuthenticated: (value: boolean | null) => {
          set({ isAuthenticated: value });
        },

        // ── UI ────────────────────────────────────────────────────────
        uiState: { currentView: "home" },

        setUIState: (state: UIState) => {
          set({ uiState: state });
        },

        navigateHome: () => {
          set({
            uiState: { currentView: "home" },
            isUploading: false,
            progress: null,
          });
        },

        navigateToProcessing: (sessionId: string) => {
          set({
            uiState: { currentView: "processing", sessionId },
          });
        },

        navigateToConversation: (conversationId: string) => {
          set({
            uiState: {
              currentView: "conversation",
              selectedConversationId: conversationId,
            },
          });
        },

        // ── Processing ───────────────────────────────────────────────
        isUploading: false,
        setIsUploading: (value: boolean) => set({ isUploading: value }),

        progress: null,
        setProgress: (progress: ProcessingProgress | null) =>
          set({ progress }),

        // ── Conversations ────────────────────────────────────────────
        recentConversations: [],

        setRecentConversations: (convs: ConversationListItem[]) =>
          set({ recentConversations: convs }),

        removeConversation: (id: string) =>
          set((state) => ({
            recentConversations: state.recentConversations.filter(
              (c) => c.id !== id
            ),
          })),

        // ── Chat ─────────────────────────────────────────────────────
        chatMessages: [],

        setChatMessages: (msgs: ChatMessage[]) =>
          set({ chatMessages: msgs }),

        addChatMessage: (msg: ChatMessage) =>
          set((state) => ({
            chatMessages: [...state.chatMessages, msg],
          })),

        clearChatMessages: () => set({ chatMessages: [] }),
      }),
      {
        name: "whatsapp-insight-store",
        // Only persist auth-related state
        partialize: (state) => ({
          isAuthenticated: state.isAuthenticated,
        }),
      }
    ),
    { name: "WhatsAppInsightStore" }
  )
);
