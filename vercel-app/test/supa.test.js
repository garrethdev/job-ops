import { test } from "node:test";
import assert from "node:assert/strict";

// supa.js reads env at import time — set it before the dynamic import.
process.env.SUPABASE_URL = "https://supa.test";
process.env.SUPABASE_SERVICE_KEY = "k";
const supa = await import("../lib/supa.js");

// ~10KB upstream error body (e.g. a full HTML error page from PostgREST/CDN).
const HUGE = "boom ".repeat(2000);

test("thrown messages truncate upstream error bodies to 200 chars", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 500, text: async () => HUGE });
  for (const [name, call] of [
    ["list", () => supa.listLeads()],
    ["insert", () => supa.insertLead({ id: "x" })],
    ["patch", () => supa.patchLead("x", {})],
  ]) {
    await assert.rejects(call, (e) => {
      assert.equal(e.message, `supabase ${name} 500: ${HUGE.slice(0, 200)}`);
      return true;
    });
  }
});
