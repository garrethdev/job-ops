# LinkedIn outreach — setup & test (runs on your machine)

The LinkedIn arm adds a **comment → DM** channel to the job-hunter, tied to the
same `jobops_leads` table. Two halves:

- **Dashboard (Vercel)** — draft a comment + DM per lead from their latest post,
  edit, and **Approve & queue**. Endpoints: `api/linkedin.js`, `lib/linkedin.js`,
  `lib/voice.js`. New **💬 LinkedIn** tab + per-row button in `vercel-app/`.
- **Local runner (`scripts/linkedin_outreach.mjs`)** — opens *your* logged-in
  Chromium and posts the approved comment/DM, pausing for you to confirm each
  action. Nothing is auto-sent; nothing bypasses LinkedIn login.

Data contract: approved rows carry `contact.li = {url, post_url, comment, dm,
li_stage}`. Stages: `pending → approved → commented → dm_sent`. The URL from
Apollo stays in `contact.linkedin`; the runner never overwrites it.

---

## A. One-time: dashboard (Vercel)
Add to the Vercel project env (Settings → Environment Variables):
- `SCRAPECREATORS_API_KEY` — reads the target's latest post (no cookie)
- (already set) `OPENROUTER_API_KEY`, `APOLLO_API_KEY`, Supabase vars

Redeploy. The **💬 LinkedIn** tab and per-row button appear once deployed.

## B. One-time: the machine that runs outreach
Same Claude account, any computer:

```bash
git clone https://github.com/garrethdev/job-ops
cd job-ops/scripts
npm install                        # installs playwright
npx playwright install chromium    # one-time browser download

# create scripts/.env  (gitignored)
cat > .env <<'ENV'
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service-role key>   # Supabase → Settings → API
ENV

npm run preflight                  # verifies env, Supabase, Chromium, queue count
```

`preflight` must be all green before you go further.

## C. Test it safely (no real outreach)
```bash
npm run outreach:dry               # opens the browser, pre-fills, but submits NOTHING
```
First run: the browser opens to LinkedIn — **log in by hand once** (the session is
saved in `scripts/.li-profile/`, gitignored). `--dry` walks the approved queue and
pre-fills each comment without posting.

## D. Go live — batch model
You approve a **2-3 day batch** in the dashboard. The runner then posts the whole
approved queue **automatically** — you confirm ONCE at the start, not per action.
It's human-paced (randomized delay between each) and capped per run.

```bash
npm run outreach                   # posts all approved COMMENTS (one y/N confirm, then auto)
npm run outreach:dm                # sends DMs to already-commented leads (second touch)

# tuning:
node linkedin_outreach.mjs --per-run 8      # cap actions this run (default 5)
node linkedin_outreach.mjs --min 60 --max 150   # delay range, seconds
node linkedin_outreach.mjs --yes            # skip even the one upfront confirm
```
After a comment posts, the lead advances `approved → commented` (`stage` → `wip`).
After a DM, `commented → dm_sent` (`stage` → `reached_out`). The per-run cap means a
big approved batch naturally spreads across days — run once a day.

---

## Daily loop
1. **Once every 2-3 days:** in the dashboard **💬 LinkedIn** tab, draft + edit +
   **Approve** a batch of leads (this is your only per-item review).
2. **Each day:** run `npm run outreach` — it posts that day's slice of approved
   comments automatically (capped, paced), then stops.
3. **A day or two after a comment:** `npm run outreach:dm` for the DM second touch.
4. Keep the daily cap sane (≈5-10). Bulk activity risks the account.

## Notes / safety
- One upfront confirm per run, then automatic. You still control WHAT goes out (you
  approve every comment/DM in the dashboard) and HOW MUCH (the per-run cap). Keep
  volumes low and human — automated bulk commenting/DMing violates LinkedIn's terms.
- LinkedIn selectors drift; if a box isn't found, that lead is left in place (logged)
  so you can retry — it is not marked done.
- `scripts/.env` and `scripts/.li-profile/` are gitignored — never commit them.
