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
_DETAIL_PROMPT = (
    "Extract the full job posting text ONLY: role summary, responsibilities, "
    "requirements/qualifications, compensation, and location/workplace type. "
    "Return clean plain text. EXCLUDE site navigation, menus, headers, footers, "
    "cookie banners, 'similar jobs', and apply buttons."
)
_DETAIL_SCHEMA = {"type": "object", "properties": {"description": {"type": "string"}}}


def fetch_description(url: str, timeout: int = 90) -> str:
    """Return the posting's clean description text, or '' on any failure.

    Uses Firecrawl JSON extraction (not raw markdown) so we get the job body
    without the site's nav/menu chrome."""
    key = firecrawl_key()
    if not key or not url:
        return ""
    body = json.dumps({
        "url": url,
        "formats": ["json"],
        "onlyMainContent": True,
        "jsonOptions": {"prompt": _DETAIL_PROMPT, "schema": _DETAIL_SCHEMA},
    }).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        desc = (((data.get("data") or {}).get("json") or {}).get("description") or "").strip()
        return "" if is_error_page(desc) else desc[:MAX_CHARS]
    except Exception:
        return ""  # detail enrichment is best-effort; never sink the run


# A posting that expired between search and fetch returns a 404/"filled" page —
# never store that as the job description.
_ERROR_MARKERS = (
    "404", "page not found", "page you're looking for", "page you are looking for",
    "can't seem to find", "cannot be found", "this is embarrassing", "no longer available",
    "no longer accepting", "position has been filled", "this job has expired",
    "posting is closed", "not found", "oops",
)


def is_error_page(text: str) -> bool:
    t = (text or "").strip().lower()
    if len(t) < 25:
        return True  # too little to be a real posting
    return any(m in t for m in _ERROR_MARKERS)
