"use client";

import DOMPurify from "dompurify";

/**
 * Parses WhatsApp-style formatting and converts to HTML.
 * Supports: *bold*, _italic_, ~strikethrough~, `monospace`, ```code blocks```, URLs
 */
export function formatWhatsAppText(text: string): string {
  if (!text) return "";
  if (typeof window === "undefined") return text;

  let html = escapeHtml(text);

  // Code blocks (```) - must be processed first
  html = html.replace(/```([\s\S]*?)```/g, '<pre class="wa-code-block"><code>$1</code></pre>');

  // Inline code (`)
  html = html.replace(/`([^`\n]+)`/g, '<code class="wa-inline-code">$1</code>');

  // Bold (*text*)
  html = html.replace(/\*([^\s*](?:[^*]*[^\s*])?)\*/g, '<strong class="wa-bold">$1</strong>');

  // Italic (_text_)
  html = html.replace(/\b_([^\s_](?:[^_]*[^\s_])?)_\b/g, '<em class="wa-italic">$1</em>');

  // Strikethrough (~text~)
  html = html.replace(/~([^\s~](?:[^~]*[^\s~])?)~/g, '<del class="wa-strike">$1</del>');

  // URLs - convert to clickable links
  html = html.replace(
    /(https?:\/\/[^\s<>"{}|\\^`[\]]+)/gi,
    '<a href="$1" target="_blank" rel="noopener noreferrer" class="wa-link">$1</a>'
  );

  // Email addresses
  html = html.replace(
    /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g,
    '<a href="mailto:$1" class="wa-link">$1</a>'
  );

  // Phone numbers (Brazilian format)
  html = html.replace(
    /(\+?\d{1,3}[\s.-]?\(?\d{2,3}\)?[\s.-]?\d{4,5}[\s.-]?\d{4})/g,
    '<a href="tel:$1" class="wa-link">$1</a>'
  );

  // Newlines to <br>
  html = html.replace(/\n/g, "<br>");

  // Sanitize to prevent XSS
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["strong", "em", "del", "code", "pre", "a", "br", "span"],
    ALLOWED_ATTR: ["href", "target", "rel", "class"],
  });
}

function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}
