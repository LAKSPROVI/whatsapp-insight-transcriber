"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Calendar, MessageSquare, Users, ChevronDown, ChevronUp } from "lucide-react";
import type { Message } from "@/types";
import { cn, getSenderColor } from "@/lib/utils";

interface TimelineViewProps {
  messages: Message[];
  participants: string[];
  onDayClick?: (date: string) => void;
}

interface DayData {
  date: string;
  dateFormatted: string;
  count: number;
  senders: Record<string, number>;
}

export function TimelineView({ messages, participants, onDayClick }: TimelineViewProps) {
  const [collapsed, setCollapsed] = useState(false);

  const days = useMemo(() => {
    const map = new Map<string, DayData>();
    for (const msg of messages) {
      try {
        const d = new Date(msg.timestamp);
        const key = d.toISOString().split("T")[0];
        const formatted = d.toLocaleDateString("pt-BR", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        });
        if (!map.has(key)) {
          map.set(key, { date: key, dateFormatted: formatted, count: 0, senders: {} });
        }
        const day = map.get(key)!;
        day.count++;
        day.senders[msg.sender] = (day.senders[msg.sender] || 0) + 1;
      } catch {
        // skip invalid timestamp
      }
    }
    return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [messages]);

  const maxCount = useMemo(() => Math.max(...days.map((d) => d.count), 1), [days]);

  if (days.length === 0) {
    return (
      <div className="glass rounded-2xl p-6 text-center">
        <Calendar className="w-8 h-8 mx-auto mb-2 text-gray-500" />
        <p className="text-sm text-gray-400">Nenhum dado de timeline disponível</p>
      </div>
    );
  }

  return (
    <div className="glass rounded-2xl p-4">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between mb-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg p-1"
        aria-expanded={!collapsed}
        aria-label="Alternar timeline visual"
      >
        <h3 className="text-sm font-semibold text-gray-200 dark:text-gray-200 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-brand-400" aria-hidden="true" />
          Timeline da Conversa
        </h3>
        {collapsed ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        )}
      </button>

      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            {/* Mobile: compact list / Desktop: full timeline */}
            <div className="relative pl-6 space-y-1 max-h-[400px] overflow-y-auto scrollbar-thin">
              {/* Vertical line */}
              <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-gradient-to-b from-brand-500/40 via-brand-500/20 to-transparent dark:from-brand-400/40 dark:via-brand-400/20" />

              {days.map((day, i) => {
                const bubbleSize = Math.max(20, Math.min(48, (day.count / maxCount) * 48));
                const activeSenders = Object.keys(day.senders);

                return (
                  <motion.div
                    key={day.date}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: Math.min(i * 0.03, 1), duration: 0.3 }}
                    className="relative flex items-center gap-3 group"
                  >
                    {/* Dot on the timeline */}
                    <div className="absolute left-[-17px] flex items-center justify-center">
                      <div
                        className="rounded-full bg-brand-500 dark:bg-brand-400 border-2 border-dark-800 dark:border-dark-900 transition-transform group-hover:scale-125"
                        style={{ width: 10, height: 10 }}
                      />
                    </div>

                    {/* Card */}
                    <button
                      onClick={() => onDayClick?.(day.date)}
                      className={cn(
                        "flex-1 flex items-center gap-3 p-2 rounded-xl transition-all text-left",
                        "hover:bg-dark-600/50 dark:hover:bg-dark-700/50",
                        "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                      )}
                      aria-label={`${day.dateFormatted}: ${day.count} mensagens`}
                    >
                      {/* Bubble representing volume */}
                      <div
                        className="shrink-0 rounded-full bg-brand-500/20 dark:bg-brand-400/20 flex items-center justify-center"
                        style={{ width: bubbleSize, height: bubbleSize }}
                      >
                        <span className="text-[10px] font-bold text-brand-300">
                          {day.count}
                        </span>
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-gray-300 dark:text-gray-300">
                          {day.dateFormatted}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[10px] text-gray-500 flex items-center gap-0.5">
                            <MessageSquare className="w-3 h-3" aria-hidden="true" />
                            {day.count}
                          </span>
                          <span className="text-[10px] text-gray-500 flex items-center gap-0.5">
                            <Users className="w-3 h-3" aria-hidden="true" />
                            {activeSenders.length}
                          </span>
                        </div>
                      </div>

                      {/* Sender color dots */}
                      <div className="flex -space-x-1 shrink-0">
                        {activeSenders.slice(0, 4).map((sender) => {
                          const color = getSenderColor(sender);
                          return (
                            <div
                              key={sender}
                              className="w-4 h-4 rounded-full border border-dark-800 dark:border-dark-900"
                              style={{ backgroundColor: color }}
                              title={`${sender}: ${day.senders[sender]} msgs`}
                            />
                          );
                        })}
                      </div>
                    </button>
                  </motion.div>
                );
              })}
            </div>

            {/* Legend */}
            <div className="mt-3 pt-3 border-t border-dark-500/20 flex flex-wrap gap-2">
              {participants.map((p) => (
                <div key={p} className="flex items-center gap-1.5 text-[10px] text-gray-500">
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: getSenderColor(p) }}
                  />
                  {p.split(" ")[0]}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
