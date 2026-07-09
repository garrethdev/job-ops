# Job-Ops Repo — Gameplan & Handoff for Opus 4.8

**Owner:** Garreth (garreth@cryptomiami.net)
**Date:** 2026-07-06
**Purpose:** A single repo of scheduled jobs that surfaces opportunities across two lanes — **software architecture** and **video AI editing** — enriches them with decision-maker contacts, and feeds the [ai-job-search](https://github.com/MadsLorentzen/ai-job-search) application pipeline.

---

## 1. Decisions already made

| Question | Decision |
|---|---|
| Runtime | **GitHub Actions cron** — jobs live in the repo, run headless |
| Email scope | **Specific senders/labels** in garreth@cryptomiami.net (list TBD — see §6) |
| Web sources | **Job boards + freelance/contract marketplaces** |
| Contact enrichment | Apollo (already connected as MCP; use Apollo REST API from Actions) |
| ai-job-search integration target | **No existing repo.** `job-ops` is our own repo. ai-job-search is treated as an **untrusted third-party dependency**: vendored under `vendor/`, pinned to a reviewed commit, isolated behind an adapter — never the repo base |
| Modularity | **Strict.** Each module is a standalone package with its own workflow, config, and secrets scope. The only shared contract is the opportunities store schema. Any module can be deleted without touching the others |

## 2. Architecture

```
                 ┌─────────────────────────────────────────┐
                 │           job-ops repo (Actions)         │
                 │                                          │
  Gmail ────────▶│  Module A: email-scanner   (cron daily)  │
                 │            │                             │
  Boards/────────▶  Module B: web-checker     (cron daily)  │
  Marketplaces   │            │                             │
                 │            ▼                             │
                 │   opportunities store (JSONL + dedupe)   │
                 │            │                             │
                 │  Module C: contact-enricher (cron/on-new)│
                 │            │                             │
                 └────────────┼─────────────────────────────┘
                              ▼
                 Module D: ai-job-search integration
                 (existing repo — /apply pipeline consumes
                  enriched opportunities)
                              │
                              ▼
                 Daily digest → email/GitHub issue
```

**Isolation rules (non-negotiable):**
- Modules never import each other. Communication is only through `store/opportunities.jsonl` (versioned schema, `schema_version` field on every record).
- Each module has its own GitHub Actions workflow, its own config file, and only the secrets it needs (email-scanner gets Gmail creds, enricher gets the Apollo key — never the union).
- Each module is independently runnable (`python -m modules.email_scanner --dry-run`) and independently disable-able (delete its workflow file, nothing else breaks).
- A failure in one module cannot corrupt the store: writes are append + atomic rewrite, validated against the schema before commit.

**Shared core (`/core`):**
- `profile/` — two lane profiles (architecture + video AI editing): skills, deal-breakers, comp floor, remote/location constraints. Mirrors ai-job-search's `CLAUDE.md` profile schema so Module D can reuse it directly.
- `store/opportunities.jsonl` — one record per opportunity. Dedupe key: normalized `company + title` and URL. Modeled on ai-job-search's `seen_jobs.json` pattern (already proven in that repo).
- `scoring/` — one Claude API call per new opportunity: lane classification (architecture / video-ai / neither), fit score 1–10, rationale, red flags.
- State is committed back to the repo by the Action (simple, versioned, no infra). Upgrade path to Supabase only if volume demands it.

**Record schema:**
```json
{
  "id": "sha1(company+title)",
  "lane": "architecture | video-ai",
  "source": "email | board | marketplace",
  "title": "", "company": "", "url": "", "location": "",
  "comp": "", "posted": "", "first_seen": "",
  "fit_score": 0, "fit_rationale": "",
  "contact": {"name": "", "title": "", "email": "", "linkedin": ""},
  "status": "new | enriched | queued_for_apply | applied | rejected"
}
```

## 3. Modules

### Module A — email-scanner (cron: daily, e.g. 7am ET)
1. Gmail API (OAuth refresh token stored as Actions secret) pulls messages from the configured **sender/label allowlist** since last run.
2. Claude API classifies each: opportunity or not → lane → fit score against the lane profile.
3. Writes new records to the store; skips dupes.
4. Failure mode to handle: token expiry → job should fail loudly (GitHub issue), not silently.

### Module B — web-checker (cron: daily, offset from A)
1. Config file `sources.yaml`: one entry per board/marketplace with search queries per lane.
2. **Fetch strategy matters more than code:** LinkedIn, Upwork, and most major boards block naive scraping and prohibit it in ToS. Prioritize, in order: official APIs/RSS (RemoteOK, WeWorkRemotely, Hacker News Who's Hiring), Firecrawl API (Garreth has an account) for JS-rendered pages, then per-site adapters only where allowed.
3. Same classify → score → dedupe → store flow as Module A.
4. Borrow directly from ai-job-search's `job-scraper` skill: its search-query config, seen-jobs dedupe, and "pre-filter on snippets before fetching" rules are the template. The Danish portal CLIs (`.agents/skills/*`) get replaced with our `sources.yaml` adapters — the repo's README explicitly says the portal layer is designed to be swapped.

### Module C — contact-enricher (cron or triggered on new high-fit records)
1. For each record with `fit_score >= threshold` and no contact: Apollo `organizations/enrich` → `people/match` filtered to titles: CTO, VP Engineering, Head of AI/ML, Lead/Principal Engineer, (for video-ai lane) Head of Post-Production/Creative Technology.
2. Store name, title, verified email, LinkedIn URL. Track Apollo credit spend per run; cap per-run lookups.
3. Compliance note: enrichment for personalized outreach is normal practice, but keep it to business contact info and one-to-one outreach — no bulk cold blasts from the job runner.

### Module D — ai-job-search as a quarantined dependency (one-time project, not a cron job)
What ai-job-search is: a Claude Code framework — `/setup` (profile), `/scrape` (portal search), `/apply` (drafter-reviewer CV/cover-letter pipeline with mandatory LaTeX→PDF verification). TypeScript/Python/TeX. MIT licensed.

**Why quarantine:** its `.claude/` skills and commands are *prompts that execute with tool access* (WebFetch, Bash, file writes). Adopting them wholesale means running third-party instructions inside your agent — a prompt-injection/supply-chain surface. Treat it like an unaudited npm package, not a foundation.

Integration approach:
1. **Vendor, don't fork-as-base:** copy the repo into `vendor/ai-job-search/` pinned to a specific reviewed commit (record the SHA). No git remote auto-pulls; upstream updates are re-reviewed diffs, applied deliberately.
2. **Audit before first run:** Opus reads every file in `.claude/commands/` and `.claude/skills/` and flags anything that fetches remote content into prompts, writes outside the repo, or runs shell beyond LaTeX compilation. Delete the Danish CLIs (`.agents/skills/`) — unneeded attack/maintenance surface.
3. **Take the assets, not the authority:** what we actually want is the LaTeX templates (`cv/`, `cover_letters/` + `cover.cls`/OpenFonts), the profile schema, the drafter-reviewer `/apply` workflow, and the PDF verification checklist. Extract these into our own `modules/apply_pipeline/` with our own slimmed command files; `vendor/` remains reference material.
4. **No secrets exposure:** the apply pipeline runs locally/interactively, never in the scheduled Actions, and has no access to Gmail/Apollo/Firecrawl secrets. It reads `opportunities.jsonl` and the profile — nothing else.
5. Run `/setup` against Garreth's real documents to populate the profile; maintain **two profile variants** (architecture lane, video-ai lane) — the framework assumes one profile.
6. Rewire `/scrape` → read high-fit records from the store; `/apply <id>` pulls the stored posting + enriched contact (cover letter addressed to a real person, not "Dear Hiring Manager").
7. Toolchain for local `/apply` runs: Python 3.10+, LaTeX with `lualatex` + `xelatex` (Bun only needed for the Danish CLIs we're deleting).

### Digest
End of each A/B run: if new records exist, send a digest (new opportunities by lane, sorted by fit, contacts where enriched) via email or a GitHub issue. One notification channel, not three.

## 4. Repo layout

Our own repo; ai-job-search lives only in `vendor/`:

```
job-ops/
├── .github/workflows/            # one workflow per module, scoped secrets
│   ├── email-scan.yml            # cron daily   (secrets: Gmail, Anthropic)
│   ├── web-check.yml             # cron daily   (secrets: Firecrawl, Anthropic)
│   └── enrich.yml                # cron/on-new  (secrets: Apollo)
├── core/                         # store I/O, schema, dedupe, profile loader
├── profiles/
│   ├── architecture.md
│   └── video-ai.md
├── modules/                      # standalone packages — no cross-imports
│   ├── email_scanner/
│   ├── web_checker/              # + sources.yaml
│   ├── contact_enricher/
│   └── apply_pipeline/           # OUR extraction of /apply (local-only, no CI secrets)
├── store/opportunities.jsonl     # the only inter-module contract
└── vendor/ai-job-search/         # pinned @ reviewed SHA, reference only, never executed by CI
```
Language: Python 3.11+ throughout (matches ai-job-search's Python side; Bun only needed inside the ai-job-search repo itself).

## 5. Build order

1. **M1 — Skeleton:** create `job-ops` from scratch: core (store/schema/dedupe), profile configs, one Action that runs and commits state. Vendor ai-job-search at a pinned SHA and complete the §Module-D audit. Prove the cron→commit loop works.
2. **M2 — Module B** (web-checker) with 2–3 easy sources (RSS/API ones first). Digest included. *Do B before A — no OAuth setup required, faster to first value.*
3. **M3 — Module A** (email-scanner) once Gmail OAuth for CI is sorted and the sender list exists.
4. **M4 — Module C** (Apollo enrichment) on high-fit records.
5. **M5 — Module D** (extract apply pipeline from vendor into `modules/apply_pipeline/`, profile setup, two-lane adaptation, wire to the store) — can run in parallel after M1; only depends on the store schema being stable.

## 6. Validation checklist — resolve before/at build start

**Blocking (Opus can't proceed without):**
- [x] **Gmail sender/label allowlist** — DONE, drafted from a live inbox scan: see `email-allowlist.yaml`. Key findings: 5 scan-worthy senders (LinkedIn ×2, Wellfound, Indeed, Glassdoor), 6 same-domain noise senders to exclude, existing `Claude-Jobs` label repurposed for routing direct recruiter outreach, and application-status emails must update records rather than create them. Marketplace email volume is ~zero — that coverage falls to Module B or enabling platform alerts.
- [ ] **Gmail auth for headless CI** — confirm a GCP OAuth client + refresh token can be provisioned. Inbox scan shows job alerts land in the **gmail.com account** (garreth.dottin@gmail.com / garrethdottin@gmail.com), not cryptomiami.net — authorize that account. Cowork's Gmail MCP does not exist inside GitHub Actions; the repo needs its own credentials.
- [ ] **Anthropic API key** as an Actions secret (scoring/classification calls).

**High priority:**
- [ ] **Named list of boards/marketplaces** per lane, and per-site check: API? RSS? Firecrawl-fetchable? ToS-prohibited? (LinkedIn and Upwork almost certainly need alternatives: email alerts routed to Module A, or official APIs.)
- [ ] **Apollo plan/credits** — verify API access tier and per-month enrichment credit budget; set the per-run cap accordingly.
- [ ] **Firecrawl API key** available as an Actions secret.
- [ ] **Two lane profiles drafted** — Opus needs Garreth's actual CV/background docs to run ai-job-search `/setup` properly.

**Confirm during build:**
- [ ] GitHub Actions cron caveat: schedules on free runners can be delayed/skipped on inactive repos — the state-commit pattern keeps the repo active, but verify.
- [ ] LaTeX in the ai-job-search repo compiles for Garreth's CV (lualatex/xelatex, 2-page CV rule).
- [ ] Digest channel choice (email vs GitHub issue) and threshold for inclusion.
- [ ] Dedupe correctness across sources (same job via email alert *and* board scrape must merge, not duplicate).
- [ ] Apollo/Firecrawl/Anthropic rate limits vs daily run volume.

## 7. Risks

- **Third-party framework risk (the big one)** — ai-job-search's skills/commands are executable prompts with tool access; upstream is one maintainer with commit rights. Mitigations already in the plan: pin SHA, audit every prompt file before use, extract assets into our own modules, never execute vendor code in CI, no secrets in the apply pipeline.
- **Coupling creep** — the whole design collapses if modules start importing each other or sharing config. Enforce: store-schema-only contract, per-module secrets, per-module workflows. Add a CI check that fails on cross-module imports.
- **Scraping fragility/ToS** — biggest ongoing cost. Mitigate by preferring email alerts (Module A) and APIs over scraping; treat per-site adapters as disposable.
- **Silent failures in cron jobs** — every workflow must open a GitHub issue on failure; a job that dies quietly for two weeks defeats the purpose.
- **One profile vs two lanes** — the framework assumes a single candidate profile; the two-variant adaptation needs care to avoid cross-contaminating CVs.
- **Fabrication guard** — keep the verification checklist intact; all CV/cover-letter claims verified against the real profile.
