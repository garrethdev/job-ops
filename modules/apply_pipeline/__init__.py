"""Module D — apply pipeline (M5, LOCAL/INTERACTIVE ONLY — never runs in CI).

This is OUR extraction of ai-job-search's /apply drafter-reviewer workflow, NOT
the vendored code. Per the security audit (docs/VENDOR_AUDIT.md) we extract only:
  - LaTeX templates (cv/, cover_letters/ incl. cover.cls + OpenFonts)
  - the profile schema (two lane variants: profiles/architecture.md, video-ai.md)
  - the drafter-reviewer /apply workflow + PDF/ATS verification checklist
  - salary_lookup.py (stdlib-only, safe)

We DO NOT extract (audit verdict DO-NOT-EXTRACT):
  - .claude/agents/gemini-research-expert.md  (calls external Gemini CLI/API)
  - .claude/skills/job-scraper/                (depends on deleted Danish bun CLIs)
  - .claude/commands/add-portal.md             (web-content -> code execution)
  - .claude/commands/reset.md                  (the only rm -rf)
  - the Bash(bun run:*) permission

Isolation: reads opportunities.jsonl + the profiles and NOTHING else. No Gmail /
Apollo / Firecrawl / Anthropic CI secrets. See docs/VENDOR_AUDIT.md for the full
extraction plan and hardening notes. Population happens in M5 with Garreth's real
CV via the extracted /setup.
"""
