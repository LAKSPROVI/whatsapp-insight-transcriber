"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users, Shield, ShieldOff, UserPlus, Trash2, Key,
  Check, X, AlertCircle, RefreshCw, ChevronLeft,
  UserCheck, UserX, Eye, EyeOff,
} from "lucide-react";
import {
  adminListUsers,
  adminCreateUser,
  adminUpdateUser,
  adminResetPassword,
  adminDeleteUser,
} from "@/lib/api";
import type { UserDetail } from "@/types";
import toast from "react-hot-toast";

interface AdminPanelProps {
  onBack: () => void;
}

export function AdminPanel({ onBack }: AdminPanelProps) {
  const [users, setUsers] = useState<UserDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [resetPasswordUserId, setResetPasswordUserId] = useState<string | null>(null);

  // Create user form
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newFullName, setNewFullName] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [creating, setCreating] = useState(false);

  // Reset password form
  const [resetPassword, setResetPassword] = useState("");
  const [showResetPassword, setShowResetPassword] = useState(false);
  const [resetting, setResetting] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminListUsers();
      setUsers(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Erro ao carregar usuários: ${msg}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newPassword.trim()) {
      toast.error("Preencha usuário e senha.");
      return;
    }
    setCreating(true);
    try {
      await adminCreateUser(newUsername.trim(), newPassword, newFullName.trim());
      toast.success(`Usuário '${newUsername}' criado com sucesso!`);
      setNewUsername("");
      setNewPassword("");
      setNewFullName("");
      setShowCreateForm(false);
      fetchUsers();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (user: UserDetail) => {
    try {
      await adminUpdateUser(user.id, { is_active: !user.is_active });
      toast.success(
        user.is_active
          ? `Usuário '${user.username}' desativado`
          : `Usuário '${user.username}' ativado`
      );
      fetchUsers();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(msg);
    }
  };

  const handleToggleAdmin = async (user: UserDetail) => {
    try {
      await adminUpdateUser(user.id, { is_admin: !user.is_admin });
      toast.success(
        user.is_admin
          ? `Admin removido de '${user.username}'`
          : `'${user.username}' promovido a admin`
      );
      fetchUsers();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(msg);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetPasswordUserId || !resetPassword.trim()) return;
    setResetting(true);
    try {
      await adminResetPassword(resetPasswordUserId, resetPassword);
      toast.success("Senha resetada com sucesso!");
      setResetPasswordUserId(null);
      setResetPassword("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(msg);
    } finally {
      setResetting(false);
    }
  };

  const handleDeleteUser = async (user: UserDetail) => {
    if (!confirm(`Remover o usuário '${user.username}' permanentemente?`)) return;
    try {
      await adminDeleteUser(user.id);
      toast.success(`Usuário '${user.username}' removido`);
      fetchUsers();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(msg);
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "-";
    try {
      return new Date(dateStr).toLocaleString("pt-BR");
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <nav className="glass-dark border-b border-brand-500/10 px-6 py-4 sticky top-0 z-30">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="p-2 rounded-lg hover:bg-dark-700/50 text-gray-400 hover:text-white transition-all"
              aria-label="Voltar"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-brand-400" />
              <h1 className="font-bold text-white text-lg">Gerenciar Usuários</h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchUsers}
              disabled={loading}
              className="p-2 rounded-lg hover:bg-dark-700/50 text-gray-400 hover:text-white transition-all"
              aria-label="Atualizar"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={() => setShowCreateForm(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-gradient-brand text-white text-sm font-semibold shadow-brand hover:shadow-glow transition-all"
            >
              <UserPlus className="w-4 h-4" />
              Novo Usuário
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Create User Modal */}
        <AnimatePresence>
          {showCreateForm && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
              onClick={() => setShowCreateForm(false)}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="glass rounded-2xl p-6 w-full max-w-md border border-brand-500/20"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                  <UserPlus className="w-5 h-5 text-brand-400" />
                  Criar Novo Usuário
                </h3>
                <form onSubmit={handleCreateUser} className="space-y-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Usuário</label>
                    <input
                      type="text"
                      value={newUsername}
                      onChange={(e) => setNewUsername(e.target.value)}
                      placeholder="nome_usuario"
                      required
                      minLength={3}
                      className="w-full px-4 py-2.5 rounded-xl bg-dark-700/50 border border-dark-500/50 text-white placeholder-gray-600 focus:border-brand-500/50 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Nome Completo</label>
                    <input
                      type="text"
                      value={newFullName}
                      onChange={(e) => setNewFullName(e.target.value)}
                      placeholder="Nome completo (opcional)"
                      className="w-full px-4 py-2.5 rounded-xl bg-dark-700/50 border border-dark-500/50 text-white placeholder-gray-600 focus:border-brand-500/50 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Senha</label>
                    <div className="relative">
                      <input
                        type={showNewPassword ? "text" : "password"}
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder="Mínimo 8 chars, 1 maiúscula, 1 número"
                        required
                        minLength={8}
                        className="w-full px-4 py-2.5 rounded-xl bg-dark-700/50 border border-dark-500/50 text-white placeholder-gray-600 focus:border-brand-500/50 focus:outline-none pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPassword(!showNewPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                      >
                        {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                  <div className="flex gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setShowCreateForm(false)}
                      className="flex-1 py-2.5 rounded-xl bg-dark-700/50 text-gray-400 hover:text-white transition-all"
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      disabled={creating}
                      className="flex-1 py-2.5 rounded-xl bg-gradient-brand text-white font-semibold disabled:opacity-50"
                    >
                      {creating ? "Criando..." : "Criar"}
                    </button>
                  </div>
                </form>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Reset Password Modal */}
        <AnimatePresence>
          {resetPasswordUserId && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
              onClick={() => setResetPasswordUserId(null)}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="glass rounded-2xl p-6 w-full max-w-md border border-brand-500/20"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                  <Key className="w-5 h-5 text-yellow-400" />
                  Resetar Senha
                </h3>
                <p className="text-sm text-gray-400 mb-4">
                  Usuário: <span className="text-white font-medium">
                    {users.find((u) => u.id === resetPasswordUserId)?.username}
                  </span>
                </p>
                <form onSubmit={handleResetPassword} className="space-y-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Nova Senha</label>
                    <div className="relative">
                      <input
                        type={showResetPassword ? "text" : "password"}
                        value={resetPassword}
                        onChange={(e) => setResetPassword(e.target.value)}
                        placeholder="Nova senha"
                        required
                        minLength={8}
                        className="w-full px-4 py-2.5 rounded-xl bg-dark-700/50 border border-dark-500/50 text-white placeholder-gray-600 focus:border-brand-500/50 focus:outline-none pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowResetPassword(!showResetPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                      >
                        {showResetPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                  <div className="flex gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => { setResetPasswordUserId(null); setResetPassword(""); }}
                      className="flex-1 py-2.5 rounded-xl bg-dark-700/50 text-gray-400 hover:text-white transition-all"
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      disabled={resetting}
                      className="flex-1 py-2.5 rounded-xl bg-yellow-500/20 text-yellow-400 font-semibold border border-yellow-500/30 disabled:opacity-50"
                    >
                      {resetting ? "Resetando..." : "Resetar Senha"}
                    </button>
                  </div>
                </form>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Users List */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
          </div>
        ) : users.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>Nenhum usuário encontrado</p>
          </div>
        ) : (
          <div className="space-y-3">
            {users.map((user) => (
              <motion.div
                key={user.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`glass rounded-2xl p-4 border ${
                  !user.is_active
                    ? "border-red-500/20 opacity-60"
                    : user.is_admin
                    ? "border-brand-500/20"
                    : "border-dark-500/30"
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white truncate">
                        {user.username}
                      </span>
                      {user.is_admin && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400 text-xs font-medium">
                          <Shield className="w-3 h-3" />
                          Admin
                        </span>
                      )}
                      {!user.is_active && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 text-xs font-medium">
                          <X className="w-3 h-3" />
                          Inativo
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {user.full_name || "Sem nome"} · Criado em {formatDate(user.created_at)}
                    </p>
                  </div>

                  <div className="flex items-center gap-1">
                    {/* Toggle Active */}
                    <button
                      onClick={() => handleToggleActive(user)}
                      className={`p-2 rounded-lg transition-all ${
                        user.is_active
                          ? "text-green-400 hover:bg-green-500/10"
                          : "text-red-400 hover:bg-red-500/10"
                      }`}
                      title={user.is_active ? "Desativar usuário" : "Ativar usuário"}
                    >
                      {user.is_active ? (
                        <UserCheck className="w-4 h-4" />
                      ) : (
                        <UserX className="w-4 h-4" />
                      )}
                    </button>

                    {/* Toggle Admin */}
                    <button
                      onClick={() => handleToggleAdmin(user)}
                      className={`p-2 rounded-lg transition-all ${
                        user.is_admin
                          ? "text-brand-400 hover:bg-brand-500/10"
                          : "text-gray-500 hover:bg-dark-700/50"
                      }`}
                      title={user.is_admin ? "Remover admin" : "Promover a admin"}
                    >
                      {user.is_admin ? (
                        <Shield className="w-4 h-4" />
                      ) : (
                        <ShieldOff className="w-4 h-4" />
                      )}
                    </button>

                    {/* Reset Password */}
                    <button
                      onClick={() => setResetPasswordUserId(user.id)}
                      className="p-2 rounded-lg text-yellow-400 hover:bg-yellow-500/10 transition-all"
                      title="Resetar senha"
                    >
                      <Key className="w-4 h-4" />
                    </button>

                    {/* Delete */}
                    <button
                      onClick={() => handleDeleteUser(user)}
                      className="p-2 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                      title="Excluir usuário"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Summary */}
        {!loading && users.length > 0 && (
          <div className="mt-6 text-center text-sm text-gray-500">
            {users.length} usuário{users.length !== 1 ? "s" : ""} ·{" "}
            {users.filter((u) => u.is_admin).length} admin{users.filter((u) => u.is_admin).length !== 1 ? "s" : ""} ·{" "}
            {users.filter((u) => u.is_active).length} ativo{users.filter((u) => u.is_active).length !== 1 ? "s" : ""}
          </div>
        )}
      </div>
    </div>
  );
}
