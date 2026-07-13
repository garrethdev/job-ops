"""Fetch a posting's FULL description from its detail page via Firecrawl.

Listing scrapes only yield card-level data (title/company/location/url). For
sources that set fetch_detail:true, run.py calls this on the roles that survive
scoring, so the stored `snippet` is the whole posting — that's what the dashboard
detail panel shows when you click a lead. Costs one Firecrawl credit per call,
so it runs only for KEPT roles, not every listing.
"""
from __future__ import annotations

import json
import urllib.request

from core.config import firecrawl_key

API = "https://api.firecrawl.dev/v1/scrape"
MAX_CHARS = 6000


def fetch_description(url: str, timeout: int = 90) -> str:
    """Return the detail page's main content as markdown, or '' on any failure."""
    key = firecrawl_key()
    if not key or not url:
        return ""
    body = json.dumps({
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        md = ((data.get("data") or {}).get("markdown") or "").strip()
        return md[:MAX_CHARS]
    except Exception:
        return ""  # detail enrichment is best-effort; never sink the run
