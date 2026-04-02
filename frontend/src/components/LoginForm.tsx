"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Brain, LogIn, UserPlus, AlertCircle, Eye, EyeOff } from "lucide-react";
import { login, register } from "@/lib/api";

interface LoginFormProps {
  onLoginSuccess: () => void;
}

export function LoginForm({ onLoginSuccess }: LoginFormProps) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!username.trim() || !password.trim()) {
      setError("Preencha todos os campos.");
      return;
    }

    if (isRegister && password !== confirmPassword) {
      setError("As senhas não coincidem.");
      return;
    }

    if (password.length < 6) {
      setError("A senha deve ter pelo menos 6 caracteres.");
      return;
    }

    setLoading(true);

    try {
      if (isRegister) {
        await register(username.trim(), password);
        // Após registrar, faz login automaticamente
        await login(username.trim(), password);
      } else {
        await login(username.trim(), password);
      }
      onLoginSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("401") || msg.includes("403")) {
        setError("Usuário ou senha incorretos.");
      } else if (msg.includes("409") || msg.includes("already exists")) {
        setError("Este usuário já existe.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6" role="main">
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="relative inline-block mb-4" aria-hidden="true">
            <div className="w-20 h-20 rounded-3xl bg-gradient-brand flex items-center justify-center shadow-glow mx-auto">
              <Brain className="w-10 h-10 text-white" />
            </div>
            <div className="absolute -inset-1 rounded-3xl bg-gradient-brand opacity-20 blur-xl" />
          </div>
          <h1 className="text-3xl font-black">
            <span className="text-gradient">WhatsApp</span>{" "}
            <span className="text-white">Insight</span>
          </h1>
          <p className="text-gray-500 text-sm mt-1">Transcriber</p>
        </div>

        {/* Form Card */}
        <div className="glass rounded-3xl p-8 border border-brand-500/10">
          <h2 className="text-xl font-bold text-white mb-6 text-center">
            {isRegister ? "Criar Conta" : "Entrar"}
          </h2>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              role="alert"
              aria-live="assertive"
              id="form-error"
              className="flex items-center gap-2 p-3 mb-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm"
            >
              <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" aria-describedby={error ? "form-error" : undefined}>
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-400 mb-1.5">
                Usuário
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Seu nome de usuário"
                autoComplete="username"
                required
                aria-required="true"
                className="w-full px-4 py-3 rounded-xl bg-dark-700/50 border border-dark-500/50 text-white placeholder-gray-600 focus:border-brand-500/50 focus:outline-none focus:ring-1 focus:ring-brand-500/30 transition-all"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-400 mb-1.5">
                Senha
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Sua senha"
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  required
                  aria-required="true"
                  minLength={6}
                  className="w-full px-4 py-3 rounded-xl bg-dark-700/50 border border-dark-500/50 text-white placeholder-gray-600 focus:border-brand-500/50 focus:outline-none focus:ring-1 focus:ring-brand-500/30 transition-all pr-12"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" aria-hidden="true" /> : <Eye className="w-4 h-4" aria-hidden="true" />}
                </button>
              </div>
            </div>

            {isRegister && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
              >
                <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-400 mb-1.5">
                  Confirmar Senha
                </label>
                <input
                  id="confirm-password"
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirme sua senha"
                  autoComplete="new-password"
                  required={isRegister}
                  aria-required={isRegister}
                  className="w-full px-4 py-3 rounded-xl bg-dark-700/50 border border-dark-500/50 text-white placeholder-gray-600 focus:border-brand-500/50 focus:outline-none focus:ring-1 focus:ring-brand-500/30 transition-all"
                />
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              aria-busy={loading}
              className="w-full py-3 rounded-xl bg-gradient-brand text-white font-bold shadow-brand hover:shadow-glow transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-900"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : isRegister ? (
                <>
                  <UserPlus className="w-4 h-4" aria-hidden="true" />
                  Criar Conta
                </>
              ) : (
                <>
                  <LogIn className="w-4 h-4" aria-hidden="true" />
                  Entrar
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setIsRegister(!isRegister);
                setError(null);
                setConfirmPassword("");
              }}
              className="text-sm text-brand-400 hover:text-brand-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
            >
              {isRegister
                ? "Já tem uma conta? Faça login"
                : "Não tem conta? Registre-se"}
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-gray-600 mt-4">
          Powered by Claude Opus 4.6 · 20 Agentes de IA
        </p>
      </motion.div>
    </div>
  );
}
