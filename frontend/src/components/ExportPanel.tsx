"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  FileDown, FileText, FileType2, Settings2, Loader2, CheckCircle2,
  FileSpreadsheet, Code2, Globe, Database
} from "lucide-react";
import { useExportConversation } from "@/lib/queries";
import type { ExportOptions } from "@/types";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

interface ExportPanelProps {
  conversationId: string;
}

const FORMATS: {
  value: ExportOptions["format"];
  label: string;
  desc: string;
  icon: React.ReactNode;
  color: string;
}[] = [
  { value: "pdf", label: "PDF", desc: "Adobe PDF", icon: <FileText className="w-5 h-5 text-red-400" />, color: "red" },
  { value: "docx", label: "DOCX", desc: "Word Document", icon: <FileType2 className="w-5 h-5 text-blue-400" />, color: "blue" },
  { value: "xlsx", label: "XLSX", desc: "Excel Spreadsheet", icon: <FileSpreadsheet className="w-5 h-5 text-green-400" />, color: "green" },
  { value: "csv", label: "CSV", desc: "Dados tabulares", icon: <Database className="w-5 h-5 text-yellow-400" />, color: "yellow" },
  { value: "html", label: "HTML", desc: "Página web", icon: <Globe className="w-5 h-5 text-orange-400" />, color: "orange" },
  { value: "json", label: "JSON", desc: "Dados estruturados", icon: <Code2 className="w-5 h-5 text-purple-400" />, color: "purple" },
];

export function ExportPanel({ conversationId }: ExportPanelProps) {
  const [options, setOptions] = useState<ExportOptions>({
    format: "pdf",
    include_media_descriptions: true,
    include_sentiment_analysis: true,
    include_summary: true,
    include_statistics: true,
  });
  const [exported, setExported] = useState(false);

  const exportMutation = useExportConversation();

  const handleExport = async () => {
    setExported(false);
    try {
      await exportMutation.mutateAsync({ conversationId, options });
      setExported(true);
      toast.success(`Exportado como ${options.format.toUpperCase()} com sucesso!`);
      setTimeout(() => setExported(false), 3000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      toast.error(`Erro ao exportar: ${message}`);
    }
  };

  const toggle = (key: keyof ExportOptions) => {
    setOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const isExporting = exportMutation.isPending;

  return (
    <div className="glass rounded-2xl p-5 space-y-5" role="region" aria-label="Exportar relatório">
      <div className="flex items-center gap-2">
        <FileDown className="w-5 h-5 text-brand-400" aria-hidden="true" />
        <h3 className="font-semibold text-gray-200">Exportar Relatório</h3>
      </div>

      {/* Format Selection - 3x2 grid */}
      <fieldset className="grid grid-cols-3 gap-2">
        <legend className="sr-only">Formato de exportação</legend>
        {FORMATS.map((fmt) => (
          <button
            key={fmt.value}
            onClick={() => setOptions((prev) => ({ ...prev, format: fmt.value }))}
            aria-pressed={options.format === fmt.value}
            aria-label={`Formato ${fmt.label}`}
            className={cn(
              "flex flex-col items-center gap-1.5 p-3 rounded-xl border-2 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
              options.format === fmt.value
                ? "border-brand-500 bg-brand-500/10"
                : "border-dark-400/30 bg-dark-700/30 hover:border-dark-300/30"
            )}
          >
            {fmt.icon}
            <div className="text-center">
              <p className="font-semibold text-xs text-white">{fmt.label}</p>
              <p className="text-[9px] text-gray-500">{fmt.desc}</p>
            </div>
          </button>
        ))}
      </fieldset>

      {/* Options */}
      <div className="space-y-3">
        <div className="flex items-center gap-1.5 text-xs text-gray-400">
          <Settings2 className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Opções de conteúdo</span>
        </div>

        {[
          { key: "include_summary" as const, label: "Resumo executivo", desc: "Incluir análise e resumo da conversa" },
          { key: "include_media_descriptions" as const, label: "Descrições de mídia", desc: "Transcrições de áudio, descrições de imagens e vídeos" },
          { key: "include_sentiment_analysis" as const, label: "Análise de sentimento", desc: "Indicadores de sentimento por mensagem" },
          { key: "include_statistics" as const, label: "Estatísticas", desc: "Tabelas com dados da conversa" },
        ].map((opt) => (
          <button
            key={opt.key}
            onClick={() => toggle(opt.key)}
            role="switch"
            aria-checked={!!options[opt.key]}
            className="w-full flex items-center gap-3 p-3 rounded-xl bg-dark-700/30 hover:bg-dark-600/40 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div
              className={cn(
                "w-9 h-5 rounded-full transition-all relative",
                options[opt.key] ? "bg-brand-500" : "bg-dark-500"
              )}
              aria-hidden="true"
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
        aria-busy={isExporting}
        className={cn(
          "w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-semibold transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
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
