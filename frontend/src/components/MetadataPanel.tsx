"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  X, FileText, Image, Video, Mic, Hash, Clock, User, Shield, Info,
  HardDrive, Cpu, Gauge, Layers
} from "lucide-react";
import type { Message, MediaMetadata } from "@/types";
import { cn, formatDuration } from "@/lib/utils";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";

interface MetadataPanelProps {
  message: Message | null;
  isOpen: boolean;
  onClose: () => void;
}

export function MetadataPanel({ message, isOpen, onClose }: MetadataPanelProps) {
  if (!message) return null;

  const meta = message.media_metadata;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: 400, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 400, opacity: 0 }}
          transition={{ type: "spring", damping: 30, stiffness: 300 }}
          className="fixed right-0 top-0 bottom-0 w-[380px] glass-dark border-l border-brand-500/20 z-50 overflow-y-auto"
          role="complementary"
          aria-label="Painel de metadados"
        >
          <div className="p-5 space-y-5">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Info className="w-5 h-5 text-brand-400" />
                <h3 className="font-semibold text-white">Metadados</h3>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-dark-600 transition-colors"
                aria-label="Fechar metadados"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Message Info */}
            <Section title="Mensagem" icon={<FileText className="w-4 h-4" />}>
              <MetaRow icon={<User className="w-3.5 h-3.5" />} label="Remetente" value={message.sender} />
              <MetaRow
                icon={<Clock className="w-3.5 h-3.5" />}
                label="Data/Hora"
                value={(() => {
                  try {
                    return format(parseISO(message.timestamp), "dd/MM/yyyy HH:mm:ss", { locale: ptBR });
                  } catch {
                    return message.timestamp;
                  }
                })()}
              />
              <MetaRow icon={<Hash className="w-3.5 h-3.5" />} label="Sequencia" value={`#${message.sequence_number}`} />
              <MetaRow icon={<Layers className="w-3.5 h-3.5" />} label="Tipo" value={message.media_type} />
              <MetaRow icon={<Shield className="w-3.5 h-3.5" />} label="Status" value={message.processing_status} />
              {message.sentiment && (
                <MetaRow
                  icon={<Gauge className="w-3.5 h-3.5" />}
                  label="Sentimento"
                  value={`${message.sentiment}${message.sentiment_score ? ` (${(message.sentiment_score * 100).toFixed(0)}%)` : ""}`}
                />
              )}
            </Section>

            {/* Media Info */}
            {meta && (
              <Section
                title="Midia"
                icon={
                  message.media_type === "image" ? <Image className="w-4 h-4" /> :
                  message.media_type === "audio" ? <Mic className="w-4 h-4" /> :
                  message.media_type === "video" ? <Video className="w-4 h-4" /> :
                  <FileText className="w-4 h-4" />
                }
              >
                {message.media_filename && (
                  <MetaRow icon={<FileText className="w-3.5 h-3.5" />} label="Arquivo" value={message.media_filename} />
                )}
                {meta.file_size_formatted && (
                  <MetaRow icon={<HardDrive className="w-3.5 h-3.5" />} label="Tamanho" value={meta.file_size_formatted} />
                )}
                {meta.format && (
                  <MetaRow icon={<Layers className="w-3.5 h-3.5" />} label="Formato" value={meta.format.toUpperCase()} />
                )}
                {meta.mime_type && (
                  <MetaRow icon={<FileText className="w-3.5 h-3.5" />} label="MIME Type" value={meta.mime_type} />
                )}
                {meta.resolution && (
                  <MetaRow icon={<Image className="w-3.5 h-3.5" />} label="Resolucao" value={meta.resolution} />
                )}
                {meta.width && meta.height && (
                  <MetaRow icon={<Image className="w-3.5 h-3.5" />} label="Dimensoes" value={`${meta.width} x ${meta.height} px`} />
                )}
                {meta.duration != null && meta.duration > 0 && (
                  <MetaRow icon={<Clock className="w-3.5 h-3.5" />} label="Duracao" value={meta.duration_formatted || formatDuration(meta.duration)} />
                )}
                {meta.codec && (
                  <MetaRow icon={<Cpu className="w-3.5 h-3.5" />} label="Codec" value={meta.codec} />
                )}
                {meta.bitrate && (
                  <MetaRow icon={<Gauge className="w-3.5 h-3.5" />} label="Bitrate" value={`${Math.round(meta.bitrate / 1000)} kbps`} />
                )}
                {meta.sample_rate && (
                  <MetaRow icon={<Mic className="w-3.5 h-3.5" />} label="Sample Rate" value={`${meta.sample_rate} Hz`} />
                )}
                {meta.channels && (
                  <MetaRow icon={<Mic className="w-3.5 h-3.5" />} label="Canais" value={meta.channels === 1 ? "Mono" : meta.channels === 2 ? "Stereo" : `${meta.channels} canais`} />
                )}
                {meta.fps && (
                  <MetaRow icon={<Video className="w-3.5 h-3.5" />} label="FPS" value={`${meta.fps} fps`} />
                )}
              </Section>
            )}

            {/* AI Content */}
            {(message.transcription || message.description || message.ocr_text) && (
              <Section title="Conteudo IA" icon={<Cpu className="w-4 h-4" />}>
                {message.transcription && (
                  <div className="bg-dark-700/50 rounded-lg p-3">
                    <p className="text-[10px] text-accent-400 font-medium mb-1">TRANSCRICAO</p>
                    <p className="text-xs text-gray-300 leading-relaxed">{message.transcription}</p>
                  </div>
                )}
                {message.description && (
                  <div className="bg-dark-700/50 rounded-lg p-3">
                    <p className="text-[10px] text-brand-400 font-medium mb-1">DESCRICAO</p>
                    <p className="text-xs text-gray-300 leading-relaxed">{message.description}</p>
                  </div>
                )}
                {message.ocr_text && (
                  <div className="bg-dark-700/50 rounded-lg p-3">
                    <p className="text-[10px] text-yellow-400 font-medium mb-1">TEXTO (OCR)</p>
                    <p className="text-xs text-gray-300 leading-relaxed font-mono">{message.ocr_text}</p>
                  </div>
                )}
              </Section>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-gray-400 font-medium">
        {icon}
        {title}
      </div>
      <div className="space-y-1.5 pl-1">
        {children}
      </div>
    </div>
  );
}

function MetaRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2 py-1">
      <span className="text-gray-500 mt-0.5 flex-shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <span className="text-[10px] text-gray-500 block">{label}</span>
        <span className="text-xs text-gray-200 break-words">{value}</span>
      </div>
    </div>
  );
}
