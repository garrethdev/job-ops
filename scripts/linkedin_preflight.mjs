#!/usr/bin/env node
/**
 * linkedin_preflight.mjs — verify the machine is ready BEFORE running outreach.
 * Touches no browser and sends nothing. Run this first on any new computer.
 *
 *   node scripts/linkedin_preflight.mjs
 *
 * Checks:
 *   1. .env has SUPABASE_URL + SUPABASE_SERVICE_KEY
 *   2. Supabase reachable + jobops_leads readable
 *   3. Playwright installed and Chromium present
 *   4. How many leads are queued (contact.li.li_stage='approved')
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dir = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dir, "..");
for (const f of [path.join(ROOT, ".env"), path.join(process.cwd(), ".env")]) {
  if (fs.existsSync(f)) for (const line of fs.readFileSync(f, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}

const ok = (m) => console.log(`  \x1b[32m✓\x1b[0m ${m}`);
const bad = (m) => console.log(`  \x1b[31m✗\x1b[0m ${m}`);
let failures = 0;

console.log("\njob-ops · LinkedIn outreach preflight\n");

// 1) env
const URL = process.env.SUPABASE_URL;
const KEY = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;
if (URL && KEY) ok("SUPABASE_URL + SUPABASE_SERVICE_KEY present");
else { bad("Missing SUPABASE_URL and/or SUPABASE_SERVICE_KEY in scripts/.env"); failures++; }

// 2) Supabase read + queued count
if (URL && KEY) {
  try {
    const r = await fetch(
      `${URL}/rest/v1/jobops_leads?select=id&contact->li->>li_stage=eq.approved`,
      { headers: { apikey: KEY, Authorization: `Bearer ${KEY}`, Prefer: "count=exact" } }
    );
    if (!r.ok) { bad(`Supabase read failed: ${r.status} ${(await r.text()).slice(0, 120)}`); failures++; }
    else {
      ok("Supabase reachable, jobops_leads readable");
      const cr = r.headers.get("content-range") || "";      // e.g. "0-4/5"
      const n = cr.includes("/") ? cr.split("/")[1] : "?";
      console.log(`      → ${n} lead(s) approved and waiting for outreach`);
    }
  } catch (e) { bad(`Supabase request error: ${e.message}`); failures++; }
}

// 3) Playwright + Chromium
try {
  const { chromium } = await import("playwright");
  const exe = chromium.executablePath();
  if (exe && fs.existsSync(exe)) ok(`Playwright Chromium installed (${exe})`);
  else { bad("Chromium not installed — run: npx playwright install chromium"); failures++; }
} catch (e) {
  bad("playwright not installed — run: npm install  (in scripts/)"); failures++;
}

console.log(
  failures === 0
    ? "\n\x1b[32mAll good.\x1b[0m Rehearse with:  npm run outreach:dry\n"
    : `\n\x1b[31m${failures} check(s) failed.\x1b[0m Fix the above, then re-run preflight.\n`
);
process.exit(failures === 0 ? 0 : 1);
