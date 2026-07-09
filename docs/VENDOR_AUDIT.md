# Vendor Security Audit — ai-job-search

**Vendored at:** `vendor/ai-job-search/`
**Pinned SHA:** `6e92a4358a51a4572f44617bac152925b516021c` (recorded in `vendor/VENDOR_SHA`)
**Upstream:** https://github.com/MadsLorentzen/ai-job-search (MIT)
**Audit date:** 2026-07-09
**Auditor:** Opus 4.8 (M1, per GAMEPLAN §Module-D)

> Why this exists: ai-job-search's `.claude/` skills and commands are *prompts
> that execute with tool access* (WebFetch, Bash, file writes). Adopting them
> wholesale means running third-party instructions inside our agent — a
> prompt-injection / supply-chain surface. This audit reads every prompt file
> before anything is trusted or extracted. Vendor code is **never executed by CI**
> and the git history was stripped on vendoring (no auto-pulls).

## Headline findings

- **No secret / API-key / env-var reads or exfiltration anywhere** in the audited
  files. Nothing reads `$HOME`, `.env`, credentials, or shells out to print env.
- **No writes outside the repo working directory.** Every write targets
  repo-relative paths (`cv/`, `cover_letters/`, `documents/`, `templates/`, …).
  No `~/`, `/etc`, or absolute-path writes.
- **Three real concerns**, none in our extraction set: `reset.md` (`rm -rf`),
  `add-portal.md` (`curl` + `bun install` + executes code generated from fetched
  web content), and `gemini-research-expert.md` (shells to an external `gemini`
  CLI / Google API).
- The Python tools (`salary_lookup.py`, `security_guards.py`, `lint_skills.py`)
  are stdlib-only, read-only, no network — clean.
- The `.agents/skills/` Danish TypeScript CLIs are **deleted, not audited**
  (unneeded attack/maintenance surface; the portal layer is designed to be swapped).

## Per-file risk table

| File | Risk | Concerning behavior (file:line) | Verdict |
|------|------|----------------------------------|---------|
| `.claude/settings.json` | LOW | Pre-approves `Bash(bun run:*)` (:5) — broad auto-run. | EXTRACT-WITH-CHANGES (drop `bun run`) |
| `commands/apply.md` | LOW-MED | `WebFetch` posting URL then drafts from it (:17); reviewer `WebSearch/WebFetch` (:98,168); `salary_lookup.py` (:33); `lualatex/xelatex` (:185-186); `pdftotext` (:230). Writes only `cv/`, `cover_letters/`; deletes only self-generated build artifacts (:255,259). | SAFE-TO-EXTRACT |
| `commands/add-template.md` | LOW | Compiles user LaTeX (:110-112); writes `templates/…`; deletes scratch artifacts (:115). Repo-local. | SAFE-TO-EXTRACT |
| `commands/expand.md` | MED | `WebFetch/WebSearch` GitHub + "any other URLs in profile" (:52-66) then writes into profile files. User-confirmed append (:163). | EXTRACT-WITH-CHANGES (optional; not core) |
| `commands/interview.md` | LOW | `WebFetch` tracker/interviewer URLs (:28,44). Writes `documents/applications/…`. No shell. | SAFE (not in core set) |
| `commands/outcome.md` | LOW | `WebFetch` posting URL (:62). Writes tracker + applications. No shell. | SAFE (not in core set) |
| `commands/rank.md` | LOW | Agents `WebFetch` posting URLs (:41). Writes `job_scraper/seen_jobs.json`. | SAFE (not in core set) |
| `commands/reset.md` | **MED** | Only `rm -rf` in repo: `rm -rf documents/applications/*/` (:196) plus `rm -f documents/{cv,linkedin,diplomas,references}/*` (:192-195). Gated by typed `RESET` (:98-109), repo-scoped. | **DO-NOT-EXTRACT** |
| `commands/setup.md` | LOW | Reads `documents/`, writes profile `.md` + `CLAUDE.md` + `search-queries.md`. No untrusted fetch, no shell. | SAFE (not in core set) |
| `skills/job-application-assistant/SKILL.md` + `01`–`07` | NONE–LOW | Orchestration + profile schema + LaTeX/interview prose. `WebFetch` posting = same injection surface as apply.md. `01`–`07` clean. | SAFE-TO-EXTRACT |
| `skills/job-scraper/SKILL.md` | MED | Runs `bun --version` (:48) and `bun run .agents/skills/*/cli/src/cli.ts` (:6,53-68) — executes the Danish CLIs we are deleting. | **DO-NOT-EXTRACT** (dangling dep) |
| `skills/job-scraper/search-queries.md` | NONE | Placeholder `site:` queries. | SAFE but not needed |
| `skills/upskill/SKILL.md` | LOW | `WebFetch/WebSearch` (:44,112); writes `upskill/`. No shell. | SAFE (not in core set) |
| `agents/gemini-research-expert.md` | **HIGH** | Shells to external `gemini -p "…"` CLI (:13,26) → Google Gemini API; sends prompts off-box; needs a Gemini credential. Not part of `/apply` (that uses a `general-purpose` reviewer). | **DO-NOT-EXTRACT — delete** |
| `salary_lookup.py` | NONE | Stdlib only; reads local `salary_data.json`; no net/shell/secrets/writes. | SAFE-TO-EXTRACT |
| `tools/security_guards.py` | NONE | Stdlib; read-only allowlist/gitignore/manifest checks. Useful guard. | SAFE-TO-EXTRACT (keep) |
| `tools/lint_skills.py` | NONE | Stdlib + PyYAML; read-only lint. | SAFE-TO-EXTRACT |

## Consolidated destructive / shell / network operations

**Destructive (file deletion):**
- `reset.md:192-195` — `rm -f documents/{cv,linkedin,diplomas,references}/*`
- `reset.md:196` — `rm -rf documents/applications/*/` (only `rm -rf`; repo-scoped, typed-`RESET` gate)
- `apply.md:255,259`, `add-template.md:115` — delete self-generated LaTeX build artifacts (benign)

**Shell beyond LaTeX/pdftotext:**
- `agents/gemini-research-expert.md:13,26` — `gemini -p` external LLM CLI (network)
- `skills/job-scraper/SKILL.md:48,53-68` — `bun --version`, `bun run …cli.ts` (deleted CLIs)
- `commands/add-portal.md:99-112` — `bun install` + `bun run src/cli.ts` (package install + runs freshly generated code)
- `settings.json:5` — pre-approves `Bash(bun run:*)`

**Allowed LaTeX toolchain (expected, safe):** `lualatex`, `xelatex`, `pdftotext`, `python[3] salary_lookup.py`.

**Network (WebFetch/WebSearch) — prompt-injection surfaces (fetch remote content, then act on it):**
- `apply.md:17,98,168`, `expand.md:52-66`, `add-portal.md:34-44` (highest-risk: web content → generated CLI → executed), plus posting fetches in `job-scraper`, `upskill`, `interview`, `outcome`, `rank`.
- Only one `curl` reference: `add-portal.md:34` ("WebFetch (or `curl`)"). No `wget`, `eval`, `os.system`, `subprocess`, or auto `git pull`.

## Extraction plan for `modules/apply_pipeline/` (M5)

**Extract (the clean core):**
- `commands/apply.md`, `commands/add-template.md`
- `skills/job-application-assistant/SKILL.md` + `01`–`07`
- `salary_lookup.py`; LaTeX assets `cv/`, `cover_letters/` (incl. `cover.cls` + `OpenFonts/`), `templates/`
- Optionally keep `tools/security_guards.py`, `tools/lint_skills.py` as local guards.

**Do NOT extract / delete:**
1. `agents/gemini-research-expert.md` — external Gemini API/CLI, off-box.
2. `skills/job-scraper/` — depends on deleted `bun` CLIs.
3. `commands/add-portal.md` — web-content-to-code-execution.
4. `commands/reset.md` — the only `rm -rf`. If a reset is wanted, reimplement it
   scoped to our own module output dirs, keep the typed-`RESET` gate, prefer
   trash over `rm -rf` globs.

**Permissions for a future `modules/apply_pipeline/.claude/settings.json`:**
- Remove `Bash(bun run:*)`.
- Keep only `Skill(job-application-assistant)`, `Bash(python[3] salary_lookup.py:*)`, `Bash(pdftotext:*)`.
- Optionally add `Bash(lualatex:*)`, `Bash(xelatex:*)` (else they prompt each run — a safe default).
- If you trim `settings.json`, also update `ALLOWED_PERMISSIONS` in
  `tools/security_guards.py:35-41` in the same change or the guard flags it.

**Injection-surface gating for the retained `/apply` flow (local/interactive):**
- The fetched posting (`apply.md:17`) and reviewer research (`:98,168`) are
  untrusted web content that then drive file writes. Keep apply.md's existing
  "verify every company claim," "never fabricate," and honesty rules. Scope the
  pipeline's write permission to `cv/**` and `cover_letters/**` so a crafted
  posting cannot induce writes elsewhere.

**Bottom line:** the `/apply` drafter-reviewer workflow, LaTeX templates, profile
schema, salary tool, and verification checklist are safe to extract once the four
files above are excluded and the `bun run` permission is dropped. No secret
exfiltration, no out-of-repo writes, no auto-pulling of remote code remain.
