"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft, MessageSquare, BarChart2, FileDown,
  Search, Loader2, RefreshCw, Users, ChevronDown, Clock, Grid3X3
} from "lucide-react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useConversation, useMessages } from "@/lib/queries";
import { getMessages } from "@/lib/api";
import type { Conversation, Message } from "@/types";
import { MessageBubble } from "@/components/MessageBubble";
import { ChatPanel } from "@/components/ChatPanel";
import { AnalyticsPanel } from "@/components/AnalyticsPanel";
import { ExportPanel } from "@/components/ExportPanel";
import { SearchBar } from "@/components/SearchBar";
import { TimelineView } from "@/components/TimelineView";
import { ActivityHeatmap } from "@/components/ActivityHeatmap";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { cn, getSentimentEmoji, getSentimentColorHex } from "@/lib/utils";

interface ConversationViewProps {
  conversationId: string;
  onBack: () => void;
}

type SidePanel = "none" | "chat" | "analytics" | "export" | "timeline" | "heatmap";

export function ConversationView({ conversationId, onBack }: ConversationViewProps) {
  const [allMessages, setAllMessages] = useState<Message[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [sidePanel, setSidePanel] = useState<SidePanel>("none");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSender, setFilterSender] = useState<string | null>(null);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const parentRef = useRef<HTMLDivElement>(null);
  const PAGE_SIZE = 100;

  // React Query para dados da conversa
  const { data: conversation, isLoading: convLoading } = useConversation(conversationId);

  // React Query para primeira página de mensagens
  const { data: initialMessages, isLoading: msgsLoading } = useMessages(
    conversationId,
    0,
    PAGE_SIZE,
    filterSender || undefined,
    !!conversationId
  );

  const loading = convLoading || msgsLoading;

  // Sincronizar mensagens iniciais
  useEffect(() => {
    if (initialMessages) {
      setAllMessages(initialMessages);
      setHasMore(initialMessages.length === PAGE_SIZE);
    }
  }, [initialMessages]);

  // Reset quando filtro muda
  useEffect(() => {
    setAllMessages([]);
  }, [filterSender]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const msgs = await getMessages(
        conversationId,
        allMessages.length,
        PAGE_SIZE,
        false,
        filterSender || undefined
      );
      setAllMessages((prev) => [...prev, ...msgs]);
      setHasMore(msgs.length === PAGE_SIZE);
    } catch (err) {
      console.error("Erro ao carregar mais mensagens:", err);
    }
    setLoadingMore(false);
  }, [conversationId, allMessages.length, filterSender, loadingMore, hasMore]);

  // Filtro de busca
  const filteredMessages = useMemo(() => {
    if (!searchQuery) return allMessages;
    const searchLower = searchQuery.toLowerCase();
    return allMessages.filter((m) =>
      m.original_text?.toLowerCase().includes(searchLower) ||
      m.transcription?.toLowerCase().includes(searchLower) ||
      m.description?.toLowerCase().includes(searchLower) ||
      m.ocr_text?.toLowerCase().includes(searchLower) ||
      m.sender.toLowerCase().includes(searchLower)
    );
  }, [allMessages, searchQuery]);

  // Agrupar mensagens por data para exibição virtual
  const virtualItems = useMemo(() => {
    const items: Array<{ type: "date"; date: string } | { type: "message"; message: Message }> = [];
    let currentDate = "";
    for (const msg of filteredMessages) {
      try {
        const msgDate = new Date(msg.timestamp).toLocaleDateString("pt-BR");
        if (msgDate !== currentDate) {
          currentDate = msgDate;
          items.push({ type: "date", date: msgDate });
        }
      } catch {
        if (items.length === 0) {
          items.push({ type: "date", date: "—" });
        }
      }
      items.push({ type: "message", message: msg });
    }
    return items;
  }, [filteredMessages]);

  // Virtualizer
  const virtualizer = useVirtualizer({
    count: virtualItems.length + (hasMore ? 1 : 0), // +1 for load more button
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => {
      if (index >= virtualItems.length) return 50; // load more button
      const item = virtualItems[index];
      return item.type === "date" ? 40 : 80;
    },
    overscan: 20,
  });

  // Detectar scroll position para "scroll to bottom"
  const handleScroll = useCallback(() => {
    const el = parentRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollToBottom(distFromBottom > 300);
  }, []);

  useEffect(() => {
    const el = parentRef.current;
    if (!el) return;
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  const scrollToBottom = useCallback(() => {
    const el = parentRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, []);

  // Auto-scroll quando novas mensagens chegam
  const prevMessageCount = useRef(0);
  useEffect(() => {
    if (allMessages.length > prevMessageCount.current && !showScrollToBottom) {
      scrollToBottom();
    }
    prevMessageCount.current = allMessages.length;
  }, [allMessages.length, showScrollToBottom, scrollToBottom]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto rounded-full border-2 border-transparent border-t-brand-500 animate-spin mb-4" />
          <p className="text-gray-400">Carregando conversa...</p>
        </div>
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <p className="text-gray-400">Conversa não encontrada</p>
          <button onClick={onBack} className="mt-4 text-brand-400 hover:text-brand-300">
            Voltar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden" role="main">
      {/* Main Content */}
      <div
        className={cn(
          "flex-1 flex flex-col transition-all duration-300",
          sidePanel !== "none" ? "mr-[400px]" : ""
        )}
      >
        {/* Header */}
        <header className="glass-dark border-b border-brand-500/10 px-4 py-3 flex items-center gap-3 shrink-0">
          <button
            onClick={onBack}
            aria-label="Voltar para a página inicial"
            className="p-2 rounded-xl hover:bg-dark-600 text-gray-400 hover:text-white transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <ArrowLeft className="w-5 h-5" aria-hidden="true" />
          </button>

          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-white truncate">
              {conversation.conversation_name || conversation.original_filename}
            </h1>
            <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
              <span className="flex items-center gap-1">
                <Users className="w-3 h-3" aria-hidden="true" />
                {conversation.participants?.join(", ")}
              </span>
              <span className="flex items-center gap-1">
                <MessageSquare className="w-3 h-3" aria-hidden="true" />
                {conversation.total_messages} mensagens
              </span>
              {conversation.sentiment_overall && (
                <span
                  className="flex items-center gap-1"
                  style={{ color: getSentimentColorHex(conversation.sentiment_overall) }}
                  aria-label={`Sentimento geral: ${conversation.sentiment_overall}`}
                >
                  {getSentimentEmoji(conversation.sentiment_overall)}
                </span>
              )}
            </div>
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-2" role="toolbar" aria-label="Ferramentas da conversa">
            {/* Advanced Search */}
            <SearchBar
              conversationId={conversationId}
              participants={conversation.participants || []}
            />

            {/* Action Buttons */}
            {[
              { id: "analytics" as SidePanel, icon: BarChart2, label: "Análises", color: "accent" },
              { id: "timeline" as SidePanel, icon: Clock, label: "Timeline", color: "brand" },
              { id: "heatmap" as SidePanel, icon: Grid3X3, label: "Heatmap", color: "brand" },
              { id: "chat" as SidePanel, icon: MessageSquare, label: "Chat IA", color: "brand" },
              { id: "export" as SidePanel, icon: FileDown, label: "Exportar", color: "brand" },
            ].map(({ id, icon: Icon, label, color }) => (
              <button
                key={id}
                onClick={() => setSidePanel(sidePanel === id ? "none" : id)}
                aria-label={`${sidePanel === id ? "Fechar" : "Abrir"} painel de ${label}`}
                aria-pressed={sidePanel === id}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                  sidePanel === id
                    ? color === "accent"
                      ? "bg-accent-400/15 border border-accent-400/30 text-accent-300"
                      : "bg-brand-500/15 border border-brand-500/30 text-brand-300"
                    : "bg-dark-700 border border-dark-500/20 text-gray-400 hover:text-gray-200"
                )}
              >
                <Icon className="w-3.5 h-3.5" aria-hidden="true" />
                <span className="hidden md:inline">{label}</span>
              </button>
            ))}
          </div>
        </header>

        {/* Filter bar */}
        <AnimatePresence>
          {conversation.participants && conversation.participants.length > 1 && (
            <motion.div
              initial={{ height: 0 }}
              animate={{ height: "auto" }}
              className="px-4 py-2 border-b border-dark-500/20 flex items-center gap-2 overflow-x-auto"
              role="toolbar"
              aria-label="Filtrar mensagens por participante"
            >
              <span className="text-xs text-gray-500 shrink-0" id="filter-label">Filtrar por:</span>
              <button
                onClick={() => setFilterSender(null)}
                aria-pressed={!filterSender}
                className={cn(
                  "px-2.5 py-1 rounded-full text-xs transition-colors shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                  !filterSender ? "bg-brand-500/20 text-brand-300" : "text-gray-500 hover:text-gray-300"
                )}
              >
                Todos
              </button>
              {conversation.participants.map((p) => (
                <button
                  key={p}
                  onClick={() => setFilterSender(filterSender === p ? null : p)}
                  aria-pressed={filterSender === p}
                  className={cn(
                    "px-2.5 py-1 rounded-full text-xs transition-colors shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                    filterSender === p
                      ? "bg-accent-400/20 text-accent-300"
                      : "text-gray-500 hover:text-gray-300"
                  )}
                >
                  {p.split(" ")[0]}
                </button>
              ))}
              {searchQuery && (
                <span className="ml-auto text-xs text-brand-400" aria-live="polite">
                  {filteredMessages.length} resultado(s)
                </span>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Virtualized Messages */}
        <div
          ref={parentRef}
          className="flex-1 overflow-y-auto px-4 py-4"
          role="log"
          aria-label="Mensagens da conversa"
        >
          {filteredMessages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-gray-500">
                <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>
                  {searchQuery ? "Nenhuma mensagem encontrada" : "Sem mensagens para exibir"}
                </p>
              </div>
            </div>
          ) : (
            <div
              style={{
                height: `${virtualizer.getTotalSize()}px`,
                width: "100%",
                position: "relative",
              }}
            >
              {virtualizer.getVirtualItems().map((virtualRow) => {
                const index = virtualRow.index;

                // Load more button
                if (index >= virtualItems.length) {
                  return (
                    <div
                      key="load-more"
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        width: "100%",
                        height: `${virtualRow.size}px`,
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                    >
                      <div className="flex justify-center py-4">
                        <button
                          onClick={loadMore}
                          disabled={loadingMore}
                          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-dark-700 hover:bg-dark-600 text-gray-400 hover:text-gray-200 text-sm transition-all"
                        >
                          {loadingMore ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <RefreshCw className="w-4 h-4" />
                          )}
                          Carregar mais mensagens
                        </button>
                      </div>
                    </div>
                  );
                }

                const item = virtualItems[index];

                if (item.type === "date") {
                  return (
                    <div
                      key={`date-${item.date}`}
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        width: "100%",
                        height: `${virtualRow.size}px`,
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                    >
                      <div className="flex items-center gap-3 py-3">
                        <div className="flex-1 h-px bg-dark-500/30" />
                        <span className="text-[10px] text-gray-600 px-2 py-0.5 rounded-full bg-dark-700/50 border border-dark-500/20">
                          {item.date}
                        </span>
                        <div className="flex-1 h-px bg-dark-500/30" />
                      </div>
                    </div>
                  );
                }

                return (
                  <div
                    key={item.message.id}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    <MessageBubble
                      message={item.message}
                      conversationId={conversationId}
                      participants={conversation.participants || []}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Scroll to bottom indicator */}
        <AnimatePresence>
          {showScrollToBottom && (
            <motion.button
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              onClick={scrollToBottom}
              aria-label="Rolar para o final das mensagens"
              className="absolute bottom-6 right-6 z-20 w-10 h-10 rounded-full bg-brand-500 hover:bg-brand-400 text-white shadow-brand flex items-center justify-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              style={{ position: "fixed", bottom: 24, right: sidePanel !== "none" ? 424 : 24 }}
            >
              <ChevronDown className="w-5 h-5" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Side Panels */}
      <AnimatePresence>
        {sidePanel !== "none" && sidePanel !== "chat" && (
          <motion.div
            key={sidePanel}
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 w-[400px] glass-dark border-l border-brand-500/20 z-40 overflow-y-auto"
            role="complementary"
            aria-label={
              sidePanel === "analytics" ? "Painel de análises" :
              sidePanel === "timeline" ? "Timeline da conversa" :
              sidePanel === "heatmap" ? "Heatmap de atividade" :
              "Painel de exportação"
            }
          >
            <div className="p-4">
              {sidePanel === "analytics" && (
                <ErrorBoundary>
                  <AnalyticsPanel conversation={conversation} />
                </ErrorBoundary>
              )}
              {sidePanel === "timeline" && (
                <ErrorBoundary>
                  <TimelineView
                    messages={allMessages}
                    participants={conversation.participants || []}
                  />
                </ErrorBoundary>
              )}
              {sidePanel === "heatmap" && (
                <ErrorBoundary>
                  <ActivityHeatmap messages={allMessages} />
                </ErrorBoundary>
              )}
              {sidePanel === "export" && (
                <ErrorBoundary>
                  <ExportPanel conversationId={conversationId} />
                </ErrorBoundary>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Chat Panel */}
      <ErrorBoundary>
        <ChatPanel
          conversationId={conversationId}
          isOpen={sidePanel === "chat"}
          onClose={() => setSidePanel("none")}
        />
      </ErrorBoundary>
    </div>
  );
}
