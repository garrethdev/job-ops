"""Classify + score an opportunity against the two lane profiles.

Two backends behind one interface:

  score_one(record, use_llm=False)

- Heuristic (default, no network, no cost): keyword match against the lane
  profiles. Deterministic — this is what runs in --dry-run and in CI, and it
  lets the whole pipeline (fetch -> score -> dedupe -> store -> digest) run
  end-to-end WITHOUT an API key or any billed call.
- LLM (use_llm=True AND ANTHROPIC_API_KEY set): one Claude call per record for
  lane + fit 1-10 + rationale + red flags. Gated so a billed call never happens
  by accident. If use_llm is requested but no key is present, it falls back to
  the heuristic and records that in the rationale.

Either way the result dict is: {lane, fit_score, fit_rationale, red_flags}.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Dict, List

from core.config import (
    LANES,
    OPENROUTER_MODEL,
    OPENROUTER_URL,
    anthropic_key,
    openrouter_key,
)
from core.profile import load_keywords
from core.vetting import junk_reason

ANTHROPIC_MODEL = "claude-sonnet-5"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# Cache compiled word-boundary patterns so scoring stays cheap across a batch.
_PAT_CACHE: Dict[str, "re.Pattern[str]"] = {}


def _pattern(kw: str) -> "re.Pattern[str]":
    p = _PAT_CACHE.get(kw)
    if p is None:
        # Whole-token match: 'ai' must not match 'email', 'intern' not 'internal'.
        p = re.compile(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", re.IGNORECASE)
        _PAT_CACHE[kw] = p
    return p


def _text_of(record: Dict[str, Any]) -> str:
    parts = [
        record.get("title", ""),
        record.get("company", ""),
        record.get("location", ""),
        record.get("snippet", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def _count_hits(text: str, words: List[str]) -> int:
    return sum(1 for w in words if w and _pattern(w).search(text))


def score_heuristic(record: Dict[str, Any]) -> Dict[str, Any]:
    text = _text_of(record)
    ignore_loc = bool(record.get("ignore_location"))
    per_lane = {}
    for lane in LANES:
        kw = load_keywords(lane)
        match_hits = _count_hits(text, kw["match"])
        boost_hits = _count_hits(text, kw["boost"])
        dealbreakers = [
            w for w in kw["deal_breakers"]
            if w and _pattern(w).search(text)
            and not (ignore_loc and w in _LOCATION_DEALBREAKERS)
        ]
        per_lane[lane] = (match_hits, boost_hits, dealbreakers)

    # Pick the lane with the most match hits; ties resolve to 'architecture'.
    lane = max(LANES, key=lambda l: (per_lane[l][0], per_lane[l][1]))
    match_hits, boost_hits, dealbreakers = per_lane[lane]

    red_flags: List[str] = []
    if match_hits == 0 and boost_hits == 0:
        score = 2
        rationale = "heuristic: no lane keywords matched (likely neither lane)"
    else:
        # Require genuine signal: 1 match => 4 (below default threshold 6),
        # 2 matches => 6 (surfaces). Strong matches saturate toward 10.
        score = min(10, 2 + 2 * match_hits + boost_hits)
        rationale = (
            f"heuristic: {lane} lane, {match_hits} match + {boost_hits} boost "
            f"keyword hits"
        )
    if dealbreakers:
        score = max(1, score - 4)
        red_flags.append("deal-breaker keyword(s): " + ", ".join(dealbreakers))
    return {
        "lane": lane,
        "fit_score": int(score),
        "fit_rationale": rationale,
        "red_flags": red_flags,
    }


# The remote/hybrid gate is the DEFAULT. A source may set ignore_location:true
# (e.g. randstad-ai) so its roles are judged purely on role-fit; the candidate
# vets location themselves for those. Every other source keeps the gate.
_LOCATION_HEADER = "The candidate works REMOTE or HYBRID only.\n"
_LOCATION_RULE = ("- REMOTE or HYBRID only: if the posting is on-site-only or requires "
                  "relocation, cap fit_score at 3 and add a red flag.\n")
# Deal-breaker keywords that are purely about location (skipped when ignore_location).
_LOCATION_DEALBREAKERS = {
    "on-site only", "onsite only", "on-site", "onsite", "in-office", "in office",
    "relocation required", "relocation",
}

_LLM_PROMPT = """You triage a job/contract opportunity for a candidate targeting FOUR role types.
{location_header}- "gtm-engineer": go-to-market / growth / forward-deployed / solutions / sales engineer; automates the revenue engine (CRM, integrations, sales/marketing automation)
- "software-architect": software/solutions architect, staff/principal engineer, system design, distributed systems, cloud/platform architecture
- "ai-consultant": AI / GenAI / LLM consultant, advisor, strategist, or implementation/transformation lead
- "ai-video-editor": AI video editor, generative video, AI-assisted editing / captioning / render pipelines

Respond with ONLY a JSON object:
{{"lane": "gtm-engineer"|"software-architect"|"ai-consultant"|"ai-video-editor", "fit_score": <int 1-10>, "fit_rationale": "<one sentence>", "red_flags": ["..."]}}

Rules:
- Pick the single best-fitting role.
- fit_score: 1-3 = weak/neither, 4-6 = plausible, 7-10 = strong. Be strict.
- DIRECT MATCH ONLY: the candidate wants exactly the four lanes above. A generic or adjacent engineering role (backend/full-stack/data/ML-infra/devops/SRE/research/computer-vision), or a role that only loosely touches AI, must score 1-3 even if technically engineering. A "multiple roles"/listing-index posting or a non-employer company scores 1. Reserve 6+ for a genuine, direct match to a specific named lane.
- JUDGE THE DETAILS below (the real job posting), not just the title. If the details reveal the role is junior / entry-level / internship / unpaid, or is not actually one of the four lanes, cap fit_score at 3. A senior/strong title with a junior or off-lane description scores LOW.
{location_rule}
POSTING:
title: {title}
company: {company}
location: {location}
comp: {comp}
details: {snippet}
"""


def _llm_backend():
    """Choose LLM provider: OpenRouter (DeepSeek) first, then Anthropic, else none."""
    ork = openrouter_key()
    if ork:
        return ("openrouter", ork, OPENROUTER_MODEL)
    ak = anthropic_key()
    if ak:
        return ("anthropic", ak, ANTHROPIC_MODEL)
    return (None, None, None)


def _post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call_llm(prompt: str):
    """Return (text, provider, model). (None, None, None) if no provider configured."""
    provider, key, model = _llm_backend()
    if provider == "openrouter":
        data = _post_json(
            OPENROUTER_URL,
            {
                "Authorization": f"Bearer {key}",
                "content-type": "application/json",
                "HTTP-Referer": "https://github.com/job-ops",
                "X-Title": "job-ops",
            },
            {
                "model": model,
                "temperature": 0,
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        return data["choices"][0]["message"]["content"], provider, model
    if provider == "anthropic":
        data = _post_json(
            ANTHROPIC_URL,
            {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            {"model": model, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]},
        )
        return "".join(b.get("text", "") for b in data.get("content", [])), provider, model
    return None, None, None


def score_llm(record: Dict[str, Any]) -> Dict[str, Any]:
    ignore_loc = bool(record.get("ignore_location"))
    prompt = _LLM_PROMPT.format(
        location_header="" if ignore_loc else _LOCATION_HEADER,
        location_rule="" if ignore_loc else _LOCATION_RULE,
        title=record.get("title", ""),
        company=record.get("company", ""),
        location=record.get("location", ""),
        comp=record.get("comp", ""),
        snippet=(record.get("snippet", "") or "")[:2000],
    )
    # A network error or a non-JSON/empty LLM reply must NEVER crash the run —
    # one bad response would take down the whole batch. Fall back to the heuristic.
    try:
        text, provider, model = _call_llm(prompt)
    except Exception:
        text, model = None, "llm-error"
    if not text:  # no key / empty reply -> deterministic fallback, flagged
        result = score_heuristic(record)
        result["fit_rationale"] = "[no LLM -> heuristic] " + result["fit_rationale"]
        return result
    try:
        parsed = json.loads(text[text.find("{"): text.rfind("}") + 1])
        if not isinstance(parsed, dict):
            raise ValueError("not a JSON object")
    except Exception:
        result = score_heuristic(record)
        result["fit_rationale"] = "[LLM reply unparseable -> heuristic] " + result["fit_rationale"]
        return result
    lane = parsed.get("lane") if parsed.get("lane") in LANES else score_heuristic(record)["lane"]
    try:
        fit = int(parsed.get("fit_score", 0))
    except (TypeError, ValueError):
        fit = 0
    return {
        "lane": lane,
        "fit_score": max(0, min(10, fit)),
        "fit_rationale": (f"[{model}] " + str(parsed.get("fit_rationale", "")))[:400],
        "red_flags": [str(x) for x in (parsed.get("red_flags") or [])][:6],
    }


def score_one(record: Dict[str, Any], use_llm: bool = False) -> Dict[str, Any]:
    return score_llm(record) if use_llm else score_heuristic(record)


def apply_scores(
    records: List[Dict[str, Any]], use_llm: bool = False
) -> List[Dict[str, Any]]:
    """Score any record still unscored (fit_score 0 / lane empty). In place.

    Junk artifacts (see core.vetting) are stamped fit_score=1 without an LLM call,
    so they can never surface regardless of how the model might rate them."""
    for r in records:
        if r.get("fit_score", 0) == 0 or not r.get("lane"):
            reason = junk_reason(r)
            if reason:
                r["fit_score"] = 1
                r["fit_rationale"] = "auto-rejected (vetting): " + reason
                r["red_flags"] = list(r.get("red_flags") or []) + ["scraping artifact: " + reason]
            else:
                r.update(score_one(r, use_llm=use_llm))
    return records
