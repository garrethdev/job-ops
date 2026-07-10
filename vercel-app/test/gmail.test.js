import { test } from "node:test";
import assert from "node:assert/strict";
import { mime, looksLikeEmail, b64url, oneLine } from "../lib/mime.js";
import { ensureLabel, createLabeledDraft } from "../lib/gmail.js";

test("mime rejects header injection via crafted To:", () => {
  const out = mime({ to: "a@b.com\r\nBcc: evil@x.com", subject: "hi", body: "hey" });
  assert.ok(!out.includes("Bcc:"), "no injected Bcc header");
  assert.ok(!out.includes("To:"), "crafted multi-token address is dropped entirely");
});

test("mime folds CRLF in the subject to a single header line", () => {
  const out = mime({ to: "", subject: "Hi\r\nX-Injected: 1", body: "b" });
  const subjectLines = out.split("\r\n").filter((l) => l.startsWith("Subject:"));
  assert.equal(subjectLines.length, 1);
  assert.equal(subjectLines[0], "Subject: Hi X-Injected: 1");
  assert.ok(!out.includes("\r\nX-Injected:"));
});

test("mime omits To: when invalid, emits it when valid, keeps required headers", () => {
  assert.ok(!mime({ to: "notanemail", subject: "s", body: "b" }).includes("To:"));
  const out = mime({ to: "jim@diamond.com", subject: "s", body: "b" });
  assert.ok(out.startsWith("To: jim@diamond.com\r\n"));
  assert.ok(out.includes('Content-Type: text/plain; charset="UTF-8"'));
  assert.ok(out.includes("MIME-Version: 1.0"));
});

test("looksLikeEmail accept/reject", () => {
  assert.equal(looksLikeEmail("a@b.com"), true);
  assert.equal(looksLikeEmail("a@b.com, c@d.com"), false);
  assert.equal(looksLikeEmail("a@b"), false);
  assert.equal(looksLikeEmail("notanemail"), false);
  assert.equal(looksLikeEmail(""), false);
});

test("b64url is url-safe and round-trips", () => {
  const s = "a?b>c~d\r\n<e>";
  const enc = b64url(s);
  assert.ok(!/[+/=]/.test(enc));
  assert.equal(Buffer.from(enc, "base64").toString("utf-8"), s);
});

test("oneLine replaces CR/LF runs with a single space and trims", () => {
  assert.equal(oneLine("  a\r\nb\nc  "), "a b c");
  assert.equal(oneLine("x\r\n\r\ny"), "x y");
});

// --- gmail client: mock global fetch, assert call ORDER and failure handling ---
function mockGmail({ labels = [], draftId = "d1", messageId = "m1", failLabelCreate = false, failModify = false } = {}) {
  const calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    const method = opts.method || "GET";
    calls.push(`${method} ${url.replace("https://gmail.googleapis.com/gmail/v1/users/me", "")}`);
    if (url.endsWith("/token")) return { ok: true, json: async () => ({ access_token: "tok" }) };
    if (url.endsWith("/labels") && method === "GET") return { ok: true, json: async () => ({ labels }) };
    if (url.endsWith("/labels") && method === "POST") {
      if (failLabelCreate) return { ok: false, status: 409, text: async () => "exists" };
      return { ok: true, json: async () => ({ id: "L1" }) };
    }
    if (url.endsWith("/drafts")) return { ok: true, json: async () => ({ id: draftId, message: { id: messageId } }) };
    if (url.includes("/messages/") && url.endsWith("/modify")) {
      if (failModify) return { ok: false, status: 500, text: async () => "boom" };
      return { ok: true, json: async () => ({}) };
    }
    return { ok: false, status: 404, text: async () => "unhandled " + url };
  };
  return { calls };
}

const ENV = { GMAIL_CLIENT_ID: "x", GMAIL_CLIENT_SECRET: "y", GMAIL_REFRESH_TOKEN: "z" };
Object.assign(process.env, ENV);

test("ensureLabel: case-insensitive match returns existing id (no create)", async () => {
  mockGmail({ labels: [{ id: "L9", name: "sendouts" }] });
  const id = await ensureLabel("tok", "Sendouts");
  assert.equal(id, "L9");
});

test("ensureLabel: creates when absent", async () => {
  mockGmail({ labels: [] });
  assert.equal(await ensureLabel("tok", "Sendouts"), "L1");
});

test("ensureLabel: create 409 -> refetch finds it", async () => {
  let call = 0;
  globalThis.fetch = async (url, opts = {}) => {
    const method = opts.method || "GET";
    if (url.endsWith("/labels") && method === "GET") {
      call++;
      return { ok: true, json: async () => ({ labels: call === 1 ? [] : [{ id: "Lr", name: "Sendouts" }] }) };
    }
    if (url.endsWith("/labels") && method === "POST") return { ok: false, status: 409, text: async () => "exists" };
    return { ok: false, status: 404, text: async () => "x" };
  };
  assert.equal(await ensureLabel("tok", "Sendouts"), "Lr");
});

test("createLabeledDraft: labels fetched BEFORE draft, modify AFTER", async () => {
  const { calls } = mockGmail({ labels: [] });
  const r = await createLabeledDraft({ to: "a@b.com", subject: "s", body: "b" });
  assert.equal(r.labeled, true);
  const iLabels = calls.findIndex((c) => c === "GET /labels");
  const iDraft = calls.findIndex((c) => c === "POST /drafts");
  const iModify = calls.findIndex((c) => c.includes("/modify"));
  assert.ok(iLabels < iDraft, "label ensured before draft created");
  assert.ok(iDraft < iModify, "draft created before it is labeled");
});

test("createLabeledDraft: modify failure -> draft returned, labeled:false (never throws)", async () => {
  mockGmail({ labels: [{ id: "L9", name: "Sendouts" }], failModify: true });
  const r = await createLabeledDraft({ to: "a@b.com", subject: "s", body: "b" });
  assert.equal(r.labeled, false);
  assert.equal(r.draftId, "d1");
});
