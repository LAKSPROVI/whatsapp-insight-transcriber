"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("[ErrorBoundary] Erro capturado:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const isDev = process.env.NODE_ENV === "development";

      return (
        <div className="flex flex-col items-center justify-center p-6 rounded-2xl glass border border-red-500/20 bg-red-500/5 min-h-[120px]">
          <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center mb-3">
            <AlertTriangle className="w-6 h-6 text-red-400" />
          </div>
          <h3 className="text-sm font-semibold text-red-300 mb-1">
            Algo deu errado
          </h3>
          <p className="text-xs text-gray-500 mb-3 text-center max-w-xs">
            Ocorreu um erro inesperado nesta seção. As demais continuam funcionando normalmente.
          </p>
          <button
            onClick={this.handleReset}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-500/15 border border-red-500/30 text-red-300 text-xs font-medium hover:bg-red-500/25 transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Tentar novamente
          </button>
          {isDev && this.state.error && (
            <details className="mt-3 w-full max-w-md">
              <summary className="text-[10px] text-gray-600 cursor-pointer hover:text-gray-400 transition-colors">
                Detalhes técnicos (dev)
              </summary>
              <pre className="mt-1 p-2 rounded-lg bg-dark-900/60 text-[10px] text-red-400/80 overflow-x-auto font-mono leading-relaxed">
                {this.state.error.message}
                {"\n"}
                {this.state.error.stack}
              </pre>
            </details>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
