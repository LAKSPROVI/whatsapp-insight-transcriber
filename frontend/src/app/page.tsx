"use client";

import { useState, useEffect, useCallback, useRef } from "react";

import { motion, AnimatePresence } from "framer-motion";
import {
  History, ChevronRight, Brain, Clock,
  MessageSquare, Cpu, Activity, CheckCircle2, Trash2, LogOut, Shield,
  Filter, ArrowUpDown, Loader2, Search
} from "lucide-react";
import { UploadZone } from "@/components/UploadZone";
import { ProcessingPanel } from "@/components/ProcessingPanel";
import { ConversationView } from "@/components/ConversationView";
import { LoginForm } from "@/components/LoginForm";
import { AdminPanel } from "@/components/AdminPanel";
import { DashboardPanel } from "@/components/DashboardPanel";
import LGPDPanel from "@/components/LGPDPanel";
import { buildWebSocketUrl, buildApiUrl, getCurrentUser, getProgress, getToken, listConversations } from "@/lib/api";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useTheme } from "@/lib/theme";
import { useAppStore } from "@/lib/store";
import {
  useConversations,
  useDeleteConversation,
  useUploadConversation,
} from "@/lib/queries";
import { cn, formatRelative } from "@/lib/utils";
import toast from "react-hot-toast";

const POLL_INTERVAL = 2000;
const PAGE_SIZE = 20;

export default function Home() {
  const {
    isAuthenticated,
    checkAuthentication,
    logout,
    setAuthenticated,
    uiState,
    setUIState,
    navigateHome,
    navigateToProcessing,
    navigateToConversation,
    isUploading,
    setIsUploading,
    progress,
    setProgress,
    recentConversations,
    setRecentConversations,
    removeConversation,
  } = useAppStore();

  // Initialize theme
  useTheme();

  const [isAdmin, setIsAdmin] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [showDashboard, setShowDashboard] = useState(false);
  const [showLGPD, setShowLGPD] = useState(false);
  const [agentStatus, setAgentStatus] = useState<{ active_agents?: number; status?: string } | null>(null);
  const [sortBy, setSortBy] = useState<"date" | "messages">("date");
  const [searchFilter, setSearchFilter] = useState("");
  const [page, setPage] = useState(0);
  const [hasMoreConversations, setHasMoreConversations] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [allConversations, setAllConversations] = useState<typeof recentConversations>([]);

  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  // ─── Deep linking: read URL parameters ────────────────────────────────────
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const convId = params.get("conversation");
    const sessionId = params.get("session");

    if (convId && isAuthenticated) {
      navigateToConversation(convId);
    } else if (sessionId && isAuthenticated) {
      navigateToProcessing(sessionId);
    }
  }, [isAuthenticated, navigateToConversation, navigateToProcessing]);

  // ─── Update URL when navigation changes ───────────────────────────────────
  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);

    if (uiState.currentView === "conversation" && uiState.selectedConversationId) {
      url.searchParams.set("conversation", uiState.selectedConversationId);
      url.searchParams.delete("session");
    } else if (uiState.currentView === "processing" && uiState.sessionId) {
      url.searchParams.set("session", uiState.sessionId);
      url.searchParams.delete("conversation");
    } else {
      url.searchParams.delete("conversation");
      url.searchParams.delete("session");
    }

    window.history.replaceState({}, "", url.toString());
  }, [uiState]);

  // Query para lista de conversas
  const { data: conversationsData, refetch: refetchConversations } =
    useConversations(0, PAGE_SIZE, !!isAuthenticated);

  // Mutations
  const uploadMutation = useUploadConversation();
  const deleteMutation = useDeleteConversation();

  // Sincronizar dados do React Query com o store + local state
  useEffect(() => {
    if (conversationsData) {
      setRecentConversations(conversationsData);
      setAllConversations(conversationsData);
      setHasMoreConversations(conversationsData.length >= PAGE_SIZE);
    }
  }, [conversationsData, setRecentConversations]);

  // ─── Infinite scroll: load more conversations ─────────────────────────────
  const loadMoreConversations = useCallback(async () => {
    if (loadingMore || !hasMoreConversations) return;
    setLoadingMore(true);
    try {
      const more = await listConversations(allConversations.length, PAGE_SIZE);
      if (more.length > 0) {
        setAllConversations((prev) => [...prev, ...more]);
        setHasMoreConversations(more.length >= PAGE_SIZE);
      } else {
        setHasMoreConversations(false);
      }
    } catch (err) {
      console.error("Error loading more conversations:", err);
    }
    setLoadingMore(false);
  }, [loadingMore, hasMoreConversations, allConversations.length]);

  // Intersection observer for infinite scroll
  useEffect(() => {
    if (observerRef.current) observerRef.current.disconnect();

    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasMoreConversations && !loadingMore) {
          loadMoreConversations();
        }
      },
      { threshold: 0.1 }
    );

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => observerRef.current?.disconnect();
  }, [hasMoreConversations, loadingMore, loadMoreConversations]);

  // ─── Sorted & filtered conversations ──────────────────────────────────────
  const displayConversations = allConversations
    .filter((conv) => {
      if (!searchFilter) return true;
      const q = searchFilter.toLowerCase();
      return (
        (conv.conversation_name || "").toLowerCase().includes(q) ||
        conv.original_filename.toLowerCase().includes(q)
      );
    })
    .sort((a, b) => {
      if (sortBy === "messages") return (b.total_messages || 0) - (a.total_messages || 0);
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

  // Verificar autenticação ao carregar
  useEffect(() => {
    checkAuthentication();
  }, [checkAuthentication]);

  // Verificar se é admin
  useEffect(() => {
    if (isAuthenticated) {
      getCurrentUser()
        .then((user) => setIsAdmin(user.is_admin))
        .catch(() => setIsAdmin(false));
    }
  }, [isAuthenticated]);

  const handleLoginSuccess = useCallback(() => {
    setAuthenticated(true);
    toast.success("Login realizado com sucesso!");
  }, [setAuthenticated]);

  const handleLogout = useCallback(() => {
    logout();
    if (wsRef.current) wsRef.current.close();
    toast.success("Logout realizado.");
  }, [logout]);

  // ─── WebSocket Progress ───────────────────────────────────────────────────
  const connectWebSocket = useCallback((sessionId: string) => {
    if (wsRef.current) wsRef.current.close();

    const token = getToken();
    if (!token) return;

    const wsUrl = buildWebSocketUrl(`/api/ws/progress/${sessionId}?token=${token}`);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "progress") {
            setProgress({
              session_id: data.session_id,
              status: data.status,
              progress: data.progress,
              progress_message: data.message,
              total_messages: data.total_messages || 0,
              processed_messages: 0,
              active_agents: 0,
            });

            if (data.status === "completed") {
              toast.success("Processamento concluido!");
              ws.close();
              listConversations(0, 1).then((convs) => {
                if (convs.length > 0) {
                  setTimeout(() => navigateToConversation(convs[0].id), 1500);
                }
              });
              refetchConversations();
              setIsUploading(false);
            } else if (data.status === "failed") {
              toast.error(`Erro: ${data.message || "Erro desconhecido"}`);
              ws.close();
              setIsUploading(false);
            }
          }
        } catch (err) {
          console.error("[WS] Parse error:", err);
        }
      };

      ws.onerror = () => {
        console.warn("[WS] Error, falling back to polling");
        ws.close();
        startPolling(sessionId);
      };

      ws.onclose = () => {
        wsRef.current = null;
      };
    } catch {
      startPolling(sessionId);
    }
  }, [setProgress, navigateToConversation, refetchConversations, setIsUploading]);

  // Fallback polling
  const startPolling = useCallback((sessionId: string) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    let pollErrors = 0;
    const interval = setInterval(async () => {
      try {
        const prog = await getProgress(sessionId);
        setProgress(prog);
        pollErrors = 0;

        if (prog.status === "completed") {
          clearInterval(interval);
          setIsUploading(false);
          toast.success("Processamento concluido!");
          const convs = await listConversations(0, 1);
          if (convs.length > 0) {
            setTimeout(() => navigateToConversation(convs[0].id), 1500);
          }
          refetchConversations();
        } else if (prog.status === "failed") {
          clearInterval(interval);
          setIsUploading(false);
          toast.error(`Erro: ${prog.progress_message || "Erro desconhecido"}`);
        }
      } catch (err) {
        pollErrors++;
        if (pollErrors >= 10) {
          clearInterval(interval);
          setIsUploading(false);
          toast.error("Conexao perdida. Tente novamente.");
          navigateHome();
        }
      }
    }, POLL_INTERVAL);
    pollingRef.current = interval;
  }, [setProgress, setIsUploading, navigateToConversation, navigateHome, refetchConversations]);

  const handleUpload = useCallback(
    async (file: File) => {
      setIsUploading(true);
      try {
        const response = await uploadMutation.mutateAsync(file);
        navigateToProcessing(response.session_id);
        setProgress({
          session_id: response.session_id,
          status: "uploading",
          progress: 0.02,
          progress_message: "Upload concluido, iniciando processamento...",
          total_messages: 0,
          processed_messages: 0,
          active_agents: 0,
        });
        toast.success("Upload realizado! Processamento com 20 agentes de IA iniciado.");

        // Prefer WebSocket, fallback to polling
        connectWebSocket(response.session_id);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        toast.error(`Erro no upload: ${message}`);
        setIsUploading(false);
        navigateHome();
      }
    },
    [uploadMutation, navigateToProcessing, navigateHome, setIsUploading, setProgress, connectWebSocket]
  );

  // Cleanup
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Remover esta conversa permanentemente?")) return;
    try {
      await deleteMutation.mutateAsync(id);
      removeConversation(id);
      setAllConversations((prev) => prev.filter((c) => c.id !== id));
      toast.success("Conversa removida");
    } catch {
      toast.error("Erro ao remover conversa");
    }
  };

  // ─── Loading State ─────────────────────────────────────────────────────────
  if (isAuthenticated === null) {
    return (
      <main className="min-h-screen flex items-center justify-center" role="main" aria-busy="true">
        <div className="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" role="status" aria-label="Carregando..." />
      </main>
    );
  }

  // ─── Login ─────────────────────────────────────────────────────────────────
  if (!isAuthenticated) {
    return (
      <main className="min-h-screen" role="main">
        <ErrorBoundary>
          <LoginForm onLoginSuccess={handleLoginSuccess} />
        </ErrorBoundary>
      </main>
    );
  }

  // ─── Admin Panel ───────────────────────────────────────────────────────────
  if (showAdmin && isAdmin) {
    return (
      <ErrorBoundary>
        <AdminPanel onBack={() => setShowAdmin(false)} />
      </ErrorBoundary>
    );
  }

  // ─── Conversation View ─────────────────────────────────────────────────────
  if (uiState.currentView === "conversation" && uiState.selectedConversationId) {
    return (
      <ErrorBoundary>
        <ConversationView
          conversationId={uiState.selectedConversationId}
          onBack={() => {
            navigateHome();
            refetchConversations();
          }}
        />
      </ErrorBoundary>
    );
  }

  return (
    <main className="min-h-screen" role="main">
      {/* Navigation Header */}
      <nav className="glass-dark border-b border-brand-500/10 px-6 py-4 sticky top-0 z-30" role="navigation" aria-label="Navegacao principal">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-3"
          >
            <div className="w-9 h-9 rounded-xl bg-gradient-brand flex items-center justify-center shadow-brand" aria-hidden="true">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-white text-sm leading-none">WhatsApp Insight</h1>
              <p className="text-[10px] text-brand-400 leading-none mt-0.5">Transcriber</p>
            </div>
          </motion.div>

          {/* Status + Theme + Logout */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-accent-400" aria-label="Status dos agentes">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-pulse" aria-hidden="true" />
              <span className="hidden sm:inline">{agentStatus?.active_agents ?? 20} Agentes Online</span>
            </div>
            <div className="text-xs text-gray-500 hidden md:block" aria-hidden="true">
              Claude Opus 4.6
            </div>
            <button
              onClick={() => setShowDashboard(true)}
              className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs text-gray-400 hover:text-brand-300 hover:bg-brand-500/10 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              aria-label="Dashboard de uso"
            >
              <Activity className="w-3.5 h-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">Dashboard</span>
            </button>
            <button
              onClick={() => setShowLGPD(true)}
              className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs text-gray-400 hover:text-brand-300 hover:bg-brand-500/10 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              aria-label="Privacidade e dados"
            >
              <Shield className="w-3.5 h-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">LGPD</span>
            </button>
            <ThemeToggle />
            {isAdmin && (
              <button
                onClick={() => setShowAdmin(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-brand-400 hover:text-brand-300 hover:bg-brand-500/10 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                aria-label="Painel de administracao"
              >
                <Shield className="w-3.5 h-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">Admin</span>
              </button>
            )}
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              aria-label="Sair da conta"
            >
              <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">Sair</span>
            </button>
          </div>
        </div>
      </nav>

      <AnimatePresence mode="wait">
        {uiState.currentView === "processing" ? (
          <motion.div
            key="processing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="max-w-3xl mx-auto px-6 py-12"
          >
            <ErrorBoundary>
              <ProcessingPanel
                progress={progress}
                sessionId={uiState.sessionId || ""}
              />
            </ErrorBoundary>
          </motion.div>
        ) : (
          <motion.div
            key="home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12"
          >
            {/* Hero */}
            <div className="text-center mb-12">
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.1 }}
              >
                {/* Glowing orb */}
                <div className="relative inline-block mb-6">
                  <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-3xl bg-gradient-brand flex items-center justify-center shadow-glow mx-auto">
                    <Brain className="w-10 h-10 sm:w-12 sm:h-12 text-white" />
                  </div>
                  <div className="absolute -inset-1 rounded-3xl bg-gradient-brand opacity-20 blur-xl" />
                  {[0, 120, 240].map((deg) => (
                    <div
                      key={deg}
                      className="absolute w-2 h-2 rounded-full bg-accent-400 top-1/2 left-1/2 hidden sm:block"
                      style={{
                        transform: `rotate(${deg}deg) translateX(50px) translateY(-50%) rotate(-${deg}deg)`,
                        boxShadow: "0 0 6px #00d4aa",
                      }}
                    />
                  ))}
                </div>

                <h1 className="text-3xl sm:text-4xl md:text-5xl font-black mb-4">
                  <span className="text-gradient">WhatsApp</span>{" "}
                  <span className="text-white">Insight Transcriber</span>
                </h1>
                <p className="text-gray-400 text-base sm:text-lg max-w-2xl mx-auto">
                  Transcreva e analise suas conversas do WhatsApp com{" "}
                  <span className="text-accent-400">20 agentes de IA</span> em paralelo.
                  Audios, videos, imagens — tudo processado com{" "}
                  <span className="text-brand-400">Claude Opus 4.6</span>.
                </p>
              </motion.div>

              {/* Feature Pills */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="flex flex-wrap justify-center gap-2 mt-6"
              >
                {[
                  { icon: "🎵", label: "Transcricao" },
                  { icon: "🖼️", label: "Visao Computacional" },
                  { icon: "🎬", label: "Video" },
                  { icon: "💬", label: "Chat RAG" },
                  { icon: "📊", label: "Sentimento" },
                  { icon: "🔗", label: "Custodia" },
                  { icon: "📄", label: "Export 6 formatos" },
                ].map((feat) => (
                  <span
                    key={feat.label}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-full glass text-xs text-gray-300"
                  >
                    <span>{feat.icon}</span>
                    {feat.label}
                  </span>
                ))}
              </motion.div>
            </div>

            {/* Upload Zone */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <ErrorBoundary>
                <UploadZone onUpload={handleUpload} isUploading={isUploading} />
              </ErrorBoundary>
            </motion.div>

            {/* Stats */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="grid grid-cols-3 gap-3 sm:gap-4 mt-8 max-w-lg mx-auto"
            >
              {[
                { label: "Agentes", value: "20", icon: Cpu, color: "brand" },
                { label: "Modelo", value: "Claude", icon: Brain, color: "accent" },
                { label: "Formatos", value: "6 tipos", icon: Activity, color: "brand" },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label} className="glass rounded-2xl p-3 sm:p-4 text-center">
                  <Icon
                    className={cn(
                      "w-5 h-5 mx-auto mb-2",
                      color === "accent" ? "text-accent-400" : "text-brand-400"
                    )}
                  />
                  <p className="font-bold text-white text-sm sm:text-base">{value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                </div>
              ))}
            </motion.div>

            {/* Recent Conversations with infinite scroll */}
            {displayConversations.length > 0 || searchFilter ? (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                className="mt-12"
              >
                {/* Header with search and sort */}
                <div className="flex items-center gap-2 mb-4 flex-wrap">
                  <History className="w-5 h-5 text-brand-400 shrink-0" />
                  <h2 className="font-bold text-gray-200">Conversas</h2>
                  <span className="text-xs text-gray-600">({displayConversations.length})</span>

                  <div className="flex-1" />

                  {/* Search filter */}
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
                    <input
                      type="text"
                      value={searchFilter}
                      onChange={(e) => setSearchFilter(e.target.value)}
                      placeholder="Filtrar..."
                      className="bg-dark-700 border border-dark-500/30 rounded-lg pl-8 pr-3 py-1.5 text-xs text-gray-300 w-36 sm:w-48 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 placeholder-gray-600"
                      aria-label="Filtrar conversas"
                    />
                  </div>

                  {/* Sort toggle */}
                  <button
                    onClick={() => setSortBy(sortBy === "date" ? "messages" : "date")}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-dark-700 border border-dark-500/30 text-xs text-gray-400 hover:text-gray-200 transition-colors"
                    aria-label={`Ordenar por ${sortBy === "date" ? "mensagens" : "data"}`}
                  >
                    <ArrowUpDown className="w-3 h-3" />
                    {sortBy === "date" ? "Data" : "Msgs"}
                  </button>
                </div>

                {/* Conversations list */}
                <div className="grid gap-3" role="list" aria-label="Lista de conversas">
                  {displayConversations.map((conv) => (
                    <motion.button
                      key={conv.id}
                      whileHover={{ scale: 1.01, x: 4 }}
                      onClick={() => navigateToConversation(conv.id)}
                      className="glass rounded-2xl p-4 text-left w-full hover:border-brand-500/30 transition-all group focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                      role="listitem"
                      aria-label={`Abrir conversa: ${conv.conversation_name || conv.original_filename}, ${conv.total_messages} mensagens`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-white truncate">
                              {conv.conversation_name || conv.original_filename}
                            </p>
                            {conv.status === "completed" && (
                              <CheckCircle2 className="w-4 h-4 text-accent-400 shrink-0" aria-label="Concluida" />
                            )}
                            {conv.status === "processing" && (
                              <Loader2 className="w-4 h-4 text-brand-400 shrink-0 animate-spin" aria-label="Processando" />
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-xs text-gray-500 mt-1.5 flex-wrap">
                            <span className="flex items-center gap-1">
                              <MessageSquare className="w-3 h-3" aria-hidden="true" />
                              {conv.total_messages} msgs
                            </span>
                            {conv.total_media > 0 && (
                              <span className="flex items-center gap-1">
                                📎 {conv.total_media} midias
                              </span>
                            )}
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" aria-hidden="true" />
                              {formatRelative(conv.created_at)}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => handleDeleteConversation(conv.id, e)}
                            className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1.5 rounded-lg hover:bg-red-500/20 text-gray-600 hover:text-red-400 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                            aria-label={`Remover conversa: ${conv.conversation_name || conv.original_filename}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                          </button>
                          <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-brand-400 transition-colors" aria-hidden="true" />
                        </div>
                      </div>
                    </motion.button>
                  ))}
                </div>

                {/* Infinite scroll trigger */}
                {hasMoreConversations && (
                  <div ref={loadMoreRef} className="flex justify-center py-6">
                    {loadingMore && (
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Carregando mais conversas...
                      </div>
                    )}
                  </div>
                )}

                {/* Empty search state */}
                {searchFilter && displayConversations.length === 0 && (
                  <div className="text-center py-8 text-gray-500">
                    <Search className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">Nenhuma conversa encontrada para "{searchFilter}"</p>
                  </div>
                )}
              </motion.div>
            ) : null}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Dashboard Modal */}
      <AnimatePresence>
        {showDashboard && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => setShowDashboard(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-4xl max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <DashboardPanel onClose={() => setShowDashboard(false)} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* LGPD Modal — LGPDPanel provides its own modal overlay */}
      <AnimatePresence>
        {showLGPD && (
          <LGPDPanel onClose={() => setShowLGPD(false)} />
        )}
      </AnimatePresence>
    </main>
  );
}
