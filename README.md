# job-ops

Scheduled jobs (GitHub Actions cron) that surface **remote or hybrid** opportunities
across four target roles — **GTM Engineer**, **Software Architect**, **AI Consultant**,
**AI Video Editor** (and close variations) — score them, enrich them with
decision-maker contacts, and feed an apply pipeline. State is committed back to the
repo as versioned JSONL; no external infra.

See [`docs/GAMEPLAN.md`](docs/GAMEPLAN.md) for the full design and
[`docs/SETUP.md`](docs/SETUP.md) to get it running.

## Architecture (strict module isolation)

Modules **never import each other**. The only shared contract is the opportunities
store (`store/opportunities.jsonl`, schema-versioned). Each module has its own
workflow, its own config, and only the secrets it needs. Any module can be deleted
by removing its workflow — nothing else breaks. A CI check
(`scripts/check_coupling.py`) fails the build on any cross-module import.

```
core/                 store I/O, schema+dedupe, profile loader, scoring, digest  (the only shared code)
profiles/             gtm-engineer.md, software-architect.md, ai-consultant.md, ai-video-editor.md
modules/
  web_checker/        Module B — API/RSS sources -> score -> dedupe -> store -> digest   [M2 ✅]
  email_scanner/      Module A — Gmail allowlist -> classify/route -> store             [M3 ⛔ Gmail OAuth]
  contact_enricher/   Module C — Apollo enrichment of high-fit records (cron)           [M4 ⛔ Apollo key]
  dashboard/          Lead dashboard — local web UI to work leads + reveal contacts     [✅ live]
  apply_pipeline/     Module D — OUR extraction of ai-job-search /apply (local only)    [M5 ⛔ CV docs]
store/opportunities.jsonl   the one inter-module contract (committed state)
vendor/ai-job-search/       pinned @ reviewed SHA, reference only, NEVER executed by CI
.github/workflows/          one workflow per module, scoped secrets, issue-on-failure
```

## Data flow

`fetch (adapters) → classify into one of 4 roles + fit-score (free heuristic, or an
LLM when a key is set: DeepSeek-V3 via OpenRouter, else Claude) → dedupe/merge
(company+title OR url) → append to store (atomic, schema-validated) → digest of
genuinely-new opportunities → GitHub issue`

Scoring enforces **remote or hybrid only**: on-site-only / relocation-required
postings are capped low and red-flagged.

## Status

- **M1 — skeleton**: ✅ core, profiles, vendored+audited dependency
  ([`docs/VENDOR_AUDIT.md`](docs/VENDOR_AUDIT.md)), CI coupling check.
- **M2 — web-checker**: ✅ RemoteOK + WeWorkRemotely + HN "Who is hiring", proven
  against live sources. Runs with no required secrets (free heuristic scorer;
  Claude scoring optional).
- **M3/M4/M5**: scaffolded, blocked on credentials / CV docs — see
  [`docs/SETUP.md`](docs/SETUP.md).

## Quick start

```bash
pip install -r requirements.txt
python -m modules.web_checker --dry-run     # preview, no store write
pytest tests/ -q                            # tests + isolation guard
```

## Lead dashboard

A local web UI over the store. Each row is one opportunity; per lead you can
**Find LinkedIn** (Apollo reveals name + LinkedIn + email in one 1-credit call),
**Find Email** (shows the cached email, free), add **notes**, or **delete**.

```bash
python -m modules.web_checker --digest-out digest.md   # seed the store with leads
python -m modules.dashboard                            # http://127.0.0.1:8787
```

Needs `APOLLO_API_KEY` in `.env` for the reveal buttons (search is free; only the
match/reveal costs 1 credit, and re-revealing a lead is cached at 0 credits). The
Apollo client lives in `core/apollo.py` so the dashboard and the Module C cron
share it. **Note:** once enriched, `store/opportunities.jsonl` contains real
contact PII — keep the repo private.

## Security posture

`vendor/ai-job-search` is treated as an **untrusted third-party dependency**:
vendored at a pinned SHA with git history stripped (no auto-pulls), audited
prompt-by-prompt before any extraction, and **never executed by CI**. The apply
pipeline (Module D) runs local/interactive only and has no access to Gmail/Apollo/
Firecrawl/Anthropic CI secrets. Full audit + extraction plan in
[`docs/VENDOR_AUDIT.md`](docs/VENDOR_AUDIT.md).
