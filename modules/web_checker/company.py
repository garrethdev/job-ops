"""Firecrawl company research: what a company does + how remote it is.

For each new company we resolve its own website and extract a small structured
profile (summary, remote policy, HQ, industry, and whether it is a staffing
agency). That profile does two jobs:

  1. Gates the lead  - an on-site-only company or a staffing/recruiting body-shop
     is rejected outright (the candidate wants remote/hybrid at the real employer).
  2. Feeds scoring + the dashboard  - the summary/remote policy inform the fit
     score and show in the role's detail popup so each lead is actionable.

Results are cached per normalized company name in store/companies.jsonl, so a
company is researched once no matter how many of its roles show up. Every call is
best-effort: any failure returns an empty profile and never sinks the run.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Dict

from core.config import ROOT, firecrawl_key
from core.schema import normalize_company, now_iso

SEARCH_API = "https://api.firecrawl.dev/v1/search"
SCRAPE_API = "https://api.firecrawl.dev/v1/scrape"
CACHE_PATH = ROOT / "store" / "companies.jsonl"

# Hosts that are NOT a company's own site (so a search hit here isn't the site).
_NOT_COMPANY_SITE = (
    "linkedin.com", "indeed.", "glassdoor.", "ziprecruiter.", "wellfound.",
    "crunchbase.", "wikipedia.", "youtube.", "facebook.", "twitter.", "x.com",
    "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "myworkdayjobs.com",
    "builtin", "google.com", "bing.com", "reddit.com", "medium.com", "github.com",
)

_FIELDS = ("company_summary", "company_remote", "company_hq")

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "remote_policy": {"type": "string", "enum": ["remote", "hybrid", "onsite", "unknown"]},
        "hq": {"type": "string"},
        "industry": {"type": "string"},
        "is_staffing_agency": {"type": "boolean"},
    },
}
_PROMPT = (
    "From this company's OWN website, extract a profile. summary: one sentence on "
    "what the company does (its product/service). remote_policy: how they let "
    "employees work - 'remote', 'hybrid', 'onsite', or 'unknown' if unstated. hq: "
    "headquarters city and country. industry: primary industry. is_staffing_agency: "
    "true ONLY if this company staffs/recruits/places people at OTHER companies "
    "(a staffing firm, recruiter, or IT body-shop) rather than hiring for itself."
)


def _post(url: str, body: Dict[str, Any], timeout: int = 90) -> Dict[str, Any]:
    key = firecrawl_key()
    if not key:
        return {}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _root(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    u = u.split("#", 1)[0]
    if "://" not in u:
        u = "https://" + u
    scheme, rest = u.split("://", 1)
    host = rest.split("/", 1)[0]
    return f"{scheme}://{host}"


def _company_site(name: str, hint_url: str) -> str:
    """Best guess at the company's own homepage URL, '' if none."""
    hint = _root(hint_url)
    if hint and not any(b in hint for b in _NOT_COMPANY_SITE):
        return hint
    try:
        data = _post(SEARCH_API, {"query": f"{name} official company website", "limit": 5})
    except Exception:
        return ""
    for r in (data.get("data") or data.get("results") or []):
        link = r.get("url") or r.get("link") or ""
        if link and not any(b in link.lower() for b in _NOT_COMPANY_SITE):
            return _root(link)
    return ""


def _scrape_profile(url: str) -> Dict[str, Any]:
    try:
        data = _post(SCRAPE_API, {
            "url": url, "formats": ["json"], "onlyMainContent": True,
            "jsonOptions": {"prompt": _PROMPT, "schema": _SCHEMA},
        })
    except Exception:
        return {}
    return ((data.get("data") or {}).get("json") or {}) or {}


def _empty() -> Dict[str, Any]:
    return {"company_summary": "", "company_remote": "", "company_hq": "",
            "is_staffing": False, "researched": False}


def _profile_to_fields(url: str, prof: Dict[str, Any]) -> Dict[str, Any]:
    remote = str(prof.get("remote_policy", "") or "").lower().strip()
    if remote not in ("remote", "hybrid", "onsite", "unknown"):
        remote = "unknown" if url else ""
    return {
        "company_summary": str(prof.get("summary", "") or "").strip()[:280],
        "company_remote": remote,
        "company_hq": str(prof.get("hq", "") or "").strip()[:80],
        "is_staffing": bool(prof.get("is_staffing_agency", False)),
        "researched": True,
        "company_url": url,
    }


# ---- cache ----------------------------------------------------------------

def load_cache(path: Path = CACHE_PATH) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                out[rec["key"]] = rec
            except Exception:
                continue
    return out


def _append_cache(rec: Dict[str, Any], path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def research_company(name: str, hint_url: str = "", cache: Dict[str, Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """Return a company profile dict, using the cache and Firecrawl. Best-effort:
    returns an empty (researched=False) profile on any failure or missing key."""
    key = normalize_company(name)
    if not key:
        return _empty()
    cache = load_cache() if cache is None else cache
    if key in cache:
        return {k: v for k, v in cache[key].items() if k not in ("key", "name", "ts")}
    if not firecrawl_key():
        return _empty()
    url = _company_site(name, hint_url)
    fields = _profile_to_fields(url, _scrape_profile(url)) if url else _empty()
    rec = {"key": key, "name": name, "ts": now_iso(), **fields}
    _append_cache(rec)
    if cache is not None:
        cache[key] = rec
    return fields
