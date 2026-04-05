"use client";

import { useMemo, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Calendar, ChevronDown } from "lucide-react";
import type { Message } from "@/types";
import { cn } from "@/lib/utils";

interface ActivityHeatmapProps {
  messages: Message[];
}

type Period = "1m" | "3m" | "6m" | "1y" | "all";

const PERIOD_LABELS: Record<Period, string> = {
  "1m": "Último mês",
  "3m": "3 meses",
  "6m": "6 meses",
  "1y": "1 ano",
  all: "Tudo",
};

const DAY_LABELS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

function getIntensityClass(count: number, max: number): string {
  if (count === 0) return "bg-gray-200 dark:bg-dark-600";
  const ratio = count / max;
  if (ratio < 0.25) return "bg-emerald-200 dark:bg-emerald-900/60";
  if (ratio < 0.5) return "bg-emerald-400 dark:bg-emerald-700/80";
  if (ratio < 0.75) return "bg-emerald-500 dark:bg-emerald-500";
  return "bg-emerald-700 dark:bg-emerald-400";
}

function getIntensityLabel(count: number, max: number): string {
  if (count === 0) return "Nenhuma mensagem";
  const ratio = count / max;
  if (ratio < 0.25) return "Pouca atividade";
  if (ratio < 0.5) return "Atividade moderada";
  if (ratio < 0.75) return "Atividade alta";
  return "Atividade muito alta";
}

export function ActivityHeatmap({ messages }: ActivityHeatmapProps) {
  const [period, setPeriod] = useState<Period>("3m");
  const [tooltip, setTooltip] = useState<{ date: string; count: number; x: number; y: number } | null>(null);

  const { grid, maxCount, weeks } = useMemo(() => {
    // Build date -> count map
    const dateMap = new Map<string, number>();
    for (const msg of messages) {
      try {
        const key = new Date(msg.timestamp).toISOString().split("T")[0];
        dateMap.set(key, (dateMap.get(key) || 0) + 1);
      } catch {
        // skip
      }
    }

    // Determine date range based on period
    const now = new Date();
    let startDate: Date;
    if (period === "all" && messages.length > 0) {
      const dates = messages
        .map((m) => { try { return new Date(m.timestamp).getTime(); } catch { return 0; } })
        .filter((t) => t > 0);
      startDate = dates.length > 0 ? new Date(Math.min(...dates)) : new Date(now.getTime() - 90 * 86400000);
    } else {
      const months = period === "1m" ? 1 : period === "3m" ? 3 : period === "6m" ? 6 : 12;
      startDate = new Date(now);
      startDate.setMonth(startDate.getMonth() - months);
    }

    // Align to start of week (Sunday)
    startDate.setDate(startDate.getDate() - startDate.getDay());

    // Build grid: array of weeks, each week has 7 days
    const gridData: Array<Array<{ date: string; count: number; dayOfWeek: number }>> = [];
    let max = 0;
    const current = new Date(startDate);
    let currentWeek: Array<{ date: string; count: number; dayOfWeek: number }> = [];

    let safety = 0;
    while (current <= now || currentWeek.length > 0) {
      if (++safety > 10000) break;
      const key = current.toISOString().split("T")[0];
      const count = dateMap.get(key) || 0;
      if (count > max) max = count;

      currentWeek.push({ date: key, count, dayOfWeek: current.getDay() });

      if (currentWeek.length === 7) {
        gridData.push(currentWeek);
        currentWeek = [];
        if (current > now) break;
      }

      current.setDate(current.getDate() + 1);
    }
    if (currentWeek.length > 0) {
      // Pad remaining days
      while (currentWeek.length < 7) {
        currentWeek.push({ date: "", count: 0, dayOfWeek: currentWeek.length });
      }
      gridData.push(currentWeek);
    }

    return { grid: gridData, maxCount: max || 1, weeks: gridData.length };
  }, [messages, period]);

  const handleMouseEnter = useCallback(
    (date: string, count: number, e: React.MouseEvent) => {
      if (!date) return;
      const rect = e.currentTarget.getBoundingClientRect();
      setTooltip({
        date: new Date(date + "T12:00:00").toLocaleDateString("pt-BR", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        }),
        count,
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
      });
    },
    []
  );

  const handleMouseLeave = useCallback(() => setTooltip(null), []);

  return (
    <div className="glass rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-200 dark:text-gray-200 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-emerald-400" aria-hidden="true" />
          Atividade
        </h3>

        {/* Period selector */}
        <div className="relative">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as Period)}
            aria-label="Período do heatmap"
            className="appearance-none bg-dark-700 dark:bg-dark-700 border border-dark-500/30 rounded-lg px-3 py-1 pr-7 text-xs text-gray-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            {(Object.entries(PERIOD_LABELS) as [Period, string][]).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-500 pointer-events-none" />
        </div>
      </div>

      {/* Heatmap grid */}
      <div className="overflow-x-auto">
        <div className="inline-flex gap-0.5" role="grid" aria-label="Heatmap de atividade de mensagens">
          {/* Day labels */}
          <div className="flex flex-col gap-0.5 mr-1 shrink-0" role="rowheader">
            {DAY_LABELS.map((label, i) => (
              <div
                key={i}
                className="h-[14px] flex items-center text-[9px] text-gray-500 dark:text-gray-500"
                style={{ display: i % 2 === 1 ? "flex" : "none" }}
              >
                {label}
              </div>
            ))}
            {/* Spacer for hidden labels */}
            {DAY_LABELS.map((_, i) => (
              i % 2 === 0 ? <div key={`s-${i}`} className="h-[14px]" /> : null
            ))}
          </div>

          {/* Weeks columns */}
          {grid.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-0.5" role="row">
              {week.map((day, di) => (
                <div
                  key={`${wi}-${di}`}
                  role="gridcell"
                  aria-label={day.date ? `${day.date}: ${day.count} mensagens` : ""}
                  className={cn(
                    "w-[14px] h-[14px] rounded-[3px] transition-colors cursor-default",
                    day.date ? getIntensityClass(day.count, maxCount) : "bg-transparent"
                  )}
                  onMouseEnter={(e) => handleMouseEnter(day.date, day.count, e)}
                  onMouseLeave={handleMouseLeave}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-dark-500/20">
        <span className="text-[10px] text-gray-500">Menos</span>
        <div className="flex gap-0.5">
          <div className="w-[14px] h-[14px] rounded-[3px] bg-gray-200 dark:bg-dark-600" />
          <div className="w-[14px] h-[14px] rounded-[3px] bg-emerald-200 dark:bg-emerald-900/60" />
          <div className="w-[14px] h-[14px] rounded-[3px] bg-emerald-400 dark:bg-emerald-700/80" />
          <div className="w-[14px] h-[14px] rounded-[3px] bg-emerald-500 dark:bg-emerald-500" />
          <div className="w-[14px] h-[14px] rounded-[3px] bg-emerald-700 dark:bg-emerald-400" />
        </div>
        <span className="text-[10px] text-gray-500">Mais</span>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 px-2 py-1 bg-dark-800 dark:bg-dark-800 border border-dark-500/30 rounded-lg shadow-lg text-xs text-gray-200 pointer-events-none"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: "translate(-50%, -100%)",
          }}
          role="tooltip"
        >
          <div className="font-medium">{tooltip.date}</div>
          <div className="text-gray-400">
            {tooltip.count} mensagem{tooltip.count !== 1 ? "s" : ""}
          </div>
        </div>
      )}
    </div>
  );
}
