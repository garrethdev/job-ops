import crypto from "crypto";

// Byte-for-byte port of core/schema.py normalize_company / normalize_title /
// make_id, so a lead created on the JS path gets the SAME id as the Python
// pipeline — otherwise Supabase merge-duplicates dedupe is silently defeated
// ("Vercel Inc" must hash identically in both). Parity is locked by
// tests/fixtures/id_vectors.json (Python: tests/test_id_contract.py, JS:
// test/id-parity.test.js). Keep the order of operations identical to Python.

const LEGAL = /\b(inc|llc|ltd|limited|gmbh|corp|co|company|plc|ab|as|oy|bv)\b/g;

export function normalizeCompany(company) {
  let s = String(company || "").toLowerCase().trim();
  s = s.replace(/[.,]/g, " ");
  s = s.replace(LEGAL, " ");
  s = s.replace(/[^a-z0-9 ]/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

export function normalizeTitle(title) {
  let s = String(title || "").toLowerCase().trim();
  s = s.replace(/[^a-z0-9 ]/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

export function makeId(company, title) {
  const key = normalizeCompany(company) + "|" + normalizeTitle(title);
  return crypto.createHash("sha1").update(key, "utf-8").digest("hex");
}
