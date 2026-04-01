"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sun, Moon, Monitor } from "lucide-react";
import { useTheme, type Theme } from "@/lib/theme";

const options: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Escuro", icon: Moon },
  { value: "system", label: "Sistema", icon: Monitor },
];

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    if (open) {
      document.addEventListener("keydown", handler);
      return () => document.removeEventListener("keydown", handler);
    }
  }, [open]);

  const CurrentIcon = resolvedTheme === "dark" ? Moon : Sun;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        aria-label={`Tema atual: ${theme === "system" ? "Sistema" : theme === "dark" ? "Escuro" : "Claro"}. Clique para alterar.`}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="p-2 rounded-lg text-gray-400 hover:text-white dark:hover:text-white hover:bg-dark-600/50 dark:hover:bg-dark-600/50 light:hover:bg-gray-200 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      >
        <motion.div
          key={resolvedTheme}
          initial={{ rotate: -90, opacity: 0 }}
          animate={{ rotate: 0, opacity: 1 }}
          exit={{ rotate: 90, opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <CurrentIcon className="w-4 h-4" />
        </motion.div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            role="listbox"
            aria-label="Selecionar tema"
            className="absolute right-0 mt-2 w-36 rounded-xl glass dark:glass border border-brand-500/20 dark:border-brand-500/20 shadow-lg overflow-hidden z-50 bg-white dark:bg-transparent"
          >
            {options.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                role="option"
                aria-selected={theme === value}
                onClick={() => {
                  setTheme(value);
                  setOpen(false);
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-sm transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500 ${
                  theme === value
                    ? "text-brand-400 bg-brand-500/10"
                    : "text-gray-400 dark:text-gray-400 hover:text-white dark:hover:text-white hover:bg-dark-600/30 dark:hover:bg-dark-600/30"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
                {theme === value && (
                  <motion.div
                    layoutId="theme-check"
                    className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-400"
                  />
                )}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
