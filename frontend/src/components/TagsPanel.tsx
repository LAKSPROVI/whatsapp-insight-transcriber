"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Tag,
  Bookmark,
  Plus,
  X,
  Trash2,
  Loader2,
  MessageSquare,
  Palette,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { buildApiUrl, getToken, APIError } from "@/lib/api";
import toast from "react-hot-toast";

// ─── Types ──────────────────────────────────────────────────────────────────

interface TagsPanelProps {
  conversationId: string;
}

interface UserTag {
  id: string;
  name: string;
  color: string;
  user_id: string;
  created_at: string;
}

interface BookmarkEntry {
  id: string;
  message_id: string;
  conversation_id: string;
  note?: string;
  created_at: string;
}

type TabId = "tags" | "bookmarks";

// ─── Preset Colors ──────────────────────────────────────────────────────────

const PRESET_COLORS = [
  "#ef4444", // red
  "#f97316", // orange
  "#eab308", // yellow
  "#22c55e", // green
  "#06b6d4", // cyan
  "#3b82f6", // blue
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#f43f5e", // rose
  "#14b8a6", // teal
];

// ─── Helpers ────────────────────────────────────────────────────────────────

async function tagsFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(buildApiUrl(path), {
    ...init,
    headers: { ...headers, ...(init?.headers as Record<string, string>) },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new APIError(res.status, res.statusText, body);
  }

  // Handle empty response bodies (e.g. 204 No Content)
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

// ─── Component ──────────────────────────────────────────────────────────────

export function TagsPanel({ conversationId }: TagsPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("tags");

  // Tags state
  const [tags, setTags] = useState<UserTag[]>([]);
  const [loadingTags, setLoadingTags] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [newTagColor, setNewTagColor] = useState(PRESET_COLORS[5]);
  const [creatingTag, setCreatingTag] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [deletingTagId, setDeletingTagId] = useState<string | null>(null);

  // Bookmarks state
  const [bookmarks, setBookmarks] = useState<BookmarkEntry[]>([]);
  const [loadingBookmarks, setLoadingBookmarks] = useState(false);
  const [deletingBookmarkId, setDeletingBookmarkId] = useState<string | null>(null);

  // ─── Load Tags ──────────────────────────────────────────────────────────

  const loadTags = useCallback(async () => {
    setLoadingTags(true);
    try {
      const data = await tagsFetch<any>("/api/tags/");
      setTags(Array.isArray(data) ? data : data.tags ?? []);
    } catch (err) {
      console.error("Failed to load tags", err);
      toast.error("Erro ao carregar tags");
    }
    setLoadingTags(false);
  }, []);

  // ─── Load Bookmarks ────────────────────────────────────────────────────

  const loadBookmarks = useCallback(async () => {
    setLoadingBookmarks(true);
    try {
      const data = await tagsFetch<any>(
        `/api/tags/bookmarks/${conversationId}`
      );
      setBookmarks(Array.isArray(data) ? data : data.bookmarks ?? []);
    } catch (err) {
      console.error("Failed to load bookmarks", err);
      toast.error("Erro ao carregar favoritos");
    }
    setLoadingBookmarks(false);
  }, [conversationId]);

  useEffect(() => {
    loadTags();
    loadBookmarks();
  }, [loadTags, loadBookmarks]);

  // ─── Create Tag ─────────────────────────────────────────────────────────

  const handleCreateTag = async () => {
    const name = newTagName.trim();
    if (!name) return;

    setCreatingTag(true);
    try {
      const tag = await tagsFetch<UserTag>("/api/tags/", {
        method: "POST",
        body: JSON.stringify({ name, color: newTagColor }),
      });
      setTags((prev) => [...prev, tag]);
      setNewTagName("");
      setShowCreateForm(false);
      toast.success("Tag criada com sucesso");
    } catch (err) {
      console.error("Failed to create tag", err);
      toast.error("Erro ao criar tag");
    }
    setCreatingTag(false);
  };

  // ─── Delete Tag ─────────────────────────────────────────────────────────

  const handleDeleteTag = async (tagId: string) => {
    setDeletingTagId(tagId);
    try {
      await tagsFetch<void>(`/api/tags/${tagId}`, { method: "DELETE" });
      setTags((prev) => prev.filter((t) => t.id !== tagId));
      toast.success("Tag removida");
    } catch (err) {
      console.error("Failed to delete tag", err);
      toast.error("Erro ao remover tag");
    }
    setDeletingTagId(null);
  };

  // ─── Delete Bookmark ──────────────────────────────────────────────────

  const handleDeleteBookmark = async (bookmarkId: string) => {
    setDeletingBookmarkId(bookmarkId);
    try {
      await tagsFetch<void>(`/api/tags/bookmarks/${bookmarkId}`, {
        method: "DELETE",
      });
      setBookmarks((prev) => prev.filter((b) => b.id !== bookmarkId));
      toast.success("Favorito removido");
    } catch (err) {
      console.error("Failed to delete bookmark", err);
      toast.error("Erro ao remover favorito");
    }
    setDeletingBookmarkId(null);
  };

  // ─── Render ───────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Tag className="w-5 h-5 text-brand-400" />
        <h3 className="font-semibold text-white">Tags & Favoritos</h3>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-dark-700/50 rounded-xl p-1">
        {(
          [
            { id: "tags" as TabId, label: "Tags", icon: Tag },
            { id: "bookmarks" as TabId, label: "Favoritos", icon: Bookmark },
          ] as const
        ).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all",
              activeTab === id
                ? "bg-brand-500/20 text-brand-300"
                : "text-gray-500 hover:text-gray-300"
            )}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Tags Tab */}
      {activeTab === "tags" && (
        <div className="space-y-3">
          {/* Create tag button / form */}
          <AnimatePresence mode="wait">
            {showCreateForm ? (
              <motion.div
                key="form"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="bg-dark-700/50 rounded-xl p-3 space-y-3 border border-dark-500/20">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-300">
                      Nova Tag
                    </span>
                    <button
                      onClick={() => setShowCreateForm(false)}
                      className="text-gray-500 hover:text-gray-300 transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <input
                    type="text"
                    placeholder="Nome da tag..."
                    value={newTagName}
                    onChange={(e) => setNewTagName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleCreateTag();
                    }}
                    maxLength={32}
                    className="w-full px-3 py-2 text-xs bg-dark-800 border border-dark-500/30 rounded-lg text-gray-300 placeholder-gray-600 focus:outline-none focus:border-brand-500/50 transition-colors"
                  />

                  {/* Color picker */}
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <Palette className="w-3 h-3 text-gray-500" />
                      <span className="text-[10px] text-gray-500">Cor</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {PRESET_COLORS.map((color) => (
                        <button
                          key={color}
                          onClick={() => setNewTagColor(color)}
                          className={cn(
                            "w-6 h-6 rounded-full border-2 transition-all",
                            newTagColor === color
                              ? "border-white scale-110"
                              : "border-transparent hover:border-gray-500"
                          )}
                          style={{ backgroundColor: color }}
                          title={color}
                        />
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={handleCreateTag}
                    disabled={!newTagName.trim() || creatingTag}
                    className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-brand-500/20 hover:bg-brand-500/30 text-brand-300 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {creatingTag ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Plus className="w-3.5 h-3.5" />
                    )}
                    Criar Tag
                  </button>
                </div>
              </motion.div>
            ) : (
              <motion.button
                key="button"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setShowCreateForm(true)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-brand-500/20 hover:bg-brand-500/30 text-brand-300 text-xs font-medium transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Nova Tag
              </motion.button>
            )}
          </AnimatePresence>

          {/* Tags list */}
          {loadingTags ? (
            <div className="flex justify-center py-6">
              <Loader2 className="w-6 h-6 animate-spin text-brand-400" />
            </div>
          ) : tags.length === 0 ? (
            <div className="text-center py-6 text-gray-500 text-xs">
              <Tag className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>Nenhuma tag criada</p>
            </div>
          ) : (
            <div className="space-y-1.5">
              <AnimatePresence>
                {tags.map((tag) => (
                  <motion.div
                    key={tag.id}
                    layout
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 10 }}
                    className="flex items-center justify-between bg-dark-700/30 rounded-xl px-3 py-2.5 group"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-3 h-3 rounded-full flex-shrink-0"
                        style={{ backgroundColor: tag.color }}
                      />
                      <span className="text-xs text-gray-200 truncate">
                        {tag.name}
                      </span>
                    </div>
                    <button
                      onClick={() => handleDeleteTag(tag.id)}
                      disabled={deletingTagId === tag.id}
                      className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all disabled:opacity-50"
                      title="Remover tag"
                    >
                      {deletingTagId === tag.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      )}

      {/* Bookmarks Tab */}
      {activeTab === "bookmarks" && (
        <div className="space-y-2">
          {loadingBookmarks ? (
            <div className="flex justify-center py-6">
              <Loader2 className="w-6 h-6 animate-spin text-brand-400" />
            </div>
          ) : bookmarks.length === 0 ? (
            <div className="text-center py-6 text-gray-500 text-xs">
              <Bookmark className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>Nenhuma mensagem favoritada</p>
            </div>
          ) : (
            <AnimatePresence>
              {bookmarks.map((bookmark) => (
                <motion.div
                  key={bookmark.id}
                  layout
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  className="bg-dark-700/30 rounded-xl p-3 space-y-1.5 group"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <MessageSquare className="w-3 h-3 text-accent-300" />
                      <span className="text-[10px] text-gray-500 font-mono truncate max-w-[180px]">
                        {bookmark.message_id}
                      </span>
                    </div>
                    <button
                      onClick={() => handleDeleteBookmark(bookmark.id)}
                      disabled={deletingBookmarkId === bookmark.id}
                      className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all disabled:opacity-50"
                      title="Remover favorito"
                    >
                      {deletingBookmarkId === bookmark.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>

                  {bookmark.note && (
                    <p className="text-xs text-gray-400 leading-relaxed">
                      {bookmark.note}
                    </p>
                  )}

                  <span className="text-[10px] text-gray-600">
                    {bookmark.created_at
                      ? new Date(bookmark.created_at).toLocaleString("pt-BR")
                      : ""}
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>
          )}
        </div>
      )}
    </div>
  );
}
