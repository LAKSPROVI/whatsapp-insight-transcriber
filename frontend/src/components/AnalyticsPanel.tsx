"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart2, Users, TrendingUp, Tag, AlertTriangle,
  Cloud, Clock, Calendar, ChevronDown
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell, Legend
} from "recharts";
import { getAnalytics } from "@/lib/api";
import type { ConversationAnalytics, Conversation } from "@/types";
import { cn, getSenderColor, getSentimentColor, getSentimentEmoji } from "@/lib/utils";

interface AnalyticsPanelProps {
  conversation: Conversation;
}

const COLORS = ["#6C63FF", "#00d4aa", "#ff6b9d", "#ffc107", "#64b5f6", "#a5d6a7"];

export function AnalyticsPanel({ conversation }: AnalyticsPanelProps) {
  const [analytics, setAnalytics] = useState<ConversationAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "sentiment" | "media" | "insights">(
    "overview"
  );

  useEffect(() => {
    getAnalytics(conversation.id)
      .then(setAnalytics)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [conversation.id]);

  if (loading) {
    return (
      <div className="glass rounded-2xl p-8 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 rounded-full border-2 border-transparent border-t-brand-500 animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-400">Carregando análises...</p>
        </div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="glass rounded-2xl p-6 text-center">
        <p className="text-gray-400">Análises não disponíveis</p>
      </div>
    );
  }

  const TABS = [
    { id: "overview", label: "Visão Geral", icon: BarChart2 },
    { id: "sentiment", label: "Sentimento", icon: TrendingUp },
    { id: "media", label: "Mídias", icon: Cloud },
    { id: "insights", label: "Insights", icon: AlertTriangle },
  ];

  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <div className="glass rounded-2xl p-1.5 flex gap-1">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id as typeof activeTab)}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl text-sm transition-all",
              activeTab === id
                ? "bg-brand-500/20 text-brand-300 border border-brand-500/30"
                : "text-gray-500 hover:text-gray-300"
            )}
          >
            <Icon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
        >
          {activeTab === "overview" && <OverviewTab analytics={analytics} conversation={conversation} />}
          {activeTab === "sentiment" && <SentimentTab analytics={analytics} />}
          {activeTab === "media" && <MediaTab analytics={analytics} />}
          {activeTab === "insights" && <InsightsTab analytics={analytics} conversation={conversation} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// ─── Overview Tab ─────────────────────────────────────────────────────────────
function OverviewTab({
  analytics,
  conversation,
}: {
  analytics: ConversationAnalytics;
  conversation: Conversation;
}) {
  // Preparar dados para gráfico de mensagens por dia
  const timelineData = analytics.message_timeline.slice(-30).map((d) => ({
    date: d.date.slice(5), // MM-DD
    Mensagens: d.count,
  }));

  // Dados por participante para gráfico de pizza
  const participantData = analytics.participant_stats.map((p, i) => ({
    name: p.name.split(" ")[0],
    value: p.total_messages,
    color: COLORS[i % COLORS.length],
  }));

  return (
    <div className="space-y-4">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Mensagens", value: conversation.total_messages, icon: "💬", color: "brand" },
          { label: "Mídias", value: conversation.total_media, icon: "📎", color: "accent" },
          { label: "Participantes", value: conversation.participants?.length || 0, icon: "👥", color: "purple" },
          { label: "Dias", value: analytics.message_timeline.length, icon: "📅", color: "yellow" },
        ].map((stat) => (
          <div key={stat.label} className="glass rounded-xl p-4">
            <span className="text-2xl">{stat.icon}</span>
            <p className="text-2xl font-bold text-white mt-2">{stat.value}</p>
            <p className="text-xs text-gray-400">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Timeline Chart */}
      {timelineData.length > 1 && (
        <div className="glass rounded-2xl p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-1.5">
            <Calendar className="w-4 h-4 text-brand-400" />
            Atividade por Dia (últimos 30 dias)
          </h4>
          <ResponsiveContainer width="100%" height={150}>
            <AreaChart data={timelineData}>
              <defs>
                <linearGradient id="colorMsg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6C63FF" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6C63FF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#666" }} />
              <YAxis tick={{ fontSize: 10, fill: "#666" }} />
              <Tooltip
                contentStyle={{
                  background: "#1a1a35",
                  border: "1px solid rgba(108,99,255,0.3)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <Area
                type="monotone"
                dataKey="Mensagens"
                stroke="#6C63FF"
                strokeWidth={2}
                fill="url(#colorMsg)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Participantes */}
      <div className="glass rounded-2xl p-4">
        <h4 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-1.5">
          <Users className="w-4 h-4 text-accent-400" />
          Participantes
        </h4>
        <div className="space-y-3">
          {analytics.participant_stats.map((p, i) => {
            const color = COLORS[i % COLORS.length];
            const pct = Math.round((p.total_messages / conversation.total_messages) * 100);
            return (
              <div key={p.name} className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium" style={{ color }}>
                    {p.name}
                  </span>
                  <div className="flex gap-3 text-xs text-gray-400">
                    <span>{p.total_messages} msgs</span>
                    <span>{p.total_media} mídias</span>
                    {p.avg_sentiment !== undefined && (
                      <span className={getSentimentColor(p.avg_sentiment > 0.3 ? "positive" : p.avg_sentiment < -0.3 ? "negative" : "neutral")}>
                        {getSentimentEmoji(p.avg_sentiment > 0.3 ? "positive" : p.avg_sentiment < -0.3 ? "negative" : "neutral")}
                      </span>
                    )}
                  </div>
                </div>
                <div className="h-1.5 bg-dark-600 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.8, delay: i * 0.1 }}
                    className="h-full rounded-full"
                    style={{ backgroundColor: color }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Topics */}
      {conversation.topics && conversation.topics.length > 0 && (
        <div className="glass rounded-2xl p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-1.5">
            <Tag className="w-4 h-4 text-brand-400" />
            Principais Tópicos
          </h4>
          <div className="flex flex-wrap gap-2">
            {conversation.topics.map((topic) => (
              <span
                key={topic}
                className="px-3 py-1 rounded-full text-xs bg-brand-500/10 border border-brand-500/20 text-brand-300"
              >
                {topic}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sentiment Tab ────────────────────────────────────────────────────────────
function SentimentTab({ analytics }: { analytics: ConversationAnalytics }) {
  const sentimentData = analytics.sentiment_timeline
    .slice(0, 100)
    .map((d, i) => ({
      i,
      score: d.score,
      sender: d.sender,
    }));

  return (
    <div className="space-y-4">
      {sentimentData.length > 0 ? (
        <div className="glass rounded-2xl p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-accent-400" />
            Linha do Tempo de Sentimento
          </h4>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={sentimentData}>
              <defs>
                <linearGradient id="posGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00d4aa" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00d4aa" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="negGrad" x1="0" y1="1" x2="0" y2="0">
                  <stop offset="5%" stopColor="#ff6b6b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ff6b6b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="i" hide />
              <YAxis domain={[-1, 1]} tick={{ fontSize: 10, fill: "#666" }} />
              <Tooltip
                contentStyle={{
                  background: "#1a1a35",
                  border: "1px solid rgba(108,99,255,0.3)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                formatter={(value: number | string) => [Number(value).toFixed(2), "Sentimento"]}
              />
              <Area
                type="monotone"
                dataKey="score"
                stroke="#6C63FF"
                strokeWidth={2}
                fill="url(#posGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-6 mt-2 text-xs">
            <span className="flex items-center gap-1 text-accent-400">
              <span>▲</span> Positivo
            </span>
            <span className="flex items-center gap-1 text-gray-400">
              <span>─</span> Neutro
            </span>
            <span className="flex items-center gap-1 text-red-400">
              <span>▼</span> Negativo
            </span>
          </div>
        </div>
      ) : (
        <div className="glass rounded-2xl p-6 text-center text-gray-500 text-sm">
          Dados de sentimento não disponíveis
        </div>
      )}
    </div>
  );
}

// ─── Media Tab ────────────────────────────────────────────────────────────────
function MediaTab({ analytics }: { analytics: ConversationAnalytics }) {
  const mediaEntries = Object.entries(analytics.media_breakdown).filter(
    ([k]) => k !== "text" && k !== "deleted"
  );

  const MEDIA_COLORS: Record<string, string> = {
    image: "#6C63FF",
    audio: "#00d4aa",
    video: "#ff6b9d",
    document: "#ffc107",
    sticker: "#64b5f6",
  };

  const pieData = mediaEntries.map(([type, count]) => ({
    name: type,
    value: count,
    color: MEDIA_COLORS[type] || "#888",
  }));

  // Word cloud data
  const wordData = analytics.word_cloud_data.slice(0, 30);

  return (
    <div className="space-y-4">
      {/* Mídia breakdown */}
      {pieData.length > 0 && (
        <div className="glass rounded-2xl p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-4">Distribuição de Mídias</h4>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width={140} height={140}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={60}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-2">
              {pieData.map((d) => (
                <div key={d.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: d.color }} />
                    <span className="text-xs text-gray-300 capitalize">{d.name}</span>
                  </div>
                  <span className="text-xs font-medium text-white">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Word Cloud */}
      {wordData.length > 0 && (
        <div className="glass rounded-2xl p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-1.5">
            <Cloud className="w-4 h-4 text-brand-400" />
            Palavras Mais Frequentes
          </h4>
          <div className="flex flex-wrap gap-2">
            {wordData.map((w, i) => {
              const maxVal = wordData[0]?.value || 1;
              const size = 10 + (w.value / maxVal) * 16;
              const opacity = 0.4 + (w.value / maxVal) * 0.6;
              return (
                <span
                  key={w.text}
                  className="inline-block"
                  style={{
                    fontSize: `${size}px`,
                    color: COLORS[i % COLORS.length],
                    opacity,
                  }}
                >
                  {w.text}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Insights Tab ─────────────────────────────────────────────────────────────
function InsightsTab({
  analytics,
  conversation,
}: {
  analytics: ConversationAnalytics;
  conversation: Conversation;
}) {
  return (
    <div className="space-y-4">
      {/* Resumo */}
      {conversation.summary && (
        <div className="glass rounded-2xl p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-3">📝 Resumo Executivo</h4>
          <p className="text-sm text-gray-300 leading-relaxed">{conversation.summary}</p>
        </div>
      )}

      {/* Momentos-chave */}
      {analytics.key_moments.length > 0 && (
        <div className="glass rounded-2xl p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-1.5">
            ⭐ Momentos-Chave
          </h4>
          <div className="space-y-2">
            {analytics.key_moments.map((km, i) => (
              <div
                key={i}
                className="flex gap-3 p-3 rounded-xl bg-brand-500/5 border border-brand-500/10"
              >
                <span className="text-brand-400 text-lg mt-0.5">◆</span>
                <div>
                  {km.timestamp_approx && (
                    <p className="text-[10px] text-gray-500 mb-0.5">{km.timestamp_approx}</p>
                  )}
                  <p className="text-sm text-gray-300">{km.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Contradições */}
      {analytics.contradictions.length > 0 && (
        <div className="glass rounded-2xl p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            Contradições Detectadas ({analytics.contradictions.length})
          </h4>
          <div className="space-y-2">
            {analytics.contradictions.map((c, i) => (
              <div
                key={i}
                className={cn(
                  "p-3 rounded-xl border",
                  c.severity === "high"
                    ? "bg-red-500/5 border-red-500/20"
                    : c.severity === "medium"
                    ? "bg-yellow-500/5 border-yellow-500/20"
                    : "bg-dark-600/30 border-dark-400/20"
                )}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  {c.participant && (
                    <span className="text-xs font-medium text-brand-300">{c.participant}</span>
                  )}
                  {c.severity && (
                    <span
                      className={cn(
                        "text-[9px] px-2 py-0.5 rounded-full",
                        c.severity === "high"
                          ? "bg-red-500/20 text-red-300"
                          : c.severity === "medium"
                          ? "bg-yellow-500/20 text-yellow-300"
                          : "bg-gray-500/20 text-gray-300"
                      )}
                    >
                      {c.severity}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-300">{c.description}</p>
                {(c.statement_1 || c.statement_2) && (
                  <div className="mt-2 space-y-1 text-xs text-gray-500">
                    {c.statement_1 && <p>• "{c.statement_1}"</p>}
                    {c.statement_2 && <p>• "{c.statement_2}"</p>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sem insights */}
      {analytics.key_moments.length === 0 && analytics.contradictions.length === 0 && !conversation.summary && (
        <div className="glass rounded-2xl p-8 text-center">
          <span className="text-4xl">🔍</span>
          <p className="text-gray-400 mt-3">Análises avançadas em andamento...</p>
        </div>
      )}
    </div>
  );
}
