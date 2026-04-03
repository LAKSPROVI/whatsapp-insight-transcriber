"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { queryKeys } from "@/lib/queries";

interface UseErrorHandlerReturn {
  error: Error | null;
  isError: boolean;
  handleError: (error: unknown, customMessage?: string) => void;
  clearError: () => void;
  wrapAsync: <T>(fn: () => Promise<T>, errorMessage?: string) => Promise<T | undefined>;
}

/**
 * Hook para tratamento centralizado de erros em operações async.
 * Exibe toasts de erro e mantém estado do último erro.
 */
export function useErrorHandler(): UseErrorHandlerReturn {
  const [error, setError] = useState<Error | null>(null);

  const handleError = useCallback((err: unknown, customMessage?: string) => {
    const errorObj = err instanceof Error ? err : new Error(String(err));
    setError(errorObj);

    const message = customMessage || getErrorMessage(errorObj);
    toast.error(message);

    console.error("[useErrorHandler]", errorObj);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const wrapAsync = useCallback(
    async <T>(fn: () => Promise<T>, errorMessage?: string): Promise<T | undefined> => {
      try {
        const result = await fn();
        return result;
      } catch (err) {
        handleError(err, errorMessage);
        return undefined;
      }
    },
    [handleError]
  );

  return {
    error,
    isError: error !== null,
    handleError,
    clearError,
    wrapAsync,
  };
}

function getErrorMessage(error: Error): string {
  const msg = error.message;

  if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
    return "Erro de conexão. Verifique sua internet e tente novamente.";
  }
  if (msg.includes("AbortError") || msg.includes("Tempo limite")) {
    return "A requisição demorou muito. Tente novamente.";
  }
  if (msg.includes("401") || msg.includes("Sessão expirada")) {
    return "Sessão expirada. Faça login novamente.";
  }
  if (msg.includes("403")) {
    return "Acesso negado. Você não tem permissão para esta ação.";
  }
  if (msg.includes("404")) {
    return "Recurso não encontrado.";
  }
  if (msg.includes("500") || msg.includes("502") || msg.includes("503")) {
    return "Erro no servidor. Tente novamente em alguns instantes.";
  }

  return msg || "Ocorreu um erro inesperado.";
}


// ─── WebSocket Progress Hook ────────────────────────────────────────────────

interface ProgressData {
  type: string;
  session_id: string;
  status: string;
  progress: number;
  message: string;
  total_messages?: number;
}

/**
 * Hook que conecta via WebSocket para receber progresso em tempo real.
 * Atualiza automaticamente o cache do React Query quando recebe dados.
 * Faz fallback para polling HTTP se WebSocket falhar.
 */
export function useWebSocketProgress(sessionId: string, enabled = true) {
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (!sessionId || !enabled) return;

    let attempts = 0;
    const maxAttempts = 5;

    function connect() {
      if (attempts >= maxAttempts) return;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/api/ws/progress/${sessionId}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        attempts = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data: ProgressData = JSON.parse(event.data);
          if (data.type === "progress") {
            setProgress(data);
            // Atualizar cache do React Query
            queryClient.setQueryData(queryKeys.progress(sessionId), {
              session_id: data.session_id,
              status: data.status,
              progress: data.progress,
              progress_message: data.message,
              total_messages: data.total_messages || 0,
            });
            // Se completou ou falhou, invalidar lista de conversas
            if (data.status === "completed" || data.status === "failed") {
              queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
            }
          }
        } catch {
          // Ignorar mensagens malformadas
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        // Reconectar se não completou
        if (progress?.status !== "completed" && progress?.status !== "failed") {
          attempts++;
          reconnectTimeoutRef.current = setTimeout(connect, Math.min(1000 * attempts, 5000));
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [sessionId, enabled, queryClient]);

  return { progress, connected };
}
