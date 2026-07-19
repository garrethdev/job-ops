// Pure formatting/sanitizing helpers shared by app.js. No DOM, no I/O — unit
// tested in test/format.test.js. These are the XSS defenses (esc, safeUrl,
// safeEmail) that guard every innerHTML sink, so they must stay pure + tested.

export const esc = (s) =>
  (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Only http(s) links may render as clickable hrefs — blocks javascript:, data:,
// and protocol-relative (//evil.com) URIs from third-party (Apollo/scraped) data.
export const safeUrl = (u) => (/^https?:\/\//i.test((u || "").trim()) ? (u || "").trim() : "");

// Same accept/reject set as lib/mime.js looksLikeEmail (kept in lockstep by test).
export const safeEmail = (e) =>
  (/^[^\s@,<>"]+@[^\s@,<>"]+\.[^\s@,<>"]+$/.test((e || "").trim()) ? (e || "").trim() : "");

export const LANE_LABELS = {
  "gtm-engineer": "GTM Engineer",
  "software-architect": "Software Architect",
  "ai-consultant": "AI Consultant",
  "ai-video-editor": "AI Video Editor",
  "product-lead": "Product Lead",
  "marketing-lead": "Marketing Lead",
  "lookup": "Contact lookup",
};

// Drop a leading "[model-tag]" the scorer prepends to rationales, for display.
export const stripTag = (s) => String(s || "").replace(/^\s*\[[^\]]*\]\s*/, "");

export const laneLabel = (l) => LANE_LABELS[l] || l || "—";

// Sort a lead list in place by the chosen mode. first_seen is ISO-8601, so
// lexical string compare orders it correctly. Default: newest first.
export function sortLeads(list, mode) {
  const byNew = (a, b) => String(b.first_seen || "").localeCompare(String(a.first_seen || ""));
  const cmp = {
    newest: byNew,
    oldest: (a, b) => String(a.first_seen || "").localeCompare(String(b.first_seen || "")),
    fit: (a, b) => (b.fit_score || 0) - (a.fit_score || 0) || byNew(a, b),
  }[mode] || byNew;
  list.sort(cmp);
  return list;
}
export const scoreClass = (s) => (s >= 8 ? "s-hi" : s >= 6 ? "s-mid" : "s-lo");

// Format an ISO timestamp as "Jul 10, 2026" (UTC, so it's deterministic). "" for empty/invalid.
const _MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return `${_MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
};

// Up-to-2-letter initials for a contact avatar. "" / junk -> "?".
export const initials = (name) => {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  const first = parts[0][0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] || "" : "";
  return (first + last).toUpperCase();
};

