#!/usr/bin/env python3
"""Gemini second-opinion scorer for the lead pipeline (mixture-of-experts QA).

DeepSeek scores every lead in-pipeline; this script cross-checks a random
sample of the freshest board rows with Gemini Pro via OpenRouter. For each
sampled lead it asks Gemini for an independent 0-10 fit score against the
lead's lane profile, then prints pipeline_score vs gemini_score and flags
DISAGREEMENTS (|delta| >= 3). Report-only: nothing is written back and the
exit code is always 0.

  python -m scripts.second_opinion          # human-readable report
  python -m scripts.second_opinion --json   # machine-readable output

BILLED: up to 15 Gemini Pro calls per run (one per sampled lead), plus one
free model-listing GET. QA rule: sample, not census.
"""
from __future__ import annotations

import json
import os
import random
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core.config  # noqa: E402  (loads .env)
from core.config import LANES, OPENROUTER_URL, PROFILES_DIR, openrouter_key  # noqa: E402

TABLE = "jobops_leads"
WINDOW_HOURS = 36
SAMPLE_CAP = 15          # QA rule: sample, not census
DISAGREE_DELTA = 3       # |gemini - pipeline| at/above this = disagreement
RUBRIC_LINES = 40        # first N lines of profiles/<lane>.md = the rubric

# Only the profile-backed lanes get a second opinion; app-owned lanes
# (recruiter / yc_gtm / lookup) have no rubric to score against.
TARGET_LANES = LANES[:4]

MODELS_URL = "https://openrouter.ai/api/v1/models"
# Best-first fallback chain, verified live 2026-08-19. gemini-3-pro-preview is
# known to 404 on OpenRouter (no text variant listed); 3.1 works.
GEMINI_CHAIN = (
    "google/gemini-3.1-pro-preview",
    "google/gemini-2.5-pro",
    "google/gemini-2.5-pro-preview",
)

_PROMPT = """You are a second-opinion QA scorer for a job-lead pipeline. Rate how well this \
lead fits the "{lane}" role below, 0-10 (0 = no fit at all, 10 = perfect direct match). \
Judge the posting details, not just the title. Be strict: reserve 7+ for a genuine, \
direct match to the role profile.

ROLE PROFILE (rubric):
{rubric}

LEAD:
title: {title}
company: {company}
company_does: {company_summary}
company_remote_policy: {company_remote}
location: {location}
comp: {comp}
details: {snippet}

Respond with ONLY a JSON object: {{"score": <int 0-10>, "reason": "<one sentence>"}}"""


def _headers():
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _req(method, path, body=None):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else []


def resolve_model() -> str:
    """Pick the best available Gemini Pro text model from the live listing.

    The /models GET needs no auth. If the listing is unreachable, trust the
    head of the hardcoded chain rather than aborting the QA run.
    """
    try:
        req = urllib.request.Request(MODELS_URL, headers={"User-Agent": "job-ops"})
        with urllib.request.urlopen(req, timeout=30) as r:
            available = {m.get("id") for m in json.loads(r.read().decode()).get("data", [])}
    except Exception:
        return GEMINI_CHAIN[0]
    for model in GEMINI_CHAIN:
        if model in available:
            return model
    return GEMINI_CHAIN[-1]


def load_rubric(lane: str) -> str:
    lines = (PROFILES_DIR / f"{lane}.md").read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[:RUBRIC_LINES]).strip()


def build_prompt(lead: dict, rubric: str) -> str:
    return _PROMPT.format(
        lane=lead.get("lane", ""),
        rubric=rubric,
        title=lead.get("title", ""),
        company=lead.get("company", ""),
        company_summary=lead.get("company_summary", "") or "(unknown)",
        company_remote=lead.get("company_remote", "") or "(unknown)",
        location=lead.get("location", "") or "(unknown)",
        comp=lead.get("comp", "") or "(unknown)",
        snippet=(lead.get("snippet", "") or "")[:2000],
    )


def score_payload(model: str, prompt: str) -> dict:
    # Generous max_tokens: Gemini 3.x Pro is a reasoning model and burns
    # tokens before emitting the tiny JSON answer.
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }


def gemini_score(model: str, lead: dict, rubric: str):
    """Return (score 0-10 or None, one-line reason). Never raises: a single
    bad call must not take down the QA report."""
    payload = score_payload(model, build_prompt(lead, rubric))
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {openrouter_key()}",
            "content-type": "application/json",
            "HTTP-Referer": "https://github.com/job-ops",
            "X-Title": "job-ops",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        parsed = json.loads(text[text.find("{"): text.rfind("}") + 1])
        score = max(0, min(10, int(parsed["score"])))
        return score, str(parsed.get("reason", ""))[:200]
    except Exception as e:
        return None, f"[gemini call failed: {type(e).__name__}]"


def fetch_recent() -> list:
    since = (datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    cols = ("id,title,company,lane,fit_score,snippet,location,comp,"
            "company_summary,company_remote")
    lanes = ",".join(TARGET_LANES)
    return _req(
        "GET",
        f"/rest/v1/{TABLE}?select={cols}&status=eq.new"
        f"&first_seen=gt.{since}&lane=in.({lanes})&limit=1000",
    )


def disagreements(rows: list) -> list:
    """Rows where Gemini and the pipeline differ by DISAGREE_DELTA or more,
    biggest gap first. Failed Gemini calls (score None) never count."""
    out = [r for r in rows
           if r["gemini_score"] is not None and abs(r["delta"]) >= DISAGREE_DELTA]
    return sorted(out, key=lambda r: abs(r["delta"]), reverse=True)


def main() -> int:
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        # BILLED run otherwise -- --help must never trigger live scoring.
        print(__doc__.strip())
        return 0
    json_out = "--json" in sys.argv

    if not openrouter_key():  # env and job-ops/.env (loaded by core.config) missed
        core.config._load_dotenv(Path.home() / ".config" / "peptide-secrets" / ".env")
    if not openrouter_key():
        print("no OPENROUTER_API_KEY (checked env, job-ops/.env, peptide-secrets/.env)")
        return 0

    try:
        leads = fetch_recent()
    except Exception as e:
        print(f"could not fetch leads from Supabase: {type(e).__name__}")
        return 0
    if not leads:
        print(f"no status=new leads in the last {WINDOW_HOURS}h - nothing to QA")
        return 0

    model = resolve_model()
    sample = random.sample(leads, min(SAMPLE_CAP, len(leads)))
    rubrics = {lane: load_rubric(lane) for lane in {r["lane"] for r in sample}}

    rows = []
    for lead in sample:
        score, reason = gemini_score(model, lead, rubrics[lead["lane"]])
        pipeline = lead.get("fit_score") or 0
        rows.append({
            "id": lead["id"],
            "title": lead.get("title", ""),
            "company": lead.get("company", ""),
            "lane": lead["lane"],
            "pipeline_score": pipeline,
            "gemini_score": score,
            "delta": (score - pipeline) if score is not None else None,
            "reason": reason,
        })
    flagged = disagreements(rows)

    if json_out:
        print(json.dumps({
            "model": model,
            "window_hours": WINDOW_HOURS,
            "candidates": len(leads),
            "sampled": len(rows),
            "leads": rows,
            "disagreement_ids": [r["id"] for r in flagged],
        }, indent=2))
        return 0

    print(f"model={model} window={WINDOW_HOURS}h candidates={len(leads)} sampled={len(rows)}\n")
    print(" pipeline  gemini  delta  lead")
    for r in rows:
        g = "-" if r["gemini_score"] is None else r["gemini_score"]
        d = "-" if r["delta"] is None else f"{r['delta']:+d}"
        print(f"{r['pipeline_score']:9d} {g:>7} {d:>6}  "
              f"{r['title']} @ {r['company']} [{r['lane']}]")

    print(f"\nDISAGREEMENTS (|delta| >= {DISAGREE_DELTA}): {len(flagged)}")
    for r in flagged:
        print(f"  - {r['title']} @ {r['company']} [{r['lane']}] "
              f"pipeline={r['pipeline_score']} gemini={r['gemini_score']}: {r['reason']}")
    if not flagged:
        print("  none - Gemini broadly agrees with the pipeline scores")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
