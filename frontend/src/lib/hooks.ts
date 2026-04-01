"use client";

import { useState, useCallback } from "react";
import toast from "react-hot-toast";

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
