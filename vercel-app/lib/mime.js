// Pure MIME/encoding helpers for Gmail draft creation. No I/O — unit-tested in
// test/gmail.test.js. Kept separate from gmail.js so the security-critical
// header-sanitizing logic is reachable without live Gmail credentials.

// Collapse CR/LF to a space so a value can't inject extra headers.
export const oneLine = (s) => String(s || "").replace(/[\r\n]+/g, " ").trim();

// A plausible single email address (no CR/LF, no comma/angle, exactly one @, a dot in the domain).
export const looksLikeEmail = (s) =>
  /^[^\s@,<>]+@[^\s@,<>]+\.[^\s@,<>]+$/.test(oneLine(s));

// URL-safe base64 (Gmail drafts.create wants raw RFC 2822 as base64url).
export const b64url = (s) =>
  Buffer.from(s, "utf-8").toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

// Build an RFC 2822 text/plain message. `to` is only emitted if it validates —
// so a crafted address (or one carrying CR/LF) can never inject a Bcc/header.
export function mime({ to, subject, body }) {
  const safeTo = looksLikeEmail(to) ? oneLine(to) : "";
  return [
    safeTo ? `To: ${safeTo}` : null,
    `Subject: ${oneLine(subject)}`,
    'Content-Type: text/plain; charset="UTF-8"',
    "MIME-Version: 1.0",
    "",
    String(body ?? ""),
  ].filter((l) => l !== null).join("\r\n");
}
