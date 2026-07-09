"""Hacker News "Who is hiring?" adapter — Algolia HN API (public, no auth).

1. Find the most recent "Ask HN: Who is hiring?" story by user `whoishiring`.
2. Pull its top-level comments (each is one job posting).
3. Convention: the first line is "Company | Role | Location | REMOTE | ...".
   We split on '|' for company/title; the whole comment is the snippet.

Best-effort parsing of freeform text — the keyword pre-filter (sources.yaml)
keeps it to lane-relevant postings so we don't dump the whole thread.
"""
from __future__ import annotations

import html
import json
import re
from typing import Dict, List

from modules.web_checker.adapters.base import http_get, partial, passes_prefilter

SEARCH = ("https://hn.algolia.com/api/v1/search_by_date"
          "?tags=story,author_whoishiring&query=who%20is%20hiring&hitsPerPage=5")
ITEM = "https://hn.algolia.com/api/v1/items/{id}"

_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://[^\s<>\"]+")


def _clean(text_html: str) -> str:
    t = text_html.replace("<p>", "\n").replace("</p>", " ")
    t = _TAG_RE.sub(" ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _latest_thread_id() -> str:
    data = json.loads(http_get(SEARCH).decode("utf-8"))
    for hit in data.get("hits", []):
        title = (hit.get("title") or "").lower()
        if "who is hiring" in title:
            return hit["objectID"]
    return ""


def fetch(entry: Dict) -> List[Dict]:
    limit = int(entry.get("limit", 50))
    keywords = entry.get("keywords") or []
    source = entry.get("source", "board")

    thread_id = _latest_thread_id()
    if not thread_id:
        return []
    tree = json.loads(http_get(ITEM.format(id=thread_id)).decode("utf-8"))

    out: List[Dict] = []
    for child in tree.get("children", []):
        raw = child.get("text") or ""
        if not raw:
            continue
        text = _clean(raw)
        if not passes_prefilter(text, keywords):
            continue
        first_line = text.split("\n", 1)[0]
        parts = [p.strip() for p in re.split(r"\||—|-", first_line) if p.strip()]
        company = parts[0][:80] if parts else (child.get("author") or "")
        title = parts[1][:120] if len(parts) > 1 else first_line[:120]
        url_match = _URL_RE.search(text)
        url = url_match.group(0) if url_match else (
            f"https://news.ycombinator.com/item?id={child.get('id')}"
        )
        out.append(partial(
            title=title or "(HN posting)",
            company=company or "(HN)",
            url=url,
            location="",
            posted=str(child.get("created_at", "")),
            snippet=text[:1500],
            source=source,
            source_detail="hn-whoishiring",
        ))
        if len(out) >= limit:
            break
    return out
