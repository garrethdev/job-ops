"""Firecrawl adapter — structured job extraction from JS-rendered boards.

For boards that block plain fetch (JS-rendered), Firecrawl's scrape+extract pulls
a structured array of {title, company, location, url} in one synchronous call.
Configured per-board in sources.yaml (url/urls + optional prompt). Costs Firecrawl
credits per scrape. Reads FIRECRAWL_API_KEY from the environment.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Dict, List

from core.config import firecrawl_key
from modules.web_checker.adapters.base import partial, passes_prefilter

API = "https://api.firecrawl.dev/v1/scrape"

_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "url": {"type": "string"},
                },
            },
        }
    },
}
_DEFAULT_PROMPT = (
    "Extract every job listing on this page: the job title, the hiring company "
    "name, the location, and the absolute URL to the posting."
)


def _root(url: str) -> str:
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _scrape_extract(url: str, prompt: str, timeout: int = 120) -> List[Dict]:
    key = firecrawl_key()
    if not key:
        raise RuntimeError("FIRECRAWL_API_KEY not set")
    body = json.dumps({
        "url": url,
        "formats": ["json"],
        "onlyMainContent": True,
        "jsonOptions": {"prompt": prompt, "schema": _SCHEMA},
    }).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return ((data.get("data") or {}).get("json") or {}).get("jobs", []) or []


def fetch(entry: Dict) -> List[Dict]:
    limit = int(entry.get("limit", 25))
    keywords = entry.get("keywords") or []
    source = entry.get("source", "board")
    prompt = entry.get("prompt", _DEFAULT_PROMPT)
    urls = entry.get("urls") or ([entry["url"]] if entry.get("url") else [])

    out: List[Dict] = []
    for url in urls:
        try:
            jobs = _scrape_extract(url, prompt)
        except Exception:
            continue  # one board failing must not sink the run
        for j in jobs:
            title = (j.get("title") or "").strip()
            company = (j.get("company") or "").strip()
            if not title or not company or company.lower() in ("not specified", "n/a", "unknown"):
                continue  # schema requires a real company; skip company-less rows
            location = (j.get("location") or "").strip()
            if not passes_prefilter(" ".join([title, company, location]), keywords):
                continue
            link = (j.get("url") or "").strip() or url
            if link.startswith("/"):
                link = _root(url) + link
            out.append(partial(
                title=title, company=company, url=link, location=location,
                source=source, source_detail=entry.get("name", "firecrawl"),
            ))
            if len(out) >= limit:
                return out
    return out
