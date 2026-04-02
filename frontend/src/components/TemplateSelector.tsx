"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Check, ChevronRight, Sparkles } from "lucide-react";
import { useTemplates, useTemplateAnalysis } from "@/lib/queries";
import type { Template, TemplateAnalysisResult } from "@/types";
import { cn } from "@/lib/utils";

interface TemplateSelectorProps {
  conversationId: string;
}

const TEMPLATE_ICONS: Record<string, string> = {
  juridico: "⚖️",
  legal: "⚖️",
  comercial: "💼",
  business: "💼",
  familiar: "👨‍👩‍👧",
  family: "👨‍👩‍👧",
  rh: "🏢",
  hr: "🏢",
  geral: "📊",
  general: "📊",
  default: "📋",
};

function getTemplateIcon(template: Template): string {
  const idLower = template.id.toLowerCase();
  const nameLower = template.name.toLowerCase();

  for (const [key, icon] of Object.entries(TEMPLATE_ICONS)) {
    if (idLower.includes(key) || nameLower.includes(key)) return icon;
  }
  return TEMPLATE_ICONS.default;
}

export function TemplateSelector({ conversationId }: TemplateSelectorProps) {
  const { data, isLoading: loadingTemplates } = useTemplates();
  const analysisMutation = useTemplateAnalysis();
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [confirmTemplate, setConfirmTemplate] = useState<string | null>(null);
  const [result, setResult] = useState<TemplateAnalysisResult | null>(null);

  const handleSelect = useCallback((templateId: string) => {
    if (confirmTemplate === templateId) {
      // Already confirming — execute
      setSelectedTemplate(templateId);
      setConfirmTemplate(null);
      setResult(null);
      analysisMutation.mutate(
        { templateId, conversationId },
        {
          onSuccess: (data) => setResult(data),
          onError: () => setSelectedTemplate(null),
        }
      );
    } else {
      setConfirmTemplate(templateId);
    }
  }, [confirmTemplate, conversationId, analysisMutation]);

  const templates = data?.templates || [];

  if (loadingTemplates) {
    return (
      <div className="glass rounded-2xl p-6 text-center">
        <Loader2 className="w-6 h-6 mx-auto animate-spin text-brand-400 mb-2" />
        <p className="text-xs text-gray-400">Carregando templates...</p>
      </div>
    );
  }

  if (templates.length === 0) {
    return null;
  }

  return (
    <div className="glass rounded-2xl p-4">
      <h3 className="text-sm font-semibold text-gray-200 dark:text-gray-200 flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-brand-400" aria-hidden="true" />
        Templates de Análise
      </h3>

      <div className="space-y-2">
        {templates.map((template) => {
          const icon = getTemplateIcon(template);
          const isConfirming = confirmTemplate === template.id;
          const isAnalyzing = selectedTemplate === template.id && analysisMutation.isPending;
          const isSelected = selectedTemplate === template.id;
          const hasResult = isSelected && result;

          return (
            <motion.div
              key={template.id}
              layout
              className={cn(
                "rounded-xl border transition-all overflow-hidden",
                isConfirming
                  ? "border-brand-500/40 bg-brand-500/5"
                  : isSelected
                  ? "border-brand-500/30 bg-dark-600/30"
                  : "border-dark-500/20 bg-dark-700/30 hover:bg-dark-600/30"
              )}
            >
              <button
                onClick={() => !isAnalyzing && handleSelect(template.id)}
                disabled={isAnalyzing}
                className="w-full text-left p-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-xl"
                aria-label={`Template: ${template.name}`}
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl shrink-0" aria-hidden="true">{icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-medium text-gray-200 truncate">
                        {template.name}
                      </h4>
                      {isAnalyzing && (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-400 shrink-0" />
                      )}
                      {hasResult && !analysisMutation.isPending && (
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      )}
                    </div>
                    <p className="text-[11px] text-gray-400 mt-0.5 line-clamp-2">
                      {template.description}
                    </p>

                    {/* Prompt list */}
                    <div className="flex flex-wrap gap-1 mt-2">
                      {Object.keys(template.prompts).map((key) => (
                        <span
                          key={key}
                          className="text-[9px] px-1.5 py-0.5 rounded-full bg-dark-600 dark:bg-dark-600 text-gray-400 border border-dark-500/20"
                        >
                          {key}
                        </span>
                      ))}
                    </div>
                  </div>
                  <ChevronRight
                    className={cn(
                      "w-4 h-4 shrink-0 transition-transform text-gray-500",
                      isConfirming && "rotate-90 text-brand-400"
                    )}
                  />
                </div>

                {/* Confirmation message */}
                <AnimatePresence>
                  {isConfirming && !isAnalyzing && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="mt-2 pt-2 border-t border-brand-500/20"
                    >
                      <p className="text-[11px] text-brand-300">
                        Clique novamente para executar a análise com este template
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </button>

              {/* Analysis Result */}
              <AnimatePresence>
                {hasResult && !analysisMutation.isPending && result && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="border-t border-dark-500/20"
                  >
                    <div className="p-3 space-y-3">
                      <div className="flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-[11px] font-medium text-emerald-300">
                          Análise concluída
                        </span>
                        <span className="text-[9px] text-gray-500">
                          ({result.executed_prompts.length} prompt{result.executed_prompts.length !== 1 ? "s" : ""})
                        </span>
                      </div>

                      {Object.entries(result.results).map(([key, value]) => (
                        <div key={key} className="rounded-lg bg-dark-700/50 p-2.5">
                          <h5 className="text-[10px] font-medium text-brand-300 uppercase tracking-wider mb-1.5">
                            {key}
                          </h5>
                          <p className="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed">
                            {value}
                          </p>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Error state */}
              {isSelected && analysisMutation.isError && (
                <div className="p-3 border-t border-red-500/20">
                  <p className="text-[11px] text-red-400">
                    Erro ao executar análise: {analysisMutation.error?.message || "tente novamente"}
                  </p>
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
