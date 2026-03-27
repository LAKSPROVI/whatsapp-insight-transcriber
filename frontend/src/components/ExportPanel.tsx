"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { FileDown, FileText, FileType2, Settings2, Loader2, CheckCircle2 } from "lucide-react";
import { exportConversation } from "@/lib/api";
import type { ExportOptions } from "@/types";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

interface ExportPanelProps {
  conversationId: string;
}

export function ExportPanel({ conversationId }: ExportPanelProps) {
  const [options, setOptions] = useState<ExportOptions>({
    format: "pdf",
    include_media_descriptions: true,
    include_sentiment_analysis: true,
    include_summary: true,
    include_statistics: true,
  });
  const [isExporting, setIsExporting] = useState(false);
  const [exported, setExported] = useState(false);

  const handleExport = async () => {
    setIsExporting(true);
    setExported(false);

    try {
      await exportConversation(conversationId, options);
      setExported(true);
      toast.success(`Exportado como ${options.format.toUpperCase()} com sucesso!`);
      setTimeout(() => setExported(false), 3000);
    } catch (err: any) {
      toast.error(`Erro ao exportar: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  const toggle = (key: keyof ExportOptions) => {
    setOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="glass rounded-2xl p-5 space-y-5">
      <div className="flex items-center gap-2">
        <FileDown className="w-5 h-5 text-brand-400" />
        <h3 className="font-semibold text-gray-200">Exportar Relatório</h3>
      </div>

      {/* Format Selection */}
      <div className="grid grid-cols-2 gap-3">
        {(["pdf", "docx"] as const).map((fmt) => (
          <button
            key={fmt}
            onClick={() => setOptions((prev) => ({ ...prev, format: fmt }))}
            className={cn(
              "flex items-center gap-3 p-4 rounded-xl border-2 transition-all",
              options.format === fmt
                ? "border-brand-500 bg-brand-500/10"
                : "border-dark-400/30 bg-dark-700/30 hover:border-dark-300/30"
            )}
          >
            {fmt === "pdf" ? (
              <FileText className="w-6 h-6 text-red-400" />
            ) : (
              <FileType2 className="w-6 h-6 text-blue-400" />
            )}
            <div className="text-left">
              <p className="font-semibold text-sm text-white">{fmt.toUpperCase()}</p>
              <p className="text-xs text-gray-500">
                {fmt === "pdf" ? "Adobe PDF" : "Word Document"}
              </p>
            </div>
          </button>
        ))}
      </div>

      {/* Options */}
      <div className="space-y-3">
        <div className="flex items-center gap-1.5 text-xs text-gray-400">
          <Settings2 className="w-3.5 h-3.5" />
          <span>Opções de conteúdo</span>
        </div>

        {[
          {
            key: "include_summary" as const,
            label: "Resumo executivo",
            desc: "Incluir análise e resumo da conversa",
          },
          {
            key: "include_media_descriptions" as const,
            label: "Descrições de mídia",
            desc: "Transcrições de áudio, descrições de imagens e vídeos",
          },
          {
            key: "include_sentiment_analysis" as const,
            label: "Análise de sentimento",
            desc: "Indicadores de sentimento por mensagem",
          },
          {
            key: "include_statistics" as const,
            label: "Estatísticas",
            desc: "Tabelas com dados da conversa",
          },
        ].map((opt) => (
          <button
            key={opt.key}
            onClick={() => toggle(opt.key)}
            className="w-full flex items-center gap-3 p-3 rounded-xl bg-dark-700/30 hover:bg-dark-600/40 transition-colors"
          >
            <div
              className={cn(
                "w-9 h-5 rounded-full transition-all relative",
                options[opt.key] ? "bg-brand-500" : "bg-dark-500"
              )}
            >
              <div
                className={cn(
                  "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all",
                  options[opt.key] ? "right-0.5" : "left-0.5"
                )}
              />
            </div>
            <div className="text-left flex-1">
              <p className="text-sm font-medium text-gray-200">{opt.label}</p>
              <p className="text-xs text-gray-500">{opt.desc}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Export Button */}
      <motion.button
        onClick={handleExport}
        disabled={isExporting}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className={cn(
          "w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-semibold transition-all",
          exported
            ? "bg-accent-400 text-dark-900"
            : "bg-brand-500 hover:bg-brand-400 text-white",
          isExporting && "opacity-70 cursor-not-allowed"
        )}
      >
        {isExporting ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Gerando {options.format.toUpperCase()}...
          </>
        ) : exported ? (
          <>
            <CheckCircle2 className="w-5 h-5" />
            Download iniciado!
          </>
        ) : (
          <>
            <FileDown className="w-5 h-5" />
            Exportar como {options.format.toUpperCase()}
          </>
        )}
      </motion.button>
    </div>
  );
}
