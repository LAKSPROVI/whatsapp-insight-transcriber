"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart2,
  DollarSign,
  MessageSquare,
  Image,
  Clock,
  Database,
  Loader2,
  Calendar,
  ChevronLeft,
  RefreshCw,
  Shield,
  Trash2,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { buildApiUrl, getToken, APIError } from "@/lib/api";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

// ─── Types ──────────────────────────────────────────────────────────────────

interface UsageStats {
  total_conversations: number;
  total_messages: number;
  total_media: number;
  total_chat_messages: number;
  conversations_by_status: Record<string, number>;
  total_tokens_used: number;
  estimated_cost_usd: number;
  active_period_days: number;
  avg_messages_per_conversation: number;
}

interface CostBreakdownEntry {
  period: string;
  tokens_input: number;
  tokens_output: number;
  total_tokens: number;
  estimated_cost_usd: number;
  conversations_processed: number;
  jobs_completed: number;
}

interface RetentionInfo {
  retention_days: string;
  auto_purge_enabled: string;
}

interface DashboardResponse {
  usage: UsageStats;
  cost_breakdown: CostBreakdownEntry[];
  retention_info: RetentionInfo;
}

interface DashboardPanelProps {
  onClose?: () => void;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const PERIOD_OPTIONS = [
  { value: 7, label: "7 dias" },
  { value: 30, label: "30 dias" },
  { value: 90, label: "90 dias" },
] as const;

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("pt-BR");
}

function formatCurrency(value: number): string {
  return `US$ ${value.toFixed(4)}`;
}

// ─── Custom Tooltip ─────────────────────────────────────────────────────────

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string }>;
  label?: string;
}

function ChartTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-dark-800 border border-dark-500/30 rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-sm font-medium text-brand-300">
          {entry.dataKey === "estimated_cost_usd"
            ? formatCurrency(entry.value)
            : formatNumber(entry.value)}
        </p>
      ))}
    </div>
  );
}

// ─── Stat Card ──────────────────────────────────────────────────────────────

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: string;
  subtitle?: string;
  color?: string;
}

function StatCard({ icon: Icon, label, value, subtitle, color = "text-brand-300" }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-dark-700 border border-dark-500/20 rounded-xl p-4 flex items-start gap-3"
    >
      <div className="p-2 rounded-lg bg-brand-500/20 shrink-0">
        <Icon className={cn("w-5 h-5", color)} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-gray-400 truncate">{label}</p>
        <p className={cn("text-lg font-semibold mt-0.5", color)}>{value}</p>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
    </motion.div>
  );
}

// ─── Component ──────────────────────────────────────────────────────────────

export function DashboardPanel({ onClose }: DashboardPanelProps) {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState<number>(30);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboard = useCallback(
    async (showRefresh = false) => {
      if (showRefresh) setRefreshing(true);
      else setLoading(true);

      setError(null);

      try {
        const token = getToken();
        const res = await fetch(buildApiUrl(`/api/dashboard/usage?days=${days}`), {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });

        if (!res.ok) {
          const body = await res.text().catch(() => "");
          throw new APIError(res.status, res.statusText, body);
        }

        const json: DashboardResponse = await res.json();
        setData(json);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Erro ao carregar dashboard.";
        setError(msg);
        toast.error(msg);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [days]
  );

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // ─── Loading ────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="glass rounded-2xl p-8 flex items-center justify-center min-h-[300px]">
        <div className="text-center">
          <Loader2 className="w-10 h-10 text-brand-400 animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-400">Carregando dashboard...</p>
        </div>
      </div>
    );
  }

  // ─── Error ──────────────────────────────────────────────────────────────

  if (error && !data) {
    return (
      <div className="glass rounded-2xl p-8 text-center min-h-[200px] flex flex-col items-center justify-center gap-3">
        <p className="text-red-400 text-sm">{error}</p>
        <button
          onClick={() => fetchDashboard()}
          className="text-sm text-brand-300 hover:text-brand-200 transition-colors underline"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  if (!data) return null;

  const { usage, cost_breakdown, retention_info } = data;
  const autoPurge = String(retention_info.auto_purge_enabled).toLowerCase() === "true";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="glass rounded-2xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-dark-700 transition-colors"
              aria-label="Voltar"
            >
              <ChevronLeft className="w-5 h-5 text-gray-400" />
            </button>
          )}
          <div className="flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-brand-400" />
            <h2 className="text-lg font-semibold text-white">Dashboard de Uso</h2>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Period Selector */}
          <div className="flex bg-dark-800 rounded-lg p-0.5 gap-0.5">
            {PERIOD_OPTIONS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setDays(value)}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                  days === value
                    ? "bg-brand-500/20 text-brand-300 border border-brand-500/30"
                    : "text-gray-400 hover:text-gray-300"
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Refresh */}
          <button
            onClick={() => fetchDashboard(true)}
            disabled={refreshing}
            className="p-2 rounded-lg hover:bg-dark-700 transition-colors text-gray-400 hover:text-gray-300 disabled:opacity-50"
            aria-label="Atualizar"
          >
            <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard
          icon={MessageSquare}
          label="Conversas"
          value={formatNumber(usage.total_conversations)}
          subtitle={`${formatNumber(usage.avg_messages_per_conversation)} msgs/conversa`}
        />
        <StatCard
          icon={Database}
          label="Mensagens Totais"
          value={formatNumber(usage.total_messages)}
          subtitle={`${formatNumber(usage.total_chat_messages)} de chat`}
        />
        <StatCard
          icon={Image}
          label="Mídias"
          value={formatNumber(usage.total_media)}
        />
        <StatCard
          icon={BarChart2}
          label="Tokens Utilizados"
          value={formatNumber(usage.total_tokens_used)}
          color="text-blue-400"
        />
        <StatCard
          icon={DollarSign}
          label="Custo Estimado"
          value={formatCurrency(usage.estimated_cost_usd)}
          color="text-emerald-400"
        />
        <StatCard
          icon={Clock}
          label="Período Ativo"
          value={`${usage.active_period_days} dias`}
          subtitle={Object.entries(usage.conversations_by_status)
            .map(([k, v]) => `${v} ${k}`)
            .join(", ")}
        />
      </div>

      {/* Cost Breakdown Chart */}
      {cost_breakdown.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-2xl p-5"
        >
          <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            Custo por Período
          </h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={cost_breakdown}
                margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis
                  dataKey="period"
                  tick={{ fill: "#9ca3af", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#9ca3af", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar
                  dataKey="estimated_cost_usd"
                  fill="#6C63FF"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={48}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Breakdown Table */}
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-dark-500/20">
                  <th className="text-left py-2 pr-3 font-medium">Período</th>
                  <th className="text-right py-2 px-3 font-medium">Tokens In</th>
                  <th className="text-right py-2 px-3 font-medium">Tokens Out</th>
                  <th className="text-right py-2 px-3 font-medium">Custo</th>
                  <th className="text-right py-2 pl-3 font-medium">Jobs</th>
                </tr>
              </thead>
              <tbody>
                {cost_breakdown.map((entry, i) => (
                  <tr
                    key={i}
                    className="border-b border-dark-500/10 text-gray-300 hover:bg-dark-700/50 transition-colors"
                  >
                    <td className="py-2 pr-3 text-gray-400">{entry.period}</td>
                    <td className="text-right py-2 px-3">{formatNumber(entry.tokens_input)}</td>
                    <td className="text-right py-2 px-3">{formatNumber(entry.tokens_output)}</td>
                    <td className="text-right py-2 px-3 text-emerald-400">
                      {formatCurrency(entry.estimated_cost_usd)}
                    </td>
                    <td className="text-right py-2 pl-3">{entry.jobs_completed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {/* Retention Info */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-2xl p-4 flex items-center gap-3"
      >
        <div className="p-2 rounded-lg bg-dark-700">
          <Shield className="w-4 h-4 text-gray-400" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-gray-300">
            Retenção de dados:{" "}
            <span className="text-white font-medium">{retention_info.retention_days} dias</span>
          </p>
          <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-1">
            {autoPurge ? (
              <>
                <Trash2 className="w-3 h-3" />
                Limpeza automática ativada
              </>
            ) : (
              <>
                <Calendar className="w-3 h-3" />
                Limpeza automática desativada
              </>
            )}
          </p>
        </div>
      </motion.div>
    </div>
  );
}
