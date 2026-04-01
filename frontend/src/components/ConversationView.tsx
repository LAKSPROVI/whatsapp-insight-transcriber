"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft, MessageSquare, BarChart2, FileDown,
  Search, Filter, ChevronDown, Cpu, ExternalLink,
  Loader2, RefreshCw, Users, Calendar, Clock
} from "lucide-react";
import { getConversation, getMessages } from "@/lib/api";
import type { Conversation, Message } from "@/types";
import { MessageBubble } from "@/components/MessageBubble";
import { ChatPanel } from "@/components/ChatPanel";
import { AnalyticsPanel } from "@/components/AnalyticsPanel";
import { ExportPanel } from "@/components/ExportPanel";
import { cn, formatDate, formatDateShort, getSentimentEmoji, getSentimentColor, getSentimentColorHex } from "@/lib/utils";

interface ConversationViewProps {
  conversationId: string;
  onBack: () => void;
}

type SidePanel = "none" | "chat" | "analytics" | "export";

export function ConversationView({ conversationId, onBack }: ConversationViewProps) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [sidePanel, setSidePanel] = useState<SidePanel>("none");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSender, setFilterSender] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const PAGE_SIZE = 100;

  const loadMessages = useCallback(
    async (skip = 0, append = false) => {
      try {
        const msgs = await getMessages(
          conversationId,
          skip,
          PAGE_SIZE,
          false,
          filterSender || undefined
        );

        if (append) {
          setMessages((prev) => [...prev, ...msgs]);
        } else {
          setMessages(msgs);
        }
        setHasMore(msgs.length === PAGE_SIZE);
      } catch (err) {
        console.error("Erro ao carregar mensagens:", err);
      }
    },
    [conversationId, filterSender]
  );

  // Effect 1: Carregar dados da conversa (só quando conversationId muda)
  useEffect(() => {
    if (conversationId) {
      setLoading(true);
      getConversation(conversationId)
        .then((conv) => {
          if (conv) setConversation(conv);
        })
        .catch((err) => console.error("Erro ao carregar conversa:", err));
    }
  }, [conversationId]);

  // Effect 2: Carregar mensagens (quando conversationId ou filtro/loadMessages muda)
  useEffect(() => {
    if (conversationId) {
      loadMessages(0, false).finally(() => setLoading(false));
    }
  }, [conversationId, loadMessages]);

  const loadMore = async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    await loadMessages(messages.length, true);
    setLoadingMore(false);
  };

  const filteredMessages = searchQuery
    ? messages.filter((m) => {
        const searchLower = searchQuery.toLowerCase();
        return (
          m.original_text?.toLowerCase().includes(searchLower) ||
          m.transcription?.toLowerCase().includes(searchLower) ||
          m.description?.toLowerCase().includes(searchLower) ||
          m.ocr_text?.toLowerCase().includes(searchLower) ||
          m.sender.toLowerCase().includes(searchLower)
        );
      })
    : messages;

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
    <div className="flex h-screen overflow-hidden">
      {/* Main Content */}
      <div
        className={cn(
          "flex-1 flex flex-col transition-all duration-300",
          sidePanel !== "none" ? "mr-[400px]" : ""
        )}
      >
        {/* Header */}
        <div className="glass-dark border-b border-brand-500/10 px-4 py-3 flex items-center gap-3 shrink-0">
          <button
            onClick={onBack}
            className="p-2 rounded-xl hover:bg-dark-600 text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>

          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-white truncate">
              {conversation.conversation_name || conversation.original_filename}
            </h1>
            <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
              <span className="flex items-center gap-1">
                <Users className="w-3 h-3" />
                {conversation.participants?.join(", ")}
              </span>
              <span className="flex items-center gap-1">
                <MessageSquare className="w-3 h-3" />
                {conversation.total_messages} mensagens
              </span>
              {conversation.sentiment_overall && (
                <span
                  className="flex items-center gap-1"
                  style={{ color: getSentimentColorHex(conversation.sentiment_overall) }}
                >
                  {getSentimentEmoji(conversation.sentiment_overall)}
                </span>
              )}
            </div>
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
              <input
                type="text"
                placeholder="Buscar..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-40 bg-dark-700 border border-dark-500/30 rounded-xl pl-8 pr-3 py-2 text-xs text-gray-200 placeholder-gray-600 focus:outline-none focus:border-brand-500/50 transition-all"
              />
            </div>

            {/* Action Buttons */}
            {[
              { id: "analytics" as SidePanel, icon: BarChart2, label: "Análises", color: "accent" },
              { id: "chat" as SidePanel, icon: MessageSquare, label: "Chat IA", color: "brand" },
              { id: "export" as SidePanel, icon: FileDown, label: "Exportar", color: "brand" },
            ].map(({ id, icon: Icon, label, color }) => (
              <button
                key={id}
                onClick={() => setSidePanel(sidePanel === id ? "none" : id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all",
                  sidePanel === id
                    ? color === "accent"
                      ? "bg-accent-400/15 border border-accent-400/30 text-accent-300"
                      : "bg-brand-500/15 border border-brand-500/30 text-brand-300"
                    : "bg-dark-700 border border-dark-500/20 text-gray-400 hover:text-gray-200"
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden md:inline">{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Filter bar */}
        <AnimatePresence>
          {conversation.participants && conversation.participants.length > 1 && (
            <motion.div
              initial={{ height: 0 }}
              animate={{ height: "auto" }}
              className="px-4 py-2 border-b border-dark-500/20 flex items-center gap-2 overflow-x-auto"
            >
              <span className="text-xs text-gray-500 shrink-0">Filtrar por:</span>
              <button
                onClick={() => setFilterSender(null)}
                className={cn(
                  "px-2.5 py-1 rounded-full text-xs transition-colors shrink-0",
                  !filterSender ? "bg-brand-500/20 text-brand-300" : "text-gray-500 hover:text-gray-300"
                )}
              >
                Todos
              </button>
              {conversation.participants.map((p) => (
                <button
                  key={p}
                  onClick={() => setFilterSender(filterSender === p ? null : p)}
                  className={cn(
                    "px-2.5 py-1 rounded-full text-xs transition-colors shrink-0",
                    filterSender === p
                      ? "bg-accent-400/20 text-accent-300"
                      : "text-gray-500 hover:text-gray-300"
                  )}
                >
                  {p.split(" ")[0]}
                </button>
              ))}
              {searchQuery && (
                <span className="ml-auto text-xs text-brand-400">
                  {filteredMessages.length} resultado(s)
                </span>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages */}
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto px-4 py-4 space-y-0.5"
        >
          {/* Group messages by date */}
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
            <>
              <DateGroupedMessages
                messages={filteredMessages}
                conversationId={conversationId}
                participants={conversation.participants || []}
              />

              {/* Load More */}
              {hasMore && (
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
              )}
            </>
          )}
        </div>
      </div>

      {/* Side Panels */}
      <AnimatePresence>
        {sidePanel !== "none" && (
          <motion.div
            key={sidePanel}
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 w-[400px] glass-dark border-l border-brand-500/20 z-40 overflow-y-auto"
          >
            <div className="p-4">
              {sidePanel === "analytics" && (
                <AnalyticsPanel conversation={conversation} />
              )}
              {sidePanel === "export" && (
                <ExportPanel conversationId={conversationId} />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Chat Panel (separate component with its own state) */}
      <ChatPanel
        conversationId={conversationId}
        isOpen={sidePanel === "chat"}
        onClose={() => setSidePanel("none")}
      />
    </div>
  );
}

// ─── Date Grouped Messages ─────────────────────────────────────────────────────
function DateGroupedMessages({
  messages,
  conversationId,
  participants,
}: {
  messages: Message[];
  conversationId: string;
  participants: string[];
}) {
  const grouped: { date: string; messages: Message[] }[] = [];
  let currentDate = "";

  for (const msg of messages) {
    try {
      const msgDate = new Date(msg.timestamp).toLocaleDateString("pt-BR");
      if (msgDate !== currentDate) {
        currentDate = msgDate;
        grouped.push({ date: msgDate, messages: [msg] });
      } else {
        grouped[grouped.length - 1].messages.push(msg);
      }
    } catch {
      if (grouped.length === 0) {
        grouped.push({ date: "—", messages: [msg] });
      } else {
        grouped[grouped.length - 1].messages.push(msg);
      }
    }
  }

  return (
    <>
      {grouped.map(({ date, messages: dayMsgs }) => (
        <div key={date}>
          {/* Date Divider */}
          <div className="flex items-center gap-3 py-3">
            <div className="flex-1 h-px bg-dark-500/30" />
            <span className="text-[10px] text-gray-600 px-2 py-0.5 rounded-full bg-dark-700/50 border border-dark-500/20">
              {date}
            </span>
            <div className="flex-1 h-px bg-dark-500/30" />
          </div>

          {/* Messages */}
          {dayMsgs.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              conversationId={conversationId}
              participants={participants}
            />
          ))}
        </div>
      ))}
    </>
  );
}
