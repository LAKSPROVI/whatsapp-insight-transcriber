"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send, Bot, User, Trash2, Sparkles, X,
  MessageSquare, ChevronDown
} from "lucide-react";
import { createChatStream, getChatHistory, clearChatHistory } from "@/lib/api";
import type { ChatMessage } from "@/types";
import { cn } from "@/lib/utils";

interface ChatPanelProps {
  conversationId: string;
  isOpen: boolean;
  onClose: () => void;
}

const QUICK_QUESTIONS = [
  "Faça um resumo dos pontos principais",
  "Qual foi o tom geral da conversa?",
  "Houve algum conflito ou desentendimento?",
  "Quais foram os principais tópicos discutidos?",
  "Liste os compromissos e acordos firmados",
  "Em que momento falaram sobre valores/dinheiro?",
];

export function ChatPanel({ conversationId, isOpen, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [showQuestions, setShowQuestions] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  // Carregar histórico
  useEffect(() => {
    if (isOpen && conversationId) {
      getChatHistory(conversationId)
        .then((data) => {
          setMessages(data.messages);
          if (data.messages.length > 0) setShowQuestions(false);
        })
        .catch(console.error);
    }
  }, [isOpen, conversationId]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  const sendMessage = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText || isLoading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: messageText,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setShowQuestions(false);
    setIsLoading(true);
    setStreamingText("");

    let fullResponse = "";

    abortRef.current = createChatStream(
      conversationId,
      messageText,
      (chunk) => {
        fullResponse += chunk;
        setStreamingText(fullResponse);
      },
      () => {
        const assistantMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: fullResponse,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setStreamingText("");
        setIsLoading(false);
        abortRef.current = null;
      },
      (err) => {
        console.error("Chat error:", err);
        setStreamingText("");
        setIsLoading(false);
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleClear = async () => {
    await clearChatHistory(conversationId);
    setMessages([]);
    setShowQuestions(true);
  };

  const stopStreaming = () => {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
      setIsLoading(false);
      if (streamingText) {
        const msg: ChatMessage = {
          id: Date.now().toString(),
          role: "assistant",
          content: streamingText + "...",
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, msg]);
        setStreamingText("");
      }
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: "100%", opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: "100%", opacity: 0 }}
          transition={{ type: "spring", damping: 30, stiffness: 300 }}
          className="fixed right-0 top-0 bottom-0 w-full max-w-md glass-dark border-l border-brand-500/20 z-50 flex flex-col shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center gap-3 p-4 border-b border-brand-500/10">
            <div className="w-9 h-9 rounded-xl bg-brand-500/20 border border-brand-500/30 flex items-center justify-center">
              <Bot className="w-5 h-5 text-brand-400" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-white text-sm">Chat com a Conversa</h3>
              <p className="text-[10px] text-gray-500">Powered by Claude Opus 4.6</p>
            </div>
            <div className="flex items-center gap-2">
              {messages.length > 0 && (
                <button
                  onClick={handleClear}
                  className="p-1.5 rounded-lg hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors"
                  title="Limpar chat"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg hover:bg-dark-600 text-gray-500 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && !isLoading && showQuestions && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                <div className="text-center py-6">
                  <div className="w-16 h-16 mx-auto rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mb-3">
                    <Sparkles className="w-8 h-8 text-brand-400" />
                  </div>
                  <h4 className="font-semibold text-gray-200">Pergunte sobre a conversa</h4>
                  <p className="text-sm text-gray-500 mt-1">
                    Faça qualquer pergunta sobre o conteúdo transcrito
                  </p>
                </div>

                <div className="space-y-2">
                  <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">
                    Sugestões rápidas
                  </p>
                  {QUICK_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => sendMessage(q)}
                      className="w-full text-left text-sm px-3 py-2 rounded-xl glass hover:bg-brand-500/10 hover:border-brand-500/30 transition-all text-gray-300 hover:text-white"
                    >
                      <span className="text-brand-400 mr-2">→</span>
                      {q}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={cn(
                  "flex gap-2.5",
                  msg.role === "user" ? "flex-row-reverse" : "flex-row"
                )}
              >
                <div
                  className={cn(
                    "w-7 h-7 rounded-lg flex items-center justify-center shrink-0",
                    msg.role === "user"
                      ? "bg-brand-500/20 border border-brand-500/30"
                      : "bg-accent-400/10 border border-accent-400/30"
                  )}
                >
                  {msg.role === "user" ? (
                    <User className="w-3.5 h-3.5 text-brand-400" />
                  ) : (
                    <Bot className="w-3.5 h-3.5 text-accent-400" />
                  )}
                </div>
                <div
                  className={cn(
                    "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed chat-content",
                    msg.role === "user"
                      ? "bg-brand-500/15 border border-brand-500/25 text-gray-100 rounded-tr-sm"
                      : "bg-dark-600/80 border border-dark-400/20 text-gray-200 rounded-tl-sm"
                  )}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  <p className="text-[9px] text-gray-600 mt-1.5 text-right">
                    {msg.tokens_used ? `${msg.tokens_used} tokens` : ""}
                  </p>
                </div>
              </motion.div>
            ))}

            {/* Streaming */}
            {isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-2.5"
              >
                <div className="w-7 h-7 rounded-lg bg-accent-400/10 border border-accent-400/30 flex items-center justify-center shrink-0">
                  <Bot className="w-3.5 h-3.5 text-accent-400 animate-pulse" />
                </div>
                <div className="max-w-[80%] rounded-2xl rounded-tl-sm px-4 py-3 bg-dark-600/80 border border-dark-400/20">
                  {streamingText ? (
                    <p className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">
                      {streamingText}
                      <motion.span
                        animate={{ opacity: [1, 0] }}
                        transition={{ repeat: Infinity, duration: 0.5 }}
                        className="inline-block w-1.5 h-3.5 bg-accent-400 ml-0.5 align-middle"
                      />
                    </p>
                  ) : (
                    <div className="flex gap-1 items-center py-1">
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-brand-500/10">
            {isLoading && (
              <div className="flex justify-center mb-2">
                <button
                  onClick={stopStreaming}
                  className="text-xs text-red-400 hover:text-red-300 transition-colors"
                >
                  Parar geração
                </button>
              </div>
            )}
            <div className="flex gap-2 items-end">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Pergunte sobre a conversa... (Enter para enviar)"
                rows={1}
                disabled={isLoading}
                className={cn(
                  "flex-1 bg-dark-600/80 border border-dark-400/30 rounded-xl px-4 py-2.5",
                  "text-sm text-gray-200 placeholder-gray-600 resize-none",
                  "focus:outline-none focus:border-brand-500/50 focus:bg-dark-500/80",
                  "transition-all duration-200 max-h-32",
                  isLoading && "opacity-50"
                )}
                style={{ minHeight: "42px" }}
              />
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim() || isLoading}
                className={cn(
                  "w-10 h-10 rounded-xl flex items-center justify-center transition-all",
                  input.trim() && !isLoading
                    ? "bg-brand-500 hover:bg-brand-400 text-white shadow-brand"
                    : "bg-dark-600 text-gray-600 cursor-not-allowed"
                )}
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
