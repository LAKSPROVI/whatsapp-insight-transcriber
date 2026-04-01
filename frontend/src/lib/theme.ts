"use client";

import { useState, useEffect, useCallback } from "react";

export type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "wit-theme-preference";

function getSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  const resolved = theme === "system" ? getSystemTheme() : theme;
  const html = document.documentElement;
  if (resolved === "dark") {
    html.classList.add("dark");
    html.classList.remove("light");
  } else {
    html.classList.add("light");
    html.classList.remove("dark");
  }
  // Update meta theme-color
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute("content", resolved === "dark" ? "#0a0a14" : "#f8f9ff");
  }
}

function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {}
  return "dark";
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>("dark");

  // Initialize on mount
  useEffect(() => {
    const stored = getStoredTheme();
    setThemeState(stored);
    applyTheme(stored);
  }, []);

  // Listen for system theme changes
  useEffect(() => {
    if (theme !== "system") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyTheme("system");
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [theme]);

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
    try {
      localStorage.setItem(STORAGE_KEY, newTheme);
    } catch {}
    applyTheme(newTheme);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next = prev === "dark" ? "light" : prev === "light" ? "system" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {}
      applyTheme(next);
      return next;
    });
  }, []);

  const resolvedTheme = theme === "system" ? getSystemTheme() : theme;

  return { theme, resolvedTheme, toggleTheme, setTheme };
}
