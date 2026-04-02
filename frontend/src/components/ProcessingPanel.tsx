"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Cpu, Zap, Activity } from "lucide-react";
import type { ProcessingProgress } from "@/types";
import { cn } from "@/lib/utils";

interface ProcessingPanelProps {
  progress: ProcessingProgress | null;
  sessionId: string;
}

const STAGE_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  pending: { label: "Aguardando", icon: "⏳", color: "text-gray-400" },
  uploading: { label: "Enviando", icon: "📤", color: "text-blue-400" },
  parsing: { label: "Analisando estrutura", icon: "🔍", color: "text-yellow-400" },
  processing: { label: "Processando com IA", icon: "🤖", color: "text-brand-400" },
  completed: { label: "Concluído", icon: "✅", color: "text-accent-400" },
  failed: { label: "Falhou", icon: "❌", color: "text-red-400" },
};

export function ProcessingPanel({ progress, sessionId }: ProcessingPanelProps) {
  const stage = progress?.status || "pending";
  const stageInfo = STAGE_LABELS[stage] || STAGE_LABELS.pending;
  const percent = Math.round((progress?.progress || 0) * 100);

  // Geração de partículas fake para visual
  const particles = Array.from({ length: 20 }, (_, i) => i);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-2xl mx-auto space-y-6"
      role="region"
      aria-label="Painel de processamento"
    >
      {/* Header da sessão */}
      <div className="glass rounded-2xl p-6">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500 font-mono">SESSION ID</span>
          <span className="text-xs text-brand-400 font-mono">{sessionId.slice(0, 8)}...</span>
        </div>

        {/* Status principal */}
        <div className="flex items-center gap-3 mt-4" aria-live="polite" aria-atomic="true">
          <div className="relative w-14 h-14 flex items-center justify-center" aria-hidden="true">
            <div
              className={cn(
                "absolute inset-0 rounded-full border-2 border-transparent",
                stage !== "completed" && stage !== "failed"
                  ? "border-t-brand-500 animate-spin"
                  : ""
              )}
            />
            <span className="text-2xl">{stageInfo.icon}</span>
          </div>
          <div>
            <p className={cn("text-xl font-bold", stageInfo.color)}>{stageInfo.label}</p>
            <p className="text-sm text-gray-400 mt-0.5">{progress?.progress_message || "..."}</p>
          </div>
        </div>

        {/* Barra de progresso */}
        <div className="mt-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm text-gray-400">Progresso</span>
            <motion.span
              key={percent}
              initial={{ scale: 1.2 }}
              animate={{ scale: 1 }}
              className="text-lg font-bold text-brand-300"
            >
              {percent}%
            </motion.span>
          </div>
          <div className="h-3 bg-dark-600 rounded-full overflow-hidden" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} aria-label={`Progresso: ${percent}%`}>
            <motion.div
              initial={{ width: "0%" }}
              animate={{ width: `${percent}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className={cn(
                "h-full rounded-full",
                stage === "completed"
                  ? "bg-accent-400"
                  : stage === "failed"
                  ? "bg-red-500"
                  : "progress-bar-animated"
              )}
            />
          </div>
        </div>

        {/* Stats */}
        {(progress?.total_messages ?? 0) > 0 && (
          <div className="grid grid-cols-3 gap-3 mt-4">
            {[
              { label: "Mensagens", value: progress?.total_messages ?? 0, icon: "💬" },
              { label: "Processadas", value: progress?.processed_messages ?? 0, icon: "✅" },
              { label: "Agentes Ativos", value: progress?.active_agents ?? 0, icon: "🤖" },
            ].map((stat) => (
              <div key={stat.label} className="bg-dark-600/50 rounded-xl p-3 text-center">
                <span className="text-lg">{stat.icon}</span>
                <p className="text-xl font-bold text-white mt-1">{stat.value}</p>
                <p className="text-xs text-gray-400">{stat.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Visualizador de Agentes */}
      {stage === "processing" && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="glass rounded-2xl p-6"
        >
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="w-5 h-5 text-brand-400" />
            <h3 className="font-semibold text-gray-200">20 Agentes de IA Paralelos</h3>
            <div className="ml-auto flex items-center gap-1">
              <Activity className="w-4 h-4 text-accent-400" />
              <span className="text-xs text-accent-400">Ativos</span>
            </div>
          </div>

          {/* Grid de agentes */}
          <div className="grid grid-cols-10 gap-2">
            {Array.from({ length: 20 }, (_, i) => {
              const isActive = i < (progress?.active_agents || 0);
              return (
                <motion.div
                  key={i}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: i * 0.02 }}
                  className={cn(
                    "aspect-square rounded-lg flex items-center justify-center text-xs font-mono",
                    isActive
                      ? "bg-brand-500/20 border border-brand-400/40"
                      : "bg-dark-600/50 border border-dark-500/30"
                  )}
                >
                  <div className="flex flex-col items-center gap-0.5">
                    <span className={cn("agent-dot", isActive ? "agent-dot-active" : "agent-dot-idle")} />
                    <span className={cn("text-[8px]", isActive ? "text-brand-400" : "text-gray-600")}>
                      {(i + 1).toString().padStart(2, "0")}
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </div>

          {/* Stream de logs fake */}
          <div className="mt-4 bg-dark-900/60 rounded-xl p-3 font-mono text-xs h-28 overflow-hidden relative">
            <div className="text-accent-400 opacity-80">
              {[
                "[agent-01] 🎵 Transcrevendo áudio PTT-20231215-WA0023.ogg...",
                "[agent-04] 🖼️ Analisando imagem IMG-20231215-WA0019.jpg...",
                "[agent-07] 🎬 Processando vídeo VID-20231215-WA0031.mp4...",
                "[agent-02] ✅ Audio transcrito em 3.2s (342 tokens)",
                "[agent-11] 🖼️ OCR detectou texto em imagem: 'Proposta...'",
                "[agent-03] 🎵 Transcrevendo áudio PTT-20231215-WA0025.ogg...",
                "[agent-08] ✅ Vídeo processado: 1 min 23s (1.2k tokens)",
              ].map((log, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.3 }}
                  className="leading-5"
                >
                  {log}
                </motion.div>
              ))}
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-dark-900/60 to-transparent" />
          </div>
        </motion.div>
      )}

      {/* Concluído */}
      {stage === "completed" && (
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="glass-accent rounded-2xl p-8 text-center"
        >
          <div className="text-5xl mb-3">🎉</div>
          <h3 className="text-2xl font-bold text-gradient-accent">Processamento Concluído!</h3>
          <p className="text-gray-400 mt-2">
            {progress?.total_messages} mensagens transcritas com sucesso
          </p>
          <motion.div
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ repeat: Infinity, duration: 1.5 }}
            className="mt-4 text-sm text-accent-400"
          >
            Redirecionando para a transcrição...
          </motion.div>
        </motion.div>
      )}

      {/* Falha */}
      {stage === "failed" && (
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="rounded-2xl p-6 bg-red-500/10 border border-red-500/30 text-center"
        >
          <div className="text-4xl mb-3">❌</div>
          <h3 className="text-xl font-bold text-red-300">Erro no processamento</h3>
          <p className="text-gray-400 mt-2 text-sm">{progress?.progress_message}</p>
        </motion.div>
      )}
    </motion.div>
  );
}
