"use client";

import { useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  History, ChevronRight, Brain, Clock,
  MessageSquare, Cpu, Activity, CheckCircle2, Trash2, LogOut
} from "lucide-react";
import { UploadZone } from "@/components/UploadZone";
import { ProcessingPanel } from "@/components/ProcessingPanel";
import { ConversationView } from "@/components/ConversationView";
import { LoginForm } from "@/components/LoginForm";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useTheme } from "@/lib/theme";
import { useAppStore } from "@/lib/store";
import {
  useConversations,
  useDeleteConversation,
  useUploadConversation,
} from "@/lib/queries";
import { getProgress, listConversations } from "@/lib/api";
import { cn, formatRelative } from "@/lib/utils";
import toast from "react-hot-toast";

const POLL_INTERVAL = 2000;

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

  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Query para lista de conversas
  const { data: conversationsData, refetch: refetchConversations } =
    useConversations(0, 10, !!isAuthenticated);

  // Mutations
  const uploadMutation = useUploadConversation();
  const deleteMutation = useDeleteConversation();

  // Sincronizar dados do React Query com o store
  useEffect(() => {
    if (conversationsData) {
      setRecentConversations(conversationsData);
    }
  }, [conversationsData, setRecentConversations]);

  // Verificar autenticação ao carregar
  useEffect(() => {
    checkAuthentication();
  }, [checkAuthentication]);

  const handleLoginSuccess = useCallback(() => {
    setAuthenticated(true);
    toast.success("Login realizado com sucesso!");
  }, [setAuthenticated]);

  const handleLogout = useCallback(() => {
    logout();
    toast.success("Logout realizado.");
  }, [logout]);

  const handleUpload = useCallback(
    async (file: File) => {
      console.log("[Upload] Iniciando upload do arquivo:", file.name, file.size);
      setIsUploading(true);

      try {
        const response = await uploadMutation.mutateAsync(file);
        console.log("[Upload] Resposta do servidor:", response);

        navigateToProcessing(response.session_id);
        setProgress({
          session_id: response.session_id,
          status: "uploading",
          progress: 0.02,
          progress_message: "Upload concluído, iniciando processamento...",
          total_messages: 0,
          processed_messages: 0,
          active_agents: 0,
        });
        toast.success("Upload realizado! Iniciando processamento com 20 agentes de IA...");

        // Iniciar polling do progresso
        let pollErrors = 0;
        const interval = setInterval(async () => {
          try {
            const prog = await getProgress(response.session_id);
            console.log("[Polling] Progresso:", prog.status, prog.progress);
            setProgress(prog);
            pollErrors = 0;

            if (prog.status === "completed") {
              clearInterval(interval);
              setIsUploading(false);
              toast.success("Processamento concluído!");
              const convs = await listConversations(0, 1);
              if (convs.length > 0) {
                setTimeout(() => {
                  navigateToConversation(convs[0].id);
                }, 1500);
              }
              refetchConversations();
            } else if (prog.status === "failed") {
              clearInterval(interval);
              setIsUploading(false);
              toast.error(`Erro no processamento: ${prog.progress_message || "Erro desconhecido"}`);
            }
          } catch (err) {
            pollErrors++;
            console.error(`[Polling] Erro #${pollErrors}:`, err);
            if (pollErrors >= 10) {
              clearInterval(interval);
              setIsUploading(false);
              toast.error("Conexão perdida com o servidor. Verifique e tente novamente.");
              navigateHome();
            }
          }
        }, POLL_INTERVAL);

        pollingRef.current = interval;
      } catch (err: unknown) {
        console.error("[Upload] Erro:", err);
        const message = err instanceof Error ? err.message : String(err);
        toast.error(`Erro no upload: ${message}`);
        setIsUploading(false);
        navigateHome();
      }
    },
    [uploadMutation, navigateToProcessing, navigateToConversation, navigateHome, setIsUploading, setProgress, refetchConversations]
  );

  // Cleanup polling
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Remover esta conversa permanentemente?")) return;
    try {
      await deleteMutation.mutateAsync(id);
      removeConversation(id);
      toast.success("Conversa removida");
    } catch {
      toast.error("Erro ao remover conversa");
    }
  };

  // ─── Loading State ─────────────────────────────────────────────────────────
  if (isAuthenticated === null) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
      </main>
    );
  }

  // ─── Login ─────────────────────────────────────────────────────────────────
  if (!isAuthenticated) {
    return (
      <main className="min-h-screen">
        <ErrorBoundary>
          <LoginForm onLoginSuccess={handleLoginSuccess} />
        </ErrorBoundary>
      </main>
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
    <main className="min-h-screen">
      {/* Navigation Header */}
      <nav className="glass-dark border-b border-brand-500/10 px-6 py-4 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-3"
          >
            <div className="w-9 h-9 rounded-xl bg-gradient-brand flex items-center justify-center shadow-brand">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-white text-sm leading-none">WhatsApp Insight</h1>
              <p className="text-[10px] text-brand-400 leading-none mt-0.5">Transcriber</p>
            </div>
          </motion.div>

          {/* Status + Logout */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-accent-400">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-pulse" />
              <span className="hidden sm:inline">20 Agentes Online</span>
            </div>
            <div className="text-xs text-gray-500">
              Claude Opus 4.6
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
              title="Sair"
            >
              <LogOut className="w-3.5 h-3.5" />
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
            className="max-w-6xl mx-auto px-6 py-12"
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
                  <div className="w-24 h-24 rounded-3xl bg-gradient-brand flex items-center justify-center shadow-glow mx-auto">
                    <Brain className="w-12 h-12 text-white" />
                  </div>
                  <div className="absolute -inset-1 rounded-3xl bg-gradient-brand opacity-20 blur-xl" />
                  {/* Orbiting dots */}
                  {[0, 120, 240].map((deg) => (
                    <div
                      key={deg}
                      className="absolute w-2 h-2 rounded-full bg-accent-400 top-1/2 left-1/2"
                      style={{
                        transform: `rotate(${deg}deg) translateX(50px) translateY(-50%) rotate(-${deg}deg)`,
                        boxShadow: "0 0 6px #00d4aa",
                      }}
                    />
                  ))}
                </div>

                <h1 className="text-4xl md:text-5xl font-black mb-4">
                  <span className="text-gradient">WhatsApp</span>{" "}
                  <span className="text-white">Insight Transcriber</span>
                </h1>
                <p className="text-gray-400 text-lg max-w-2xl mx-auto">
                  Transcreva e analise suas conversas do WhatsApp com{" "}
                  <span className="text-accent-400">20 agentes de IA</span> em paralelo.
                  Áudios, vídeos, imagens — tudo processado com{" "}
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
                  { icon: "🎵", label: "Transcrição de Áudio" },
                  { icon: "🖼️", label: "Visão Computacional" },
                  { icon: "🎬", label: "Análise de Vídeo" },
                  { icon: "💬", label: "Chat RAG" },
                  { icon: "📊", label: "Análise de Sentimento" },
                  { icon: "📄", label: "Export PDF/DOCX" },
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
              className="grid grid-cols-3 gap-4 mt-8 max-w-lg mx-auto"
            >
              {[
                { label: "Agentes Paralelos", value: "20", icon: Cpu, color: "brand" },
                { label: "Modelo", value: "Claude", icon: Brain, color: "accent" },
                { label: "Formatos", value: "PDF+DOCX", icon: Activity, color: "brand" },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label} className="glass rounded-2xl p-4 text-center">
                  <Icon
                    className={cn(
                      "w-5 h-5 mx-auto mb-2",
                      color === "accent" ? "text-accent-400" : "text-brand-400"
                    )}
                  />
                  <p className="font-bold text-white">{value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                </div>
              ))}
            </motion.div>

            {/* Recent Conversations */}
            {recentConversations.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                className="mt-12"
              >
                <div className="flex items-center gap-2 mb-4">
                  <History className="w-5 h-5 text-brand-400" />
                  <h2 className="font-bold text-gray-200">Conversas Recentes</h2>
                </div>
                <div className="grid gap-3">
                  {recentConversations.map((conv) => (
                    <motion.button
                      key={conv.id}
                      whileHover={{ scale: 1.01, x: 4 }}
                      onClick={() => navigateToConversation(conv.id)}
                      className="glass rounded-2xl p-4 text-left w-full hover:border-brand-500/30 transition-all group"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-white truncate">
                              {conv.conversation_name || conv.original_filename}
                            </p>
                            {conv.status === "completed" && (
                              <CheckCircle2 className="w-4 h-4 text-accent-400 shrink-0" />
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-xs text-gray-500 mt-1.5">
                            <span className="flex items-center gap-1">
                              <MessageSquare className="w-3 h-3" />
                              {conv.total_messages} msgs
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {formatRelative(conv.created_at)}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => handleDeleteConversation(conv.id, e)}
                            className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-500/20 text-gray-600 hover:text-red-400 transition-all"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                          <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-brand-400 transition-colors" />
                        </div>
                      </div>
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
