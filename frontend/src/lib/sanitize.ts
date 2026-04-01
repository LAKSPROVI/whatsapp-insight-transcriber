import DOMPurify from "dompurify";

/**
 * Sanitiza HTML para prevenir ataques XSS.
 * Remove scripts, event handlers e outros vetores de ataque.
 */
export function sanitizeHTML(html: string): string {
  if (typeof window === "undefined") {
    // SSR: strip all tags as fallback
    return html.replace(/<[^>]*>/g, "");
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "b", "i", "em", "strong", "a", "p", "br", "ul", "ol", "li",
      "code", "pre", "blockquote", "span", "div", "h1", "h2", "h3",
      "h4", "h5", "h6", "table", "thead", "tbody", "tr", "th", "td",
    ],
    ALLOWED_ATTR: ["href", "target", "rel", "class"],
    ALLOW_DATA_ATTR: false,
  });
}

/**
 * Sanitiza texto plano removendo qualquer tag HTML.
 */
export function sanitizeText(text: string): string {
  if (typeof window === "undefined") {
    return text.replace(/<[^>]*>/g, "");
  }
  return DOMPurify.sanitize(text, { ALLOWED_TAGS: [] });
}
