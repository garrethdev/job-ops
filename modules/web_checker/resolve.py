"""Resolve a real job-posting URL for a lead that has none.

Some boards (Clay, GTME Pulse) give a real company + title but no per-role link,
so the lead is un-actionable. This searches (Firecrawl) for the exact role and
returns the first result that looks like a SPECIFIC posting (an ATS page, a
`/job/` page, or a company careers page) — skipping aggregator indexes, social
posts, and news. Runs only for KEPT leads (see web_checker.run), so it's bounded.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Tuple

from core.config import firecrawl_key

SEARCH_API = "https://api.firecrawl.dev/v1/search"

# A URL that looks like one concrete posting we can apply to.
_POSTING_HINTS = (
    "ashbyhq.com", "greenhouse.io", "lever.co", "workable.com", "recruitee.com",
    "breezy.hr", "teamtailor.com", "smartrecruiters.com", "myworkdayjobs.com",
    "rippling.com", "jobvite.com", "builtin", "/job/", "/jobs/", "/careers/", "/o/",
)
# Indexes / social / news / aggregators — never a single apply page.
_BAD = (
    "reddit.com", "/posts/", "indeed.com/q-", "glassdoor.com", "youtube.com",
    "wikipedia.org", "linkedin.com/posts", "medium.com", "substack.com",
    "/search", "google.com", "bing.com",
)


def _search(query: str, n: int = 6):
    key = firecrawl_key()
    if not key:
        return []
    body = json.dumps({"query": query, "limit": n}).encode("utf-8")
    req = urllib.request.Request(
        SEARCH_API, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        data = d.get("data")
        return data if isinstance(data, list) else ((data or {}).get("web") or [])
    except Exception:
        return []


def pick_posting(results) -> Tuple[str, str]:
    """From search results, return (url, description) of the first real posting."""
    for it in results:
        url = (it.get("url") or "").strip()
        low = url.lower()
        if not url or any(b in low for b in _BAD):
            continue
        if any(h in low for h in _POSTING_HINTS):
            return url, (it.get("description") or "").strip()[:2000]
    return "", ""


def resolve_posting(title: str, company: str) -> Tuple[str, str]:
    """Return (url, short_description) for the role, or ('', '') if not found."""
    if not title or not company:
        return "", ""
    return pick_posting(_search(f'"{title}" {company} job'))
