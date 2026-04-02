"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, X, Filter, Loader2, ChevronDown, ChevronUp,
  MessageSquare, Image, Video, Mic, FileText
} from "lucide-react";
import { useSearchMessages } from "@/lib/queries";
import type { SearchParams, SearchResultItem, MediaType } from "@/types";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  conversationId: string;
  participants: string[];
  onResultClick?: (messageId: string, conversationId: string) => void;
}

const MESSAGE_TYPES: { value: MediaType; label: string; icon: React.ReactNode }[] = [
  { value: "text", label: "Texto", icon: <FileText className="w-3 h-3" /> },
  { value: "image", label: "Imagem", icon: <Image className="w-3 h-3" /> },
  { value: "video", label: "Vídeo", icon: <Video className="w-3 h-3" /> },
  { value: "audio", label: "Áudio", icon: <Mic className="w-3 h-3" /> },
];

export function SearchBar({ conversationId, participants, onResultClick }: SearchBarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [sender, setSender] = useState<string>("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [messageType, setMessageType] = useState<string>("");
  const [useRegex, setUseRegex] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounce
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Keyboard shortcut: Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen(true);
        setTimeout(() => inputRef.current?.focus(), 100);
      }
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen]);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isOpen]);

  const searchParams: SearchParams = useMemo(() => ({
    q: debouncedQuery,
    conversation_id: conversationId,
    sender: sender || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    type: messageType as MediaType || undefined,
    regex: useRegex || undefined,
    limit: 30,
  }), [debouncedQuery, conversationId, sender, dateFrom, dateTo, messageType, useRegex]);

  const { data, isLoading, isFetching } = useSearchMessages(searchParams, isOpen && !!debouncedQuery);

  const clearAll = useCallback(() => {
    setQuery("");
    setDebouncedQuery("");
    setSender("");
    setDateFrom("");
    setDateTo("");
    setMessageType("");
    setUseRegex(false);
  }, []);

  const handleResultClick = useCallback(
    (item: SearchResultItem) => {
      onResultClick?.(item.message_id, item.conversation_id);
      setIsOpen(false);
    },
    [onResultClick]
  );

  // Highlight helper
  const renderHighlightedText = useCallback((text: string) => {
    if (!text) return null;
    // Backend marks highlights with **text**
    const parts = text.split(/\*\*(.*?)\*\*/g);
    return parts.map((part, i) =>
      i % 2 === 1 ? (
        <mark key={i} className="bg-brand-500/30 text-brand-200 rounded px-0.5">
          {part}
        </mark>
      ) : (
        <span key={i}>{part}</span>
      )
    );
  }, []);

  return (
    <div ref={containerRef} className="relative">
      {/* Toggle button */}
      {!isOpen && (
        <button
          onClick={() => { setIsOpen(true); setTimeout(() => inputRef.current?.focus(), 100); }}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-dark-700 dark:bg-dark-700 border border-dark-500/20 text-xs text-gray-400 hover:text-gray-200 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          aria-label="Abrir pesquisa avançada (Ctrl+K)"
        >
          <Search className="w-3.5 h-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">Pesquisar</span>
          <kbd className="hidden md:inline text-[9px] px-1.5 py-0.5 rounded bg-dark-600 border border-dark-500/30 text-gray-500 ml-1">
            Ctrl+K
          </kbd>
        </button>
      )}

      {/* Search panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="absolute top-0 right-0 z-50 w-[360px] sm:w-[420px] bg-dark-800 dark:bg-dark-800 border border-dark-500/30 rounded-2xl shadow-2xl overflow-hidden"
          >
            {/* Input */}
            <div className="flex items-center gap-2 p-3 border-b border-dark-500/20">
              <Search className="w-4 h-4 text-gray-500 shrink-0" aria-hidden="true" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Buscar mensagens..."
                aria-label="Pesquisar mensagens"
                className="flex-1 bg-transparent text-sm text-gray-200 placeholder-gray-600 focus:outline-none"
              />
              {(isLoading || isFetching) && (
                <Loader2 className="w-4 h-4 text-brand-400 animate-spin shrink-0" aria-label="Buscando..." />
              )}
              {query && (
                <button
                  onClick={() => { setQuery(""); setDebouncedQuery(""); }}
                  aria-label="Limpar busca"
                  className="p-1 rounded-lg hover:bg-dark-600 text-gray-500 hover:text-gray-300 transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={() => setShowFilters(!showFilters)}
                aria-label="Alternar filtros"
                aria-expanded={showFilters}
                className={cn(
                  "p-1.5 rounded-lg transition-colors",
                  showFilters ? "bg-brand-500/20 text-brand-300" : "text-gray-500 hover:text-gray-300 hover:bg-dark-600"
                )}
              >
                <Filter className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                aria-label="Fechar pesquisa"
                className="p-1 rounded-lg hover:bg-dark-600 text-gray-500 hover:text-gray-300 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Filters */}
            <AnimatePresence>
              {showFilters && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden border-b border-dark-500/20"
                >
                  <div className="p-3 space-y-2">
                    {/* Sender */}
                    <div>
                      <label className="text-[10px] text-gray-500 mb-1 block">Remetente</label>
                      <select
                        value={sender}
                        onChange={(e) => setSender(e.target.value)}
                        aria-label="Filtrar por remetente"
                        className="w-full bg-dark-700 border border-dark-500/30 rounded-lg px-2 py-1.5 text-xs text-gray-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                      >
                        <option value="">Todos</option>
                        {participants.map((p) => (
                          <option key={p} value={p}>{p}</option>
                        ))}
                      </select>
                    </div>

                    {/* Date range */}
                    <div className="flex gap-2">
                      <div className="flex-1">
                        <label className="text-[10px] text-gray-500 mb-1 block">De</label>
                        <input
                          type="date"
                          value={dateFrom}
                          onChange={(e) => setDateFrom(e.target.value)}
                          aria-label="Data inicial"
                          className="w-full bg-dark-700 border border-dark-500/30 rounded-lg px-2 py-1.5 text-xs text-gray-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                        />
                      </div>
                      <div className="flex-1">
                        <label className="text-[10px] text-gray-500 mb-1 block">Até</label>
                        <input
                          type="date"
                          value={dateTo}
                          onChange={(e) => setDateTo(e.target.value)}
                          aria-label="Data final"
                          className="w-full bg-dark-700 border border-dark-500/30 rounded-lg px-2 py-1.5 text-xs text-gray-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                        />
                      </div>
                    </div>

                    {/* Message type */}
                    <div>
                      <label className="text-[10px] text-gray-500 mb-1 block">Tipo de mensagem</label>
                      <div className="flex gap-1 flex-wrap">
                        {MESSAGE_TYPES.map((t) => (
                          <button
                            key={t.value}
                            onClick={() => setMessageType(messageType === t.value ? "" : t.value)}
                            aria-pressed={messageType === t.value}
                            className={cn(
                              "flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] transition-colors",
                              messageType === t.value
                                ? "bg-brand-500/20 text-brand-300 border border-brand-500/30"
                                : "bg-dark-600 text-gray-400 hover:text-gray-300 border border-transparent"
                            )}
                          >
                            {t.icon}
                            {t.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Regex toggle */}
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useRegex}
                        onChange={(e) => setUseRegex(e.target.checked)}
                        className="rounded border-dark-500/30 bg-dark-700 text-brand-500 focus:ring-brand-500 focus:ring-offset-0 w-3.5 h-3.5"
                      />
                      <span className="text-[10px] text-gray-400">Usar regex</span>
                    </label>

                    {/* Clear filters */}
                    <button
                      onClick={clearAll}
                      className="text-[10px] text-brand-400 hover:text-brand-300 transition-colors"
                    >
                      Limpar filtros
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Results */}
            <div className="max-h-[350px] overflow-y-auto">
              {!debouncedQuery ? (
                <div className="p-6 text-center text-gray-500">
                  <Search className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-xs">Digite para buscar mensagens</p>
                  <p className="text-[10px] text-gray-600 mt-1">
                    Use filtros para refinar sua busca
                  </p>
                </div>
              ) : isLoading ? (
                <div className="p-6 text-center">
                  <Loader2 className="w-6 h-6 mx-auto animate-spin text-brand-400 mb-2" />
                  <p className="text-xs text-gray-500">Buscando...</p>
                </div>
              ) : data && data.results.length > 0 ? (
                <>
                  <div className="px-3 py-2 text-[10px] text-gray-500 border-b border-dark-500/10">
                    {data.total} resultado{data.total !== 1 ? "s" : ""} encontrado{data.total !== 1 ? "s" : ""}
                  </div>
                  {data.results.map((item) => (
                    <button
                      key={item.message_id}
                      onClick={() => handleResultClick(item)}
                      className="w-full text-left px-3 py-2.5 hover:bg-dark-700/50 transition-colors border-b border-dark-500/10 focus:outline-none focus-visible:bg-dark-700/50"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-medium text-brand-300">
                          {item.sender}
                        </span>
                        <span className="text-[9px] text-gray-600">
                          {new Date(item.timestamp).toLocaleDateString("pt-BR")}
                        </span>
                        {item.sentiment && (
                          <span className="text-[9px]">
                            {item.sentiment === "positive" ? "😊" : item.sentiment === "negative" ? "😟" : "😐"}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-300 line-clamp-2">
                        {item.highlighted_text
                          ? renderHighlightedText(item.highlighted_text)
                          : item.text || "(mídia)"}
                      </p>
                    </button>
                  ))}
                </>
              ) : (
                <div className="p-6 text-center text-gray-500">
                  <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-xs">Nenhum resultado encontrado</p>
                  <p className="text-[10px] text-gray-600 mt-1">
                    Tente termos diferentes ou ajuste os filtros
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
