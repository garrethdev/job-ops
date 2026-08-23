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
npm run outreach:dry               # opens the browser, pre-fills, but never submits
```
First run: the browser opens to LinkedIn — **log in by hand once** (the session is
saved in `scripts/.li-profile/`, gitignored). `--dry` walks each approved lead,
pre-fills the comment, and shows the confirm prompt without posting.

## D. Go live
```bash
npm run outreach                   # comments only; ENTER to post each, s=skip, q=quit
npm run outreach:dm                # also send the DM (second touch)
# node linkedin_outreach.mjs --limit 3   # cap per run
```
Every action pauses for your confirmation. After posting, the lead's
`li_stage` advances and `stage` moves `wip` → `reached_out`.

---

## Daily loop
1. In the dashboard **💬 LinkedIn** tab, draft + edit + **Approve** a few leads.
2. On your machine: `npm run outreach` (comments), and a day or two later
   `npm run outreach:dm`.
3. Keep it human-paced — a handful a day, not a batch of 50.

## Notes / safety
- Manual-assist by design: you are logged in and confirm each action. Keep volumes
  low and human. Automated bulk commenting/DMing violates LinkedIn's terms.
- LinkedIn selectors drift; if the comment/DM box isn't found, paste it yourself in
  the open window, then confirm. The script tells you when to.
- `scripts/.env` and `scripts/.li-profile/` are gitignored — never commit them.
