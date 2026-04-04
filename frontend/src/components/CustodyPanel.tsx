"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield, CheckCircle2, XCircle, Loader2, FileText,
  Clock, User, Hash, Link2, Download, RefreshCw,
  ChevronDown, ChevronUp, AlertTriangle, Award
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getCustodyChain, verifyCustodyChain, generateCertificate,
  getAuditEvents,
  type CustodyRecord, type CertificateResponse, type AuditEvent
} from "@/lib/api";
import toast from "react-hot-toast";

interface CustodyPanelProps {
  conversationId: string;
}

type TabId = "chain" | "audit" | "certificate";

export function CustodyPanel({ conversationId }: CustodyPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("chain");
  const [chain, setChain] = useState<CustodyRecord[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [certificate, setCertificate] = useState<CertificateResponse | null>(null);
  const [chainValid, setChainValid] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [verifyCertId, setVerifyCertId] = useState("");
  const [verifyingCert, setVerifyingCert] = useState(false);
  const [certVerifyResult, setCertVerifyResult] = useState<{ valid: boolean } | null>(null);

  const loadChain = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCustodyChain(conversationId);
      setChain(data.records);
    } catch (err) {
      console.error("Failed to load custody chain", err);
    }
    setLoading(false);
  }, [conversationId]);

  const loadAudit = useCallback(async () => {
    try {
      const data = await getAuditEvents(conversationId);
      setAuditEvents(data.events);
    } catch (err) {
      console.error("Failed to load audit events", err);
    }
  }, [conversationId]);

  useEffect(() => {
    loadChain();
    loadAudit();
  }, [loadChain, loadAudit]);

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const result = await verifyCustodyChain(conversationId);
      setChainValid(result.valid);
      if (result.valid) {
        toast.success(`Cadeia integra - ${result.records_checked} registros verificados`);
      } else {
        toast.error(`Cadeia comprometida: ${result.error || "Erro desconhecido"}`);
      }
    } catch (err) {
      toast.error("Erro ao verificar cadeia");
    }
    setVerifying(false);
  };

  const handleGenerateCert = async () => {
    setGenerating(true);
    try {
      const cert = await generateCertificate(conversationId);
      setCertificate(cert);
      toast.success("Certificado gerado com sucesso!");
    } catch (err) {
      toast.error("Erro ao gerar certificado");
    }
    setGenerating(false);
  };

  const handleVerifyCert = async () => {
    if (!verifyCertId.trim()) return;
    setVerifyingCert(true);
    setCertVerifyResult(null);
    try {
      const result = await verifyCertificate(verifyCertId.trim());
      setCertVerifyResult({ valid: result.valid && result.signature_valid && result.chain_valid });
    } catch (err) {
      setCertVerifyResult({ valid: false });
    }
    setVerifyingCert(false);
  };

  const EVENT_COLORS: Record<string, string> = {
    IMPORTED: "text-green-400",
    PROCESSED: "text-blue-400",
    ACCESSED: "text-gray-400",
    EXPORTED: "text-yellow-400",
    VERIFIED: "text-purple-400",
    DELETED: "text-red-400",
  };

  const EVENT_ICONS: Record<string, string> = {
    IMPORTED: "📥",
    PROCESSED: "⚙️",
    ACCESSED: "👁️",
    EXPORTED: "📤",
    VERIFIED: "✅",
    DELETED: "🗑️",
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Shield className="w-5 h-5 text-brand-400" />
        <h3 className="font-semibold text-white">Cadeia de Custodia</h3>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-dark-700/50 rounded-xl p-1">
        {[
          { id: "chain" as TabId, label: "Custodia", icon: Link2 },
          { id: "audit" as TabId, label: "Auditoria", icon: Clock },
          { id: "certificate" as TabId, label: "Certificado", icon: Award },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all",
              activeTab === id
                ? "bg-brand-500/20 text-brand-300"
                : "text-gray-500 hover:text-gray-300"
            )}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Chain Tab */}
      {activeTab === "chain" && (
        <div className="space-y-3">
          {/* Verify button */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleVerify}
              disabled={verifying}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-brand-500/20 hover:bg-brand-500/30 text-brand-300 text-xs font-medium transition-colors"
            >
              {verifying ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
              Verificar Integridade
            </button>
            {chainValid !== null && (
              <span className={cn(
                "flex items-center gap-1 text-xs font-medium",
                chainValid ? "text-green-400" : "text-red-400"
              )}>
                {chainValid ? (
                  <><CheckCircle2 className="w-4 h-4" /> Integra</>
                ) : (
                  <><XCircle className="w-4 h-4" /> Comprometida</>
                )}
              </span>
            )}
          </div>

          {/* Chain records */}
          {loading ? (
            <div className="flex justify-center py-6">
              <Loader2 className="w-6 h-6 animate-spin text-brand-400" />
            </div>
          ) : chain.length === 0 ? (
            <div className="text-center py-6 text-gray-500 text-xs">
              <Shield className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>Nenhum registro de custodia encontrado</p>
            </div>
          ) : (
            <div className="space-y-2">
              {chain.map((record, i) => (
                <CustodyRecordCard key={record.id} record={record} index={i} colors={EVENT_COLORS} icons={EVENT_ICONS} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Audit Tab */}
      {activeTab === "audit" && (
        <div className="space-y-2">
          {auditEvents.length === 0 ? (
            <div className="text-center py-6 text-gray-500 text-xs">
              <Clock className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>Nenhum evento de auditoria</p>
            </div>
          ) : (
            auditEvents.map((event) => (
              <div key={event.id} className="bg-dark-700/30 rounded-xl p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-accent-300">{event.action}</span>
                  <span className="text-[10px] text-gray-600">
                    {event.created_at ? new Date(event.created_at).toLocaleString("pt-BR") : ""}
                  </span>
                </div>
                {event.ip_address && (
                  <p className="text-[10px] text-gray-500">IP: {event.ip_address}</p>
                )}
                {event.details && (
                  <p className="text-[10px] text-gray-500 font-mono">
                    {JSON.stringify(event.details).slice(0, 100)}
                  </p>
                )}
                {event.event_hash && (
                  <p className="text-[9px] text-gray-700 font-mono truncate">Hash: {event.event_hash}</p>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Certificate Tab */}
      {activeTab === "certificate" && (
        <div className="space-y-3">
          <button
            onClick={handleGenerateCert}
            disabled={generating}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-brand-500 hover:bg-brand-400 text-white font-semibold text-sm transition-colors disabled:opacity-50"
          >
            {generating ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Gerando...</>
            ) : (
              <><Award className="w-4 h-4" /> Gerar Certificado de Integridade</>
            )}
          </button>

          {certificate && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-dark-700/50 rounded-xl p-4 space-y-3 border border-accent-400/20"
            >
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-accent-400" />
                <h4 className="font-semibold text-white text-sm">Certificado de Integridade</h4>
              </div>

              <div className="space-y-2">
                <CertRow label="Conversa" value={certificate.conversation_name} />
                <CertRow label="Emitido em" value={new Date(certificate.issued_at).toLocaleString("pt-BR")} />
                <CertRow label="Hash do ZIP" value={certificate.zip_hash || "N/A"} mono />
                <CertRow label="Merkle Root" value={certificate.merkle_root || "N/A"} mono />
                <CertRow label="Assinatura" value={certificate.signature} mono />
                <CertRow label="Arquivos" value={`${certificate.file_count}`} />
                <CertRow label="Mensagens" value={`${certificate.message_count}`} />
                <CertRow
                  label="Cadeia"
                  value={certificate.chain_valid ? "Integra" : "Comprometida"}
                  color={certificate.chain_valid ? "text-green-400" : "text-red-400"}
                />
              </div>

              <div className="pt-2 border-t border-dark-500/20">
                <p className="text-[9px] text-gray-600 leading-relaxed">
                  DECLARACAO DE INTEGRIDADE: Este certificado atesta que os dados importados
                  da conversa acima identificada foram processados sem autorizacao de
                  modificacao do conteudo original. Os hashes criptograficos registrados
                  permitem verificar a integridade de cada arquivo individual e do
                  conjunto completo de dados.
                </p>
              </div>

              <p className="text-[9px] text-gray-700 font-mono">
                ID: {certificate.certificate_id}
              </p>
            </motion.div>
          )}

          {/* Verify Existing Certificate */}
          <div className="pt-3 border-t border-dark-600/30">
            <p className="text-xs text-gray-500 mb-2">Verificar certificado existente:</p>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="ID do certificado..."
                value={verifyCertId}
                onChange={(e) => setVerifyCertId(e.target.value)}
                className="flex-1 px-3 py-2 text-xs bg-dark-700 border border-dark-500/30 rounded-lg text-gray-300 placeholder-gray-600 focus:outline-none focus:border-brand-500/50"
              />
              <button
                onClick={handleVerifyCert}
                disabled={!verifyCertId.trim() || verifyingCert}
                className="px-3 py-2 text-xs bg-dark-600 hover:bg-dark-500 text-gray-300 rounded-lg transition-colors disabled:opacity-50"
              >
                {verifyingCert ? <Loader2 className="w-3 h-3 animate-spin" /> : "Verificar"}
              </button>
            </div>
            {certVerifyResult && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className={`mt-2 p-2 rounded-lg text-xs flex items-center gap-2 ${
                  certVerifyResult.valid
                    ? "bg-green-500/10 border border-green-500/30 text-green-400"
                    : "bg-red-500/10 border border-red-500/30 text-red-400"
                }`}
              >
                {certVerifyResult.valid ? (
                  <><CheckCircle2 className="w-3 h-3" /> Certificado valido. Assinatura e cadeia integras.</>
                ) : (
                  <><XCircle className="w-3 h-3" /> Certificado invalido ou nao encontrado.</>
                )}
              </motion.div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function CustodyRecordCard({
  record,
  index,
  colors,
  icons,
}: {
  record: CustodyRecord;
  index: number;
  colors: Record<string, string>;
  icons: Record<string, string>;
}) {
  const [expanded, setExpanded] = useState(false);
  const color = colors[record.event_type] || "text-gray-400";
  const icon = icons[record.event_type] || "📋";

  return (
    <div className="bg-dark-700/30 rounded-xl p-3 space-y-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm">{icon}</span>
          <span className={cn("text-xs font-semibold", color)}>{record.event_type}</span>
        </div>
        <span className="text-[10px] text-gray-600">
          {record.created_at ? new Date(record.created_at).toLocaleString("pt-BR") : ""}
        </span>
      </div>

      {record.description && (
        <p className="text-xs text-gray-400">{record.description}</p>
      )}

      <div className="flex items-center gap-1">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[9px] text-gray-600 hover:text-gray-400 flex items-center gap-0.5"
        >
          {expanded ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
          {expanded ? "Ocultar" : "Ver"} hashes
        </button>
      </div>

      {expanded && (
        <div className="space-y-0.5 pt-1">
          <p className="text-[9px] text-gray-700 font-mono truncate">Prev: {record.prev_hash}</p>
          <p className="text-[9px] text-gray-700 font-mono truncate">Hash: {record.current_hash}</p>
        </div>
      )}
    </div>
  );
}

function CertRow({ label, value, mono, color }: { label: string; value: string; mono?: boolean; color?: string }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-[10px] text-gray-500 w-24 flex-shrink-0">{label}:</span>
      <span className={cn(
        "text-[10px] break-all",
        mono ? "font-mono text-gray-400" : color || "text-gray-200"
      )}>
        {value}
      </span>
    </div>
  );
}
