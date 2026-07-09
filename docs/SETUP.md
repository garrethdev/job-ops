# Setup — secrets, GitHub, and what unblocks each module

## 0. Push this repo to GitHub

This repo was built locally. To finish the M1/M2 "definition of done" (crons green
on two consecutive scheduled runs) it needs a GitHub remote:

```bash
cd job-ops
gh repo create job-ops --private --source=. --remote=origin --push
# or: git remote add origin git@github.com:<you>/job-ops.git && git push -u origin main
```

Actions run on the default branch. After the first push, the `ci` workflow runs on
push/PR and `web-check` becomes schedulable.

## 1. Actions secrets

Add under **Settings → Secrets and variables → Actions**. Only the module that
needs a secret can see it (per-workflow scoping is enforced by which `secrets.*`
each workflow references).

| Secret | Used by | Required? | Notes |
|--------|---------|-----------|-------|
| `ANTHROPIC_API_KEY` | web-check, email-scan | Optional (recommended) | Enables LLM classification. **Without it, web-check still runs** on the free deterministic heuristic scorer. Billed when set + `--llm`. |
| `FIRECRAWL_API_KEY` | web-check | Optional | Only for JS-rendered sources (none configured yet). |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN` | email-scan (M3) | **Blocks M3** | OAuth for the **gmail.com** account (garreth.dottin@gmail.com / garrethdottin@gmail.com), **NOT** cryptomiami.net — that's where the job alerts land. See §3. |
| `APOLLO_API_KEY` | enrich (M4) | **Blocks M4** | Verify plan/credit tier; per-run cap is `JOBOPS_APOLLO_MAX_LOOKUPS` (default 25). |

## 2. Turn on the crons

- **web-check** (M2) is already scheduled (`cron: "0 11 * * *"`). It runs headless
  with no required secrets. Nothing to do beyond pushing.
- **email-scan** (M3) and **enrich** (M4) have their `schedule:` blocks **commented
  out** so they don't run and fail before credentials exist. Uncomment the schedule
  in each workflow once the secrets above are set.

## 3. Gmail OAuth for headless CI (unblocks M3)

Cowork's Gmail MCP does not exist inside GitHub Actions — the repo needs its own
credentials. Provision a Google Cloud OAuth **Desktop** client for the gmail.com
account, grant `gmail.readonly`, and mint a refresh token once locally; store the
three values as the `GMAIL_*` secrets. The scanner reads
`modules/email_scanner/allowlist.yaml` (already in the repo) for senders, labels,
and the `jobs-noreply@linkedin.com` status-update routing rule.

## 4. What's blocked vs. ready

| Milestone | Status |
|-----------|--------|
| M1 skeleton (core, profiles, vendor+audit, CI coupling check) | ✅ done |
| M2 web-checker (RemoteOK, WeWorkRemotely, HN Who's Hiring) | ✅ done, proven against live sources |
| M3 email-scanner | ⛔ blocked on `GMAIL_*` secrets |
| M4 contact-enricher | ⛔ blocked on `APOLLO_API_KEY` |
| M5 apply pipeline | ⛔ needs Garreth's CV/background docs; extraction plan in `docs/VENDOR_AUDIT.md` |

## 5. Local usage

```bash
pip install -r requirements.txt

# Fetch + score + preview digest, WITHOUT writing the store:
python -m modules.web_checker --dry-run

# Real run (writes store/opportunities.jsonl, dedupes):
python -m modules.web_checker --digest-out digest.md

# Use Claude for classification instead of the heuristic (needs ANTHROPIC_API_KEY; billed):
ANTHROPIC_API_KEY=sk-... python -m modules.web_checker --llm --dry-run

# Tests + isolation guard:
pytest tests/ -q
python scripts/check_coupling.py
```

Tune the fit threshold with `JOBOPS_FIT_THRESHOLD` (default 6).
