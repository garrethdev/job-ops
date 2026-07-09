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

from core.config import LANES, anthropic_key
from core.profile import load_keywords

ANTHROPIC_MODEL = "claude-sonnet-5"

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
    per_lane = {}
    for lane in LANES:
        kw = load_keywords(lane)
        match_hits = _count_hits(text, kw["match"])
        boost_hits = _count_hits(text, kw["boost"])
        dealbreakers = [w for w in kw["deal_breakers"] if w and _pattern(w).search(text)]
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


_LLM_PROMPT = """You are triaging a job/contract opportunity for a candidate who works in two lanes:
- "architecture": senior/staff software architecture & backend/platform engineering
- "video-ai": AI video editing / generative-media tooling / creative-technology engineering

Given the posting below, respond with ONLY a JSON object:
{{"lane": "architecture" | "video-ai", "fit_score": <int 1-10>, "fit_rationale": "<one sentence>", "red_flags": ["..."]}}
fit_score 1-3 = weak/neither, 4-6 = plausible, 7-10 = strong. Be strict.

POSTING:
title: {title}
company: {company}
location: {location}
comp: {comp}
details: {snippet}
"""


def score_llm(record: Dict[str, Any]) -> Dict[str, Any]:
    key = anthropic_key()
    if not key:
        result = score_heuristic(record)
        result["fit_rationale"] = "[no ANTHROPIC_API_KEY -> heuristic] " + result["fit_rationale"]
        return result
    prompt = _LLM_PROMPT.format(
        title=record.get("title", ""),
        company=record.get("company", ""),
        location=record.get("location", ""),
        comp=record.get("comp", ""),
        snippet=(record.get("snippet", "") or "")[:2000],
    )
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    text = "".join(b.get("text", "") for b in payload.get("content", []))
    parsed = json.loads(text[text.find("{"): text.rfind("}") + 1])
    lane = parsed.get("lane") if parsed.get("lane") in LANES else "architecture"
    return {
        "lane": lane,
        "fit_score": int(parsed.get("fit_score", 0)),
        "fit_rationale": str(parsed.get("fit_rationale", ""))[:400],
        "red_flags": [str(x) for x in parsed.get("red_flags", [])][:6],
    }


def score_one(record: Dict[str, Any], use_llm: bool = False) -> Dict[str, Any]:
    return score_llm(record) if use_llm else score_heuristic(record)


def apply_scores(
    records: List[Dict[str, Any]], use_llm: bool = False
) -> List[Dict[str, Any]]:
    """Score any record still unscored (fit_score 0 / lane empty). In place."""
    for r in records:
        if r.get("fit_score", 0) == 0 or not r.get("lane"):
            r.update(score_one(r, use_llm=use_llm))
    return records
