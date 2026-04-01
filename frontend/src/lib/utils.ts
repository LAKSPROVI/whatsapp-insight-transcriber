import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNow, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import type { MediaType, SentimentType } from "@/types";

// ─── Classnames ─────────────────────────────────────────────────────────────

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ─── Date Formatting ────────────────────────────────────────────────────────

export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return format(d, "dd/MM/yyyy HH:mm", { locale: ptBR });
}

export function formatDateShort(date: string | Date): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return format(d, "dd/MM/yy", { locale: ptBR });
}

export function formatRelative(date: string | Date): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return formatDistanceToNow(d, { addSuffix: true, locale: ptBR });
}

// ─── Duration ───────────────────────────────────────────────────────────────

export function formatDuration(seconds?: number): string {
  if (!seconds) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// ─── Media helpers ──────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8020";

export function getMediaUrl(conversationId: string, filename: string): string {
  return `${API_BASE}/api/media/${conversationId}/${filename}`;
}

export function getMediaIcon(mediaType: MediaType): string {
  const icons: Record<MediaType, string> = {
    text: "MessageSquare",
    image: "Image",
    audio: "Volume2",
    video: "Video",
    document: "FileText",
    sticker: "Image",
    contact: "User",
    location: "MapPin",
    deleted: "AlertTriangle",
  };
  return icons[mediaType] || "FileText";
}

export function getMediaLabel(mediaType: MediaType): string {
  const labels: Record<MediaType, string> = {
    text: "Texto",
    image: "Imagem",
    audio: "Áudio",
    video: "Vídeo",
    document: "Documento",
    sticker: "Sticker",
    contact: "Contato",
    location: "Localização",
    deleted: "Deletada",
  };
  return labels[mediaType] || mediaType;
}

// ─── Sentiment helpers ──────────────────────────────────────────────────────

export function getSentimentEmoji(sentiment?: SentimentType): string {
  if (!sentiment) return "😐";
  const emojis: Record<SentimentType, string> = {
    positive: "😊",
    negative: "😟",
    neutral: "😐",
    mixed: "🤔",
  };
  return emojis[sentiment] || "😐";
}

export function getSentimentColor(sentiment?: SentimentType): string {
  if (!sentiment) return "text-gray-400";
  const colors: Record<SentimentType, string> = {
    positive: "text-green-400",
    negative: "text-red-400",
    neutral: "text-gray-400",
    mixed: "text-yellow-400",
  };
  return colors[sentiment] || "text-gray-400";
}

// ─── Sender helpers ─────────────────────────────────────────────────────────

const SENDER_COLORS = [
  "bg-purple-500/20 text-purple-300 border-purple-500/30",
  "bg-blue-500/20 text-blue-300 border-blue-500/30",
  "bg-green-500/20 text-green-300 border-green-500/30",
  "bg-pink-500/20 text-pink-300 border-pink-500/30",
  "bg-amber-500/20 text-amber-300 border-amber-500/30",
  "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
];

const SENDER_CHART_COLORS = [
  "#6C63FF",
  "#00d4aa",
  "#ff6b9d",
  "#ffc107",
  "#64b5f6",
  "#a5d6a7",
];

export function getSenderColor(sender: string, variant: "badge" | "chart" = "badge"): string {
  let hash = 0;
  for (let i = 0; i < sender.length; i++) {
    hash = sender.charCodeAt(i) + ((hash << 5) - hash);
  }
  const idx = Math.abs(hash) % SENDER_COLORS.length;
  return variant === "chart" ? SENDER_CHART_COLORS[idx] : SENDER_COLORS[idx];
}

export function getSenderInitials(sender: string): string {
  return sender
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}
