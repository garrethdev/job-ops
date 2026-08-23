#!/usr/bin/env node
/**
 * linkedin_outreach.mjs — LOCAL LinkedIn outreach runner (runs on YOUR machine,
 * in a browser YOU are logged into).
 *
 * Model: you approve a batch (2-3 days of comments + DMs) in the job-ops
 * dashboard. This script then posts them AUTOMATICALLY — no per-action pause.
 * You confirm ONCE at the start; after that it works the approved queue on its
 * own, human-paced (randomized delays) and capped per run.
 *
 * Two passes, run on different days:
 *   (default)  comments — posts on leads with contact.li.li_stage = 'approved'
 *   --dm       DMs      — messages leads with contact.li.li_stage = 'commented'
 *              (the second touch, a day or two after the comment)
 *
 * Safety: you are logged in as yourself, you approve everything up front, volume
 * is capped, and delays are randomized. Keep the caps sane — bulk activity risks
 * your account. Use --dry to rehearse (opens + fills, never submits).
 *
 * Setup (once, on the machine):
 *   npm install            # in scripts/  (installs playwright)
 *   npx playwright install chromium
 *   # scripts/.env: SUPABASE_URL + SUPABASE_SERVICE_KEY
 *   node linkedin_preflight.mjs
 *
 * Usage:
 *   node linkedin_outreach.mjs                 # post approved comments
 *   node linkedin_outreach.mjs --dm            # send DMs to commented leads
 *   node linkedin_outreach.mjs --dry           # rehearse, submit nothing
 *   node linkedin_outreach.mjs --yes           # skip the one upfront confirm
 *   node linkedin_outreach.mjs --per-run 8     # cap actions this run (default 5)
 *   node linkedin_outreach.mjs --min 45 --max 120   # delay range in seconds
 */

import { chromium } from "playwright";
import readline from "node:readline";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// --- tiny .env loader ------------------------------------------------------
const __dir = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dir, "..");
for (const f of [path.join(ROOT, ".env"), path.join(process.cwd(), ".env")]) {
  if (fs.existsSync(f)) for (const line of fs.readFileSync(f, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY in env (.env).");
  process.exit(1);
}

const args = process.argv.slice(2);
const has = (f) => args.includes(f);
const val = (f, d) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : d; };
const MODE = has("--dm") ? "dm" : "comment";
const DRY = has("--dry");
const YES = has("--yes");
const PER_RUN = parseInt(val("--per-run", "5"), 10);      // daily cap per run
const MIN_DELAY = parseInt(val("--min", "45"), 10) * 1000; // between actions
const MAX_DELAY = parseInt(val("--max", "120"), 10) * 1000;
const PROFILE_DIR = path.join(ROOT, ".li-profile");        // gitignored; your login

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise((res) => rl.question(q, res));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const jitter = () => MIN_DELAY + Math.floor(Math.random() * Math.max(0, MAX_DELAY - MIN_DELAY));

// --- Supabase REST ---------------------------------------------------------
const sb = (p, init = {}) =>
  fetch(`${SUPABASE_URL}/rest/v1/${p}`, {
    ...init,
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, "Content-Type": "application/json", ...(init.headers || {}) },
  });

async function fetchQueue(stage) {
  const q = `jobops_leads?select=id,company,title,contact,stage&contact->li->>li_stage=eq.${stage}&limit=${PER_RUN}`;
  const r = await sb(q);
  if (!r.ok) throw new Error(`supabase read ${r.status}: ${await r.text()}`);
  return r.json();
}
async function updateLead(id, contact, extra = {}) {
  const r = await sb(`jobops_leads?id=eq.${encodeURIComponent(id)}`, {
    method: "PATCH", headers: { Prefer: "return=minimal" },
    body: JSON.stringify({ contact, updated_at: new Date().toISOString(), ...extra }),
  });
  if (!r.ok) throw new Error(`supabase write ${r.status}: ${await r.text()}`);
}

// --- browser actions -------------------------------------------------------
async function postComment(page, li) {
  await page.goto(li.post_url, { waitUntil: "domcontentloaded" });
  await sleep(2500 + Math.random() * 2000);
  const box = page.locator('[contenteditable="true"][role="textbox"], .comments-comment-box__form [contenteditable="true"], .ql-editor[contenteditable="true"]').first();
  await box.scrollIntoViewIfNeeded({ timeout: 6000 });
  await box.click({ timeout: 6000 });
  await box.type(li.comment, { delay: 20 });
  if (DRY) return "dry";
  const post = page.getByRole("button", { name: /^(post|comment)$/i }).first();
  await post.click({ timeout: 6000 });
  await sleep(2500);
  return "posted";
}

async function sendDM(page, profileUrl, li) {
  await page.goto(profileUrl, { waitUntil: "domcontentloaded" });
  await sleep(2500 + Math.random() * 2000);
  await page.getByRole("button", { name: /message/i }).first().click({ timeout: 8000 });
  const box = page.locator('.msg-form__contenteditable[contenteditable="true"], [contenteditable="true"][role="textbox"]').first();
  await box.click({ timeout: 6000 });
  await box.type(li.dm, { delay: 20 });
  if (DRY) return "dry";
  await page.getByRole("button", { name: /^send$/i }).first().click({ timeout: 6000 });
  await sleep(2500);
  return "sent";
}

// --- main ------------------------------------------------------------------
async function run() {
  const stage = MODE === "dm" ? "commented" : "approved";
  const leads = await fetchQueue(stage);
  const action = MODE === "dm" ? "DM" : "comment";
  if (!leads.length) {
    console.log(`No leads with li_stage='${stage}'. ${MODE === "dm" ? "Post comments first, or" : ""} approve some in the dashboard.`);
    rl.close(); return;
  }

  console.log(`\n${leads.length} ${action}(s) queued (cap ${PER_RUN}/run). Dry run: ${DRY}.`);
  for (const l of leads) {
    const c = l.contact || {}, li = c.li || {};
    console.log(`  • ${l.company} — ${c.name || "?"}: ${(MODE === "dm" ? li.dm : li.comment || "").slice(0, 90)}…`);
  }
  console.log(`Delay between actions: ${MIN_DELAY / 1000}-${MAX_DELAY / 1000}s.`);

  if (!YES && !DRY) {
    const a = (await ask(`\nPost all ${leads.length} ${action}(s) now? (y/N) `)).trim().toLowerCase();
    if (a !== "y" && a !== "yes") { console.log("Aborted."); rl.close(); return; }
  }

  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false, viewport: { width: 1280, height: 900 },
    args: ["--disable-blink-features=AutomationControlled"],
  });
  const page = ctx.pages()[0] || (await ctx.newPage());
  await page.goto("https://www.linkedin.com/feed/", { waitUntil: "domcontentloaded" });
  if (page.url().includes("/login") || page.url().includes("/checkpoint")) {
    await ask("Log into LinkedIn in the open window, then press ENTER... ");
  }

  let done = 0, failed = 0;
  for (let i = 0; i < leads.length; i++) {
    const lead = leads[i], c = lead.contact || {}, li = c.li || {};
    const profileUrl = li.url || c.linkedin || "";
    const who = `${lead.company} — ${c.name || "?"}`;
    try {
      if (MODE === "comment") {
        if (!li.post_url || !li.comment) { console.log(`skip (no post/comment): ${who}`); continue; }
        const r = await postComment(page, li);
        if (r !== "dry") { await updateLead(lead.id, { ...c, li: { ...li, li_stage: "commented", commented_at: new Date().toISOString() } }, { stage: "wip", outreached_at: new Date().toISOString() }); }
        console.log(`✓ ${r === "dry" ? "(dry) " : ""}comment · ${who}`);
      } else {
        if (!profileUrl || !li.dm) { console.log(`skip (no profile/dm): ${who}`); continue; }
        const r = await sendDM(page, profileUrl, li);
        if (r !== "dry") { await updateLead(lead.id, { ...c, li: { ...li, li_stage: "dm_sent", dm_sent_at: new Date().toISOString() } }, { stage: "reached_out" }); }
        console.log(`✓ ${r === "dry" ? "(dry) " : ""}DM · ${who}`);
      }
      done++;
    } catch (e) {
      failed++;
      console.log(`✗ ${who}: ${String(e.message || e).slice(0, 120)}`);
      console.log("  (LinkedIn UI may have changed — this one left in place to retry.)");
    }
    if (i < leads.length - 1) { const d = jitter(); console.log(`  …waiting ${Math.round(d / 1000)}s`); await sleep(d); }
  }

  console.log(`\nDone. ${done} ${action}(s)${DRY ? " (dry, nothing sent)" : ""}, ${failed} failed.`);
  await ctx.close();
  rl.close();
}

run().catch((e) => { console.error(e); rl.close(); process.exit(1); });
