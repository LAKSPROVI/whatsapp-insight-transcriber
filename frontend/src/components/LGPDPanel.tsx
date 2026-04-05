"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  FileText,
  Trash2,
  Download,
  Check,
  X,
  Loader2,
  AlertTriangle,
  ToggleLeft,
  ToggleRight,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { buildApiUrl, getToken } from "@/lib/api";
import toast from "react-hot-toast";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LGPDPanelProps {
  onClose?: () => void;
}

interface ConsentRecord {
  consent_type: string;
  granted: boolean;
  consent_text?: string;
  granted_at?: string;
  revoked_at?: string;
}

interface PrivacyPolicy {
  text: string;
  version?: string;
  updated_at?: string;
}

type ConsentType = "upload_processing" | "data_retention" | "ai_analysis";

const CONSENT_LABELS: Record<ConsentType, { label: string; description: string }> = {
  upload_processing: {
    label: "Processamento de Uploads",
    description:
      "Permite o processamento dos arquivos enviados para transcrição e análise.",
  },
  data_retention: {
    label: "Retenção de Dados",
    description:
      "Permite o armazenamento dos dados processados pelo período definido na política.",
  },
  ai_analysis: {
    label: "Análise por IA",
    description:
      "Permite a utilização de inteligência artificial para análise do conteúdo.",
  },
};

const CONSENT_TYPES: ConsentType[] = [
  "upload_processing",
  "data_retention",
  "ai_analysis",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function lgpdFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(buildApiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as Record<string, string>).detail ||
        (body as Record<string, string>).message ||
        `Erro ${res.status}`
    );
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ConfirmDialog({
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
  loading,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}) {
  return (
    <motion.div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60] p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onCancel}
    >
      <motion.div
        className="glass rounded-2xl p-6 max-w-md w-full space-y-4"
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-red-500/20">
            <AlertTriangle className="w-5 h-5 text-red-400" />
          </div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
        </div>
        <p className="text-gray-300 text-sm leading-relaxed">{message}</p>
        <div className="flex justify-end gap-3 pt-2">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 rounded-xl bg-dark-700/50 text-gray-400 hover:text-white transition-colors disabled:opacity-50"
          >
            Cancelar
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onConfirm}
            disabled={loading}
            className="px-4 py-2 rounded-xl bg-red-500/20 text-red-400 hover:bg-red-500/30 font-semibold transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {confirmLabel}
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
  );
}

function ConsentToggle({
  type,
  granted,
  loading,
  onToggle,
}: {
  type: ConsentType;
  granted: boolean;
  loading: boolean;
  onToggle: (type: ConsentType, value: boolean) => void;
}) {
  const meta = CONSENT_LABELS[type];
  return (
    <motion.div
      className="flex items-start justify-between gap-4 p-4 rounded-xl bg-dark-700/30 border border-dark-500/20"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white">{meta.label}</p>
        <p className="text-xs text-gray-400 mt-1 leading-relaxed">
          {meta.description}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={granted}
        aria-label={`${meta.label}: ${granted ? "ativado" : "desativado"}`}
        disabled={loading}
        onClick={() => onToggle(type, !granted)}
        className="flex-shrink-0 mt-0.5 transition-colors disabled:opacity-50"
      >
        {loading ? (
          <Loader2 className="w-6 h-6 text-brand-400 animate-spin" />
        ) : granted ? (
          <ToggleRight className="w-8 h-8 text-brand-400" />
        ) : (
          <ToggleLeft className="w-8 h-8 text-gray-500" />
        )}
      </button>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function LGPDPanel({ onClose }: LGPDPanelProps) {
  // State
  const [consents, setConsents] = useState<Record<ConsentType, boolean>>({
    upload_processing: false,
    data_retention: false,
    ai_analysis: false,
  });
  const [loadingConsents, setLoadingConsents] = useState(true);
  const [togglingConsent, setTogglingConsent] = useState<ConsentType | null>(null);
  const [privacyPolicy, setPrivacyPolicy] = useState<PrivacyPolicy | null>(null);
  const [loadingPolicy, setLoadingPolicy] = useState(false);
  const [policyExpanded, setPolicyExpanded] = useState(false);
  const [acceptingPolicy, setAcceptingPolicy] = useState(false);
  const [exportingData, setExportingData] = useState(false);
  const [deletingData, setDeletingData] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState<ConsentType | null>(null);

  // -------------------------------------------------------------------------
  // Data fetching
  // -------------------------------------------------------------------------

  const fetchConsents = useCallback(async () => {
    try {
      setLoadingConsents(true);
      const data = await lgpdFetch<ConsentRecord[] | { consents: ConsentRecord[] }>(
        "/api/lgpd/consents"
      );
      const list = Array.isArray(data) ? data : data.consents ?? [];
      const map: Record<string, boolean> = {};
      for (const c of list) {
        map[c.consent_type] = c.granted;
      }
      setConsents({
        upload_processing: map["upload_processing"] ?? false,
        data_retention: map["data_retention"] ?? false,
        ai_analysis: map["ai_analysis"] ?? false,
      });
    } catch (err) {
      toast.error(
        `Erro ao carregar consentimentos: ${err instanceof Error ? err.message : "erro desconhecido"}`
      );
    } finally {
      setLoadingConsents(false);
    }
  }, []);

  const fetchPolicy = useCallback(async () => {
    try {
      setLoadingPolicy(true);
      const data = await lgpdFetch<PrivacyPolicy | { policy: PrivacyPolicy }>(
        "/api/lgpd/privacy-policy"
      );
      const policy = "policy" in data ? data.policy : data;
      setPrivacyPolicy(policy);
    } catch (err) {
      toast.error(
        `Erro ao carregar política: ${err instanceof Error ? err.message : "erro desconhecido"}`
      );
    } finally {
      setLoadingPolicy(false);
    }
  }, []);

  useEffect(() => {
    fetchConsents();
  }, [fetchConsents]);

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------

  const handleToggleConsent = useCallback(
    async (type: ConsentType, value: boolean) => {
      // If revoking, ask for confirmation first
      if (!value) {
        setConfirmRevoke(type);
        return;
      }

      try {
        setTogglingConsent(type);
        await lgpdFetch<unknown>("/api/lgpd/consent", {
          method: "POST",
          body: JSON.stringify({
            consent_type: type,
            granted: true,
            consent_text: CONSENT_LABELS[type].description,
          }),
        });
        setConsents((prev) => ({ ...prev, [type]: true }));
        toast.success("Consentimento registrado com sucesso.");
      } catch (err) {
        toast.error(
          `Erro ao registrar consentimento: ${err instanceof Error ? err.message : "erro desconhecido"}`
        );
      } finally {
        setTogglingConsent(null);
      }
    },
    []
  );

  const handleRevokeConsent = useCallback(async (type: ConsentType) => {
    try {
      setConfirmRevoke(null);
      setTogglingConsent(type);
      await lgpdFetch<unknown>("/api/lgpd/consent/revoke", {
        method: "POST",
        body: JSON.stringify({ consent_type: type }),
      });
      setConsents((prev) => ({ ...prev, [type]: false }));
      toast.success("Consentimento revogado com sucesso.");
    } catch (err) {
      toast.error(
        `Erro ao revogar consentimento: ${err instanceof Error ? err.message : "erro desconhecido"}`
      );
    } finally {
      setTogglingConsent(null);
    }
  }, []);

  const handleExportData = useCallback(async () => {
    try {
      setExportingData(true);
      const token = getToken();
      const res = await fetch(buildApiUrl("/api/lgpd/my-data"), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!res.ok) {
        throw new Error(`Erro ${res.status}`);
      }

      const blob = await res.blob();
      const contentDisposition = res.headers.get("content-disposition");
      let filename = "meus-dados.json";
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^";\s]+)"?/);
        if (match?.[1]) filename = match[1];
      }

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast.success("Dados exportados com sucesso.");
    } catch (err) {
      toast.error(
        `Erro ao exportar dados: ${err instanceof Error ? err.message : "erro desconhecido"}`
      );
    } finally {
      setExportingData(false);
    }
  }, []);

  const handleDeleteData = useCallback(async () => {
    try {
      setConfirmDelete(false);
      setDeletingData(true);
      await lgpdFetch<unknown>("/api/lgpd/delete-my-data", {
        method: "POST",
      });
      toast.success(
        "Solicitação de exclusão de dados registrada. Você será notificado quando o processo for concluído."
      );
    } catch (err) {
      toast.error(
        `Erro ao solicitar exclusão: ${err instanceof Error ? err.message : "erro desconhecido"}`
      );
    } finally {
      setDeletingData(false);
    }
  }, []);

  const handleAcceptPolicy = useCallback(async () => {
    try {
      setAcceptingPolicy(true);
      await lgpdFetch<unknown>("/api/lgpd/accept-privacy-policy", {
        method: "POST",
      });
      toast.success("Política de privacidade aceita.");
    } catch (err) {
      toast.error(
        `Erro ao aceitar política: ${err instanceof Error ? err.message : "erro desconhecido"}`
      );
    } finally {
      setAcceptingPolicy(false);
    }
  }, []);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <>
      <motion.div
        className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="glass rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden"
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          transition={{ type: "spring", damping: 30, stiffness: 300 }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-brand-500/10">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-brand-500/20">
                <Shield className="w-5 h-5 text-brand-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Privacidade & LGPD
                </h2>
                <p className="text-xs text-gray-400">
                  Gerencie seus consentimentos e dados pessoais
                </p>
              </div>
            </div>
            {onClose && (
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={onClose}
                className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-dark-700/50 transition-colors"
                aria-label="Fechar painel"
              >
                <X className="w-5 h-5" />
              </motion.button>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-8">
            {/* ----- Section: Consentimentos ----- */}
            <section aria-labelledby="lgpd-consents-heading">
              <h3
                id="lgpd-consents-heading"
                className="text-sm font-semibold text-gray-200 uppercase tracking-wider mb-4 flex items-center gap-2"
              >
                <Check className="w-4 h-4 text-brand-400" />
                Consentimentos
              </h3>

              {loadingConsents ? (
                <div className="flex items-center justify-center py-8">
                  <div className="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
                </div>
              ) : (
                <div className="space-y-3">
                  {CONSENT_TYPES.map((type) => (
                    <ConsentToggle
                      key={type}
                      type={type}
                      granted={consents[type]}
                      loading={togglingConsent === type}
                      onToggle={handleToggleConsent}
                    />
                  ))}
                </div>
              )}
            </section>

            {/* ----- Section: Seus Dados ----- */}
            <section aria-labelledby="lgpd-data-heading">
              <h3
                id="lgpd-data-heading"
                className="text-sm font-semibold text-gray-200 uppercase tracking-wider mb-4 flex items-center gap-2"
              >
                <Download className="w-4 h-4 text-brand-400" />
                Seus Dados
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleExportData}
                  disabled={exportingData}
                  className="flex items-center gap-3 p-4 rounded-xl bg-dark-700/30 border border-dark-500/20 hover:bg-dark-700/50 transition-colors disabled:opacity-50"
                >
                  {exportingData ? (
                    <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />
                  ) : (
                    <Download className="w-5 h-5 text-brand-400" />
                  )}
                  <div className="text-left">
                    <p className="text-sm font-medium text-white">
                      Exportar Dados
                    </p>
                    <p className="text-xs text-gray-400">
                      Baixe uma cópia dos seus dados
                    </p>
                  </div>
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setConfirmDelete(true)}
                  disabled={deletingData}
                  className="flex items-center gap-3 p-4 rounded-xl bg-dark-700/30 border border-red-500/20 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                >
                  {deletingData ? (
                    <Loader2 className="w-5 h-5 text-red-400 animate-spin" />
                  ) : (
                    <Trash2 className="w-5 h-5 text-red-400" />
                  )}
                  <div className="text-left">
                    <p className="text-sm font-medium text-white">
                      Excluir Dados
                    </p>
                    <p className="text-xs text-gray-400">
                      Solicite a remoção dos seus dados
                    </p>
                  </div>
                </motion.button>
              </div>
            </section>

            {/* ----- Section: Política de Privacidade ----- */}
            <section aria-labelledby="lgpd-policy-heading">
              <h3
                id="lgpd-policy-heading"
                className="text-sm font-semibold text-gray-200 uppercase tracking-wider mb-4 flex items-center gap-2"
              >
                <FileText className="w-4 h-4 text-brand-400" />
                Política de Privacidade
              </h3>

              <div className="rounded-xl bg-dark-700/30 border border-dark-500/20 overflow-hidden">
                <button
                  type="button"
                  onClick={() => {
                    if (!privacyPolicy && !loadingPolicy) fetchPolicy();
                    setPolicyExpanded((v) => !v);
                  }}
                  className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-dark-700/50 transition-colors"
                  aria-expanded={policyExpanded}
                >
                  <span className="text-sm text-gray-200">
                    Ver política de privacidade
                  </span>
                  {policyExpanded ? (
                    <ChevronUp className="w-4 h-4 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  )}
                </button>

                <AnimatePresence>
                  {policyExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="px-4 pb-4 space-y-4">
                        {loadingPolicy ? (
                          <div className="flex items-center justify-center py-8">
                            <div className="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
                          </div>
                        ) : privacyPolicy ? (
                          <>
                            <div className="max-h-64 overflow-y-auto pr-2 text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">
                              {privacyPolicy.text}
                            </div>
                            {privacyPolicy.version && (
                              <p className="text-xs text-gray-500">
                                Versão {privacyPolicy.version}
                                {privacyPolicy.updated_at &&
                                  ` — Atualizada em ${new Date(privacyPolicy.updated_at).toLocaleDateString("pt-BR")}`}
                              </p>
                            )}
                            <motion.button
                              whileHover={{ scale: 1.02 }}
                              whileTap={{ scale: 0.98 }}
                              onClick={handleAcceptPolicy}
                              disabled={acceptingPolicy}
                              className="bg-gradient-brand text-white font-semibold px-4 py-2 rounded-xl shadow-brand hover:shadow-glow transition-all disabled:opacity-50 flex items-center gap-2 text-sm"
                            >
                              {acceptingPolicy ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Check className="w-4 h-4" />
                              )}
                              Aceitar Política de Privacidade
                            </motion.button>
                          </>
                        ) : (
                          <p className="text-xs text-gray-500 py-4 text-center">
                            Não foi possível carregar a política de privacidade.
                          </p>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </section>
          </div>
        </motion.div>
      </motion.div>

      {/* Confirmation dialogs */}
      <AnimatePresence>
        {confirmDelete && (
          <ConfirmDialog
            title="Excluir dados pessoais"
            message="Tem certeza que deseja solicitar a exclusão de todos os seus dados pessoais? Esta ação é irreversível e pode levar até 15 dias para ser processada conforme a LGPD."
            confirmLabel="Sim, excluir meus dados"
            loading={deletingData}
            onConfirm={handleDeleteData}
            onCancel={() => setConfirmDelete(false)}
          />
        )}
        {confirmRevoke !== null && (
          <ConfirmDialog
            title="Revogar consentimento"
            message={`Tem certeza que deseja revogar o consentimento de "${CONSENT_LABELS[confirmRevoke].label}"? Isso pode afetar o funcionamento de alguns recursos.`}
            confirmLabel="Revogar"
            loading={togglingConsent === confirmRevoke}
            onConfirm={() => handleRevokeConsent(confirmRevoke)}
            onCancel={() => setConfirmRevoke(null)}
          />
        )}
      </AnimatePresence>
    </>
  );
}
