#!/usr/bin/env node
/**
 * linkedin_outreach.mjs — LOCAL, human-in-the-loop LinkedIn outreach runner.
 *
 * Runs on YOUR Mac, in a browser YOU are logged into. It does NOT bypass
 * LinkedIn auth, does NOT use bot actors, and never submits anything without
 * you pressing a key. This keeps it a manual assist (you drive), which is the
 * lowest-risk way to act on your own account.
 *
 * Flow:
 *   1. Pull leads from Supabase where contact.li_stage = 'approved'
 *      (drafted + approved in the job-ops dashboard).
 *   2. Open a persistent Chromium profile (you log into LinkedIn ONCE; the
 *      session is remembered under .li-profile/).
 *   3. For each lead: open the post, pre-fill the approved comment, then PAUSE.
 *      You read it, edit if needed, and press ENTER to post (or 's' to skip).
 *   4. Optional second touch: open the profile, start a message, pre-fill the
 *      approved DM, PAUSE again, you press ENTER to send.
 *   5. Mark contact.li_stage = 'commented' / 'dm_sent', set outreached_at.
 *
 * Setup (once, on your Mac):
 *   npm i playwright dotenv
 *   npx playwright install chromium
 *   echo "SUPABASE_URL=...\nSUPABASE_SERVICE_KEY=..." >> .env   # service role key
 *   node scripts/linkedin_outreach.mjs            # first run: log into LinkedIn
 *
 * Flags:
 *   --limit N     max leads this run (default 5 — keep it human-paced)
 *   --dm          also do the DM step (default: comment only)
 *   --dry         open + pre-fill but never submit (rehearsal)
 */

import { chromium } from "playwright";
import readline from "node:readline";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// --- tiny .env loader (avoids a hard dep) ----------------------------------
const __dir = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dir, "..");
for (const f of [path.join(ROOT, ".env"), path.join(process.cwd(), ".env")]) {
  if (fs.existsSync(f)) {
    for (const line of fs.readFileSync(f, "utf8").split("\n")) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
      if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
    }
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
const LIMIT = parseInt(val("--limit", "5"), 10);
const DO_DM = has("--dm");
const DRY = has("--dry");
const PROFILE_DIR = path.join(ROOT, ".li-profile"); // gitignored; holds your login

// --- Supabase REST helpers (PostgREST) -------------------------------------
const sb = (p, init = {}) =>
  fetch(`${SUPABASE_URL}/rest/v1/${p}`, {
    ...init,
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });

async function fetchApproved() {
  // contact is jsonb; the outreach object lives at contact.li, approved rows
  // have contact.li.li_stage = 'approved' (PostgREST nested arrow filter).
  const q =
    `jobops_leads?select=id,company,title,contact,stage` +
    `&contact->li->>li_stage=eq.approved&limit=${LIMIT}`;
  const r = await sb(q);
  if (!r.ok) throw new Error(`supabase read ${r.status}: ${await r.text()}`);
  return r.json();
}

async function updateLead(id, contact, extra = {}) {
  const r = await sb(`jobops_leads?id=eq.${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({ contact, updated_at: new Date().toISOString(), ...extra }),
  });
  if (!r.ok) throw new Error(`supabase write ${r.status}: ${await r.text()}`);
}

// --- console prompt ---------------------------------------------------------
const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise((res) => rl.question(q, res));

// --- main -------------------------------------------------------------------
async function run() {
  const leads = await fetchApproved();
  if (!leads.length) {
    console.log("No approved LinkedIn leads. Draft + approve some in the dashboard first.");
    rl.close();
    return;
  }
  console.log(`${leads.length} approved lead(s). DM step: ${DO_DM ? "on" : "off"}. Dry run: ${DRY}.`);

  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false,
    viewport: { width: 1280, height: 900 },
    args: ["--disable-blink-features=AutomationControlled"],
  });
  const page = ctx.pages()[0] || (await ctx.newPage());

  // Ensure logged in (first run: you log in by hand, then press Enter).
  await page.goto("https://www.linkedin.com/feed/", { waitUntil: "domcontentloaded" });
  if (page.url().includes("/login") || page.url().includes("/checkpoint")) {
    await ask("Log into LinkedIn in the open window, then press ENTER here... ");
  }

  for (const lead of leads) {
    const c = lead.contact || {};
    const li = c.li || {};                 // { url, post_url, comment, dm, li_stage }
    const profileUrl = li.url || c.linkedin || "";
    const label = `${lead.company} — ${c.name || "unknown"}`;
    console.log(`\n=== ${label} ===`);

    // 1) COMMENT on their post
    if (li.post_url && li.comment && li.li_stage === "approved") {
      console.log(`Post:    ${li.post_url}`);
      console.log(`Comment: ${li.comment}`);
      await page.goto(li.post_url, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(2500 + Math.random() * 2000); // human pacing

      // LinkedIn's comment box is a contenteditable. Selectors drift — we try a
      // few, and if none match you can paste manually before confirming.
      const box = page.locator(
        '[contenteditable="true"][role="textbox"], .comments-comment-box__form [contenteditable="true"], .ql-editor[contenteditable="true"]'
      ).first();
      try {
        await box.scrollIntoViewIfNeeded({ timeout: 5000 });
        await box.click({ timeout: 5000 });
        await box.type(li.comment, { delay: 25 });
      } catch {
        console.log("(!) Could not find the comment box automatically — paste the comment yourself in the window.");
      }

      const a = (await ask("ENTER = post comment · s = skip · q = quit: ")).trim().toLowerCase();
      if (a === "q") break;
      if (a === "s") { console.log("skipped"); continue; }
      if (!DRY) {
        // Click the Post/Comment submit button.
        const post = page.getByRole("button", { name: /^(post|comment)$/i }).first();
        try { await post.click({ timeout: 5000 }); }
        catch { console.log("(!) Couldn't click Post — click it yourself, then continue."); await ask("ENTER once posted... "); }
        await updateLead(lead.id, { ...c, li: { ...li, li_stage: "commented", commented_at: new Date().toISOString() } }, { stage: "wip", outreached_at: new Date().toISOString() });
        console.log("✓ commented → li_stage=commented");
      } else {
        console.log("(dry) not posted");
      }
      await page.waitForTimeout(3000 + Math.random() * 3000);
    } else {
      console.log("(no approved comment/post_url for this lead — skipping comment)");
    }

    // 2) DM (optional second touch)
    if (DO_DM && profileUrl && li.dm) {
      console.log(`DM:      ${li.dm}`);
      await page.goto(profileUrl, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(2500 + Math.random() * 2000);
      const msgBtn = page.getByRole("button", { name: /message/i }).first();
      try { await msgBtn.click({ timeout: 6000 }); } catch { console.log("(!) No Message button (not connected / DMs off). Skipping DM."); continue; }
      const dmBox = page.locator('.msg-form__contenteditable[contenteditable="true"], [contenteditable="true"][role="textbox"]').first();
      try { await dmBox.click({ timeout: 5000 }); await dmBox.type(li.dm, { delay: 25 }); }
      catch { console.log("(!) Couldn't find the DM box — type it yourself before confirming."); }

      const a = (await ask("ENTER = send DM · s = skip · q = quit: ")).trim().toLowerCase();
      if (a === "q") break;
      if (a === "s") { console.log("skipped DM"); continue; }
      if (!DRY) {
        const send = page.getByRole("button", { name: /^send$/i }).first();
        try { await send.click({ timeout: 5000 }); } catch { console.log("(!) Couldn't click Send — send it yourself."); await ask("ENTER once sent... "); }
        await updateLead(lead.id, { ...c, li: { ...li, li_stage: "dm_sent", dm_sent_at: new Date().toISOString() } }, { stage: "reached_out" });
        console.log("✓ DM sent → li_stage=dm_sent, stage=reached_out");
      } else {
        console.log("(dry) not sent");
      }
      await page.waitForTimeout(3000 + Math.random() * 3000);
    }
  }

  console.log("\nDone. Close the browser window when ready.");
  await ask("ENTER to close... ");
  await ctx.close();
  rl.close();
}

run().catch((e) => { console.error(e); rl.close(); process.exit(1); });
