// Gmail client (server-side only): refresh-token -> access token, create a
// draft, ensure the "Sendouts" label exists, and label the draft's message.
// Scope: gmail.modify (re-minted 2026-07-10).

import { mime, b64url } from "./mime.js";

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

// Case-insensitive lookup; if create races and 409s, re-fetch and find it.
export async function ensureLabel(token, name) {
  const target = name.toLowerCase();
  const { labels = [] } = await gfetch(token, "/labels");
  const found = labels.find((l) => (l.name || "").toLowerCase() === target);
  if (found) return found.id;
  try {
    const made = await gfetch(token, "/labels", {
      method: "POST",
      body: JSON.stringify({ name, labelListVisibility: "labelShow", messageListVisibility: "show" }),
    });
    return made.id;
  } catch (e) {
    const { labels: again = [] } = await gfetch(token, "/labels");
    const re = again.find((l) => (l.name || "").toLowerCase() === target);
    if (re) return re.id;
    throw e;
  }
}

/** Create a labeled draft. Returns {draftId, messageId, label, labeled}.
 *  Label the draft AFTER ensuring the label exists; a labeling failure never
 *  fails the whole request (the draft is already the valuable artifact). */
export async function createLabeledDraft({ to, subject, body }) {
  const token = await accessToken();
  let labelId = null;
  try {
    labelId = await ensureLabel(token, OUTREACH_LABEL);
  } catch (e) {
    labelId = null; // proceed unlabeled rather than orphaning a draft
  }
  const draft = await gfetch(token, "/drafts", {
    method: "POST",
    body: JSON.stringify({ message: { raw: b64url(mime({ to, subject, body })) } }),
  });
  const messageId = draft.message && draft.message.id;
  let labeled = false;
  if (messageId && labelId) {
    try {
      await gfetch(token, `/messages/${messageId}/modify`, {
        method: "POST",
        body: JSON.stringify({ addLabelIds: [labelId] }),
      });
      labeled = true;
    } catch (e) {
      labeled = false;
    }
  }
  return { draftId: draft.id, messageId, label: OUTREACH_LABEL, labeled };
}
