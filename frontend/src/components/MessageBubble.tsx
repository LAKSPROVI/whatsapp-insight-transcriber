"use client";

import { useState, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Download, ChevronDown, ChevronUp,
  Star, AlertTriangle, Info, Reply, Forward, Bookmark
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import type { Message } from "@/types";
import {
  cn, getSenderColor, getSenderInitials, getMediaIcon,
  getMediaLabel, getSentimentEmoji, getSentimentColor,
  formatDuration
} from "@/lib/utils";
import { buildApiUrl } from "@/lib/api";
import { formatWhatsAppText } from "@/lib/whatsappFormatter";
import { AudioPlayer } from "@/components/AudioPlayer";
import { VideoPlayer } from "@/components/VideoPlayer";

interface MessageBubbleProps {
  message: Message;
  conversationId: string;
  participants: string[];
  showSender?: boolean;
  isHighlighted?: boolean;
  onImageClick?: (messageId: string) => void;
  onMetadataClick?: (message: Message) => void;
}

export function MessageBubble({
  message,
  conversationId,
  participants,
  showSender = true,
  isHighlighted = false,
  onImageClick,
  onMetadataClick,
}: MessageBubbleProps) {
  const [expanded, setExpanded] = useState(false);

  const senderColor = getSenderColor(message.sender, "chart");
  const isMedia = message.media_type !== "text" && message.media_type !== "deleted";
  const hasContent = message.transcription || message.description || message.ocr_text;

  const ts = useMemo(() => {
    try {
      return format(parseISO(message.timestamp), "HH:mm", { locale: ptBR });
    } catch {
      return message.timestamp;
    }
  }, [message.timestamp]);

  const dateStr = useMemo(() => {
    try {
      return format(parseISO(message.timestamp), "dd/MM/yyyy", { locale: ptBR });
    } catch {
      return "";
    }
  }, [message.timestamp]);

  const mediaUrl = message.media_url
    ? buildApiUrl(message.media_url)
    : null;

  // Parse forwarded/quoted info from original_text
  const isForwarded = message.original_text?.startsWith("[Encaminhada]") ||
    message.original_text?.startsWith("[Forwarded]") || false;

  // Formatted text with WhatsApp-style rendering
  const formattedHtml = useMemo(() => {
    if (!message.original_text) return "";
    let text = message.original_text;
    // Strip forwarded prefix for display
    if (isForwarded) {
      text = text.replace(/^\[(Encaminhada|Forwarded)\]\s*/i, "");
    }
    return formatWhatsAppText(text);
  }, [message.original_text, isForwarded]);

  return (
    <div
      id={`msg-${message.id}`}
      className={cn(
        "message-bubble group flex gap-3 py-1.5 px-2 rounded-xl transition-all duration-500",
        message.is_key_moment && "bg-brand-500/5 border-l-2 border-brand-400",
        isHighlighted && "bg-brand-500/15 ring-2 ring-brand-400/50 animate-pulse"
      )}
      data-message-id={message.id}
    >
      {/* Avatar */}
      <div className="flex-shrink-0 pt-0.5">
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shadow-lg"
          style={{
            backgroundColor: senderColor + "22",
            border: `1px solid ${senderColor}44`,
            color: senderColor,
          }}
          aria-hidden="true"
        >
          {getSenderInitials(message.sender)}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold" style={{ color: senderColor }}>
            {message.sender}
          </span>
          <span className="text-[10px] text-gray-600">{ts}</span>
          <span className="text-[10px] text-gray-700">{dateStr}</span>
          {isForwarded && (
            <span className="flex items-center gap-0.5 text-[10px] text-gray-500 italic">
              <Forward className="w-2.5 h-2.5" />
              Encaminhada
            </span>
          )}
          {message.is_key_moment && (
            <span className="flex items-center gap-0.5 text-[10px] text-brand-400">
              <Star className="w-2.5 h-2.5" />
              Momento-chave
            </span>
          )}
          {/* Action buttons - visible on hover */}
          <div className="ml-auto flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {onMetadataClick && (
              <button
                onClick={() => onMetadataClick(message)}
                className="p-1 rounded text-gray-600 hover:text-brand-400 transition-colors"
                aria-label="Ver metadados"
              >
                <Info className="w-3 h-3" />
              </button>
            )}
          </div>
          {/* Sentimento */}
          {message.sentiment && (
            <span
              className={cn("text-[10px] opacity-60", getSentimentColor(message.sentiment))}
            >
              {getSentimentEmoji(message.sentiment)}
            </span>
          )}
        </div>

        {/* Bubble */}
        <div
          className={cn(
            "rounded-xl px-3 py-2 max-w-2xl",
            message.media_type === "deleted"
              ? "message-bubble-deleted"
              : isMedia
              ? "message-bubble-media"
              : "message-bubble-text"
          )}
        >
          {/* Text message with WhatsApp formatting */}
          {message.media_type === "text" && message.original_text && (
            <div
              className="text-sm text-gray-200 leading-relaxed break-words wa-message-text"
              dangerouslySetInnerHTML={{ __html: formattedHtml }}
            />
          )}

          {/* Deleted message */}
          {message.media_type === "deleted" && (
            <p className="text-sm text-gray-500 italic flex items-center gap-1.5">
              <span>🗑️</span> Mensagem apagada
            </p>
          )}

          {/* Media content */}
          {isMedia && (
            <div className="space-y-2">
              {/* Media header */}
              <div className="flex items-center gap-2">
                <span className="text-lg">{getMediaIcon(message.media_type)}</span>
                <div className="flex-1">
                  <span className="text-xs font-semibold text-accent-300">
                    {getMediaLabel(message.media_type)}
                  </span>
                  {message.media_filename && (
                    <span className="text-[10px] text-gray-500 ml-2">{message.media_filename}</span>
                  )}
                </div>
                {/* Download button */}
                {mediaUrl && (
                  <a
                    href={mediaUrl}
                    download={message.media_filename}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg bg-accent-400/20 hover:bg-accent-400/30 text-accent-300 text-[10px] transition-colors"
                  >
                    <Download className="w-3 h-3" />
                    Baixar
                  </a>
                )}
              </div>

              {/* Metadata badges */}
              {message.media_metadata && (
                <div className="flex flex-wrap gap-2">
                  {message.media_metadata.file_size_formatted && (
                    <MetaBadge label="Tamanho" value={message.media_metadata.file_size_formatted} />
                  )}
                  {message.media_metadata.duration_formatted && (
                    <MetaBadge label="Duração" value={message.media_metadata.duration_formatted} />
                  )}
                  {message.media_metadata.resolution && (
                    <MetaBadge label="Resolução" value={message.media_metadata.resolution} />
                  )}
                  {message.media_metadata.format && (
                    <MetaBadge label="Formato" value={message.media_metadata.format.toUpperCase()} />
                  )}
                  {message.media_metadata.codec && (
                    <MetaBadge label="Codec" value={message.media_metadata.codec} />
                  )}
                </div>
              )}

              {/* Audio Player - inline with waveform */}
              {message.media_type === "audio" && mediaUrl && (
                <AudioPlayer
                  src={mediaUrl}
                  duration={message.media_metadata?.duration}
                  transcription={message.transcription}
                />
              )}

              {/* Video Player - inline with controls */}
              {message.media_type === "video" && mediaUrl && (
                <VideoPlayer src={mediaUrl} />
              )}

              {/* Image Preview - clickable for lightbox */}
              {message.media_type === "image" && mediaUrl && (
                <div className="mt-2">
                  <motion.img
                    src={mediaUrl}
                    alt={message.description || "Imagem"}
                    className="max-h-48 rounded-lg cursor-pointer hover:brightness-110 transition-all duration-300 object-cover shadow-lg"
                    onClick={() => onImageClick?.(message.id)}
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                    loading="lazy"
                  />
                </div>
              )}

              {/* Sticker */}
              {message.media_type === "sticker" && mediaUrl && (
                <div className="mt-2">
                  <img
                    src={mediaUrl}
                    alt="Sticker"
                    className="max-h-24 max-w-24"
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                </div>
              )}

              {/* Location */}
              {message.media_type === "location" && message.original_text && (
                <a
                  href={message.original_text}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-brand-400 hover:text-brand-300 underline"
                >
                  Abrir localização no mapa
                </a>
              )}

              {/* Text content of media message */}
              {message.original_text && message.media_type !== "location" && (
                <div
                  className="text-sm text-gray-200 leading-relaxed break-words wa-message-text mt-1"
                  dangerouslySetInnerHTML={{ __html: formatWhatsAppText(message.original_text) }}
                />
              )}

              {/* AI Transcription/Description */}
              {hasContent && (
                <div className="mt-2 space-y-1.5">
                  <button
                    onClick={() => setExpanded(!expanded)}
                    className="flex items-center gap-1 text-[10px] text-gray-400 hover:text-gray-200 transition-colors"
                  >
                    {expanded ? (
                      <ChevronUp className="w-3 h-3" />
                    ) : (
                      <ChevronDown className="w-3 h-3" />
                    )}
                    {expanded ? "Ocultar" : "Ver"} conteúdo da IA
                  </button>

                  <AnimatePresence>
                    {expanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="space-y-2 pt-1">
                          {message.transcription && (
                            <div className="bg-dark-700/50 rounded-lg p-2">
                              <p className="text-[10px] text-accent-400 font-medium mb-1">
                                🎤 TRANSCRIÇÃO
                              </p>
                              <p className="text-xs text-gray-300 leading-relaxed">
                                {message.transcription}
                              </p>
                            </div>
                          )}
                          {message.description && (
                            <div className="bg-dark-700/50 rounded-lg p-2">
                              <p className="text-[10px] text-brand-400 font-medium mb-1">
                                👁️ DESCRIÇÃO
                              </p>
                              <p className="text-xs text-gray-300 leading-relaxed">
                                {message.description}
                              </p>
                            </div>
                          )}
                          {message.ocr_text && (
                            <div className="bg-dark-700/50 rounded-lg p-2">
                              <p className="text-[10px] text-yellow-400 font-medium mb-1">
                                📄 TEXTO (OCR)
                              </p>
                              <p className="text-xs text-gray-300 leading-relaxed font-mono">
                                {message.ocr_text}
                              </p>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Preview when collapsed */}
                  {!expanded && (message.transcription || message.description) && (
                    <p className="text-xs text-gray-500 italic line-clamp-1">
                      "{(message.transcription || message.description || "").slice(0, 80)}..."
                    </p>
                  )}
                </div>
              )}

              {/* Processing status */}
              {message.processing_status === "processing" && (
                <div className="flex items-center gap-1.5 text-[10px] text-brand-400">
                  <div className="w-2 h-2 rounded-full bg-brand-400 animate-pulse" />
                  Processando...
                </div>
              )}
              {message.processing_status === "failed" && (
                <div className="flex items-center gap-1 text-[10px] text-red-400">
                  <AlertTriangle className="w-3 h-3" />
                  Falha no processamento
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetaBadge({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-dark-600/80 border border-dark-400/30 text-[9px]">
      <span className="text-gray-500">{label}:</span>
      <span className="text-gray-300 font-medium">{value}</span>
    </span>
  );
}
