// Gmail client (server-side only): refresh-token -> access token, create a
// draft, ensure the "Sendouts" label exists, and label the draft's message.
// Scope: gmail.modify (re-minted 2026-07-10).

const TOKEN_URL = "https://oauth2.googleapis.com/token";
const API = "https://gmail.googleapis.com/gmail/v1/users/me";

export const OUTREACH_LABEL = "Sendouts";

async function accessToken() {
  const body = new URLSearchParams({
    client_id: process.env.GMAIL_CLIENT_ID,
    client_secret: process.env.GMAIL_CLIENT_SECRET,
    refresh_token: process.env.GMAIL_REFRESH_TOKEN,
    grant_type: "refresh_token",
  });
  const r = await fetch(TOKEN_URL, { method: "POST", body });
  if (!r.ok) throw new Error(`gmail token refresh ${r.status}: ${await r.text()}`);
  return (await r.json()).access_token;
}

async function gfetch(token, path, opts = {}) {
  const r = await fetch(API + path, {
    ...opts,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  if (!r.ok) throw new Error(`gmail ${path} ${r.status}: ${(await r.text()).slice(0, 300)}`);
  return r.json();
}

function b64url(s) {
  return Buffer.from(s, "utf-8").toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function mime({ to, subject, body }) {
  const lines = [
    to ? `To: ${to}` : null,
    `Subject: ${subject.replace(/[\r\n]+/g, " ")}`,
    'Content-Type: text/plain; charset="UTF-8"',
    "MIME-Version: 1.0",
    "",
    body,
  ].filter((l) => l !== null);
  return lines.join("\r\n");
}

async function ensureLabel(token, name) {
  const { labels = [] } = await gfetch(token, "/labels");
  const found = labels.find((l) => l.name === name);
  if (found) return found.id;
  const made = await gfetch(token, "/labels", {
    method: "POST",
    body: JSON.stringify({ name, labelListVisibility: "labelShow", messageListVisibility: "show" }),
  });
  return made.id;
}

/** Create a labeled draft. Returns {draftId, messageId, label}. */
export async function createLabeledDraft({ to, subject, body }) {
  const token = await accessToken();
  const draft = await gfetch(token, "/drafts", {
    method: "POST",
    body: JSON.stringify({ message: { raw: b64url(mime({ to, subject, body })) } }),
  });
  const messageId = draft.message && draft.message.id;
  const labelId = await ensureLabel(token, OUTREACH_LABEL);
  if (messageId) {
    await gfetch(token, `/messages/${messageId}/modify`, {
      method: "POST",
      body: JSON.stringify({ addLabelIds: [labelId] }),
    });
  }
  return { draftId: draft.id, messageId, label: OUTREACH_LABEL };
}
