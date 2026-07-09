"""Lane-profile loader.

Two lanes: architecture, video-ai. Each is a markdown profile in profiles/.
Kept deliberately simple (markdown + a small front-matter-free keyword block)
so it mirrors ai-job-search's CLAUDE.md profile idea and Module D can reuse it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from core.config import LANES, PROFILES_DIR


def load_profile_text(lane: str, profiles_dir: Path = PROFILES_DIR) -> str:
    if lane not in LANES:
        raise ValueError(f"unknown lane: {lane!r}")
    p = profiles_dir / f"{lane}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _keywords_under(heading: str, text: str) -> List[str]:
    """Pull comma/newline-separated keywords listed under a `## heading`."""
    m = re.search(rf"(?im)^##\s*{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.S)
    if not m:
        return []
    body = m.group(1)
    items: List[str] = []
    for line in body.splitlines():
        line = line.strip().lstrip("-* ").strip()
        if line:
            items.extend([x.strip().lower() for x in re.split(r",|/", line) if x.strip()])
    return items


def load_keywords(lane: str, profiles_dir: Path = PROFILES_DIR) -> Dict[str, List[str]]:
    """Return {match, boost, deal_breakers} keyword lists for heuristic scoring."""
    text = load_profile_text(lane, profiles_dir)
    return {
        "match": _keywords_under("Match keywords", text),
        "boost": _keywords_under("Boost keywords", text),
        "deal_breakers": _keywords_under("Deal-breakers", text),
    }
