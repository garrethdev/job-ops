"""Firecrawl adapter — structured job extraction from JS-rendered boards.

Firecrawl's scrape+JSON-extract pulls {title, company, location, url} per listing.
Per-board knobs in sources.yaml:
  url / urls          the board listing page(s)
  wait_for            ms to wait for a JS SPA to render (e.g. 8000 for YC/Wellfound)
  url_must_contain    only trust extracted apply-URLs containing this substring;
                      default is "same domain as the board". This is critical:
                      Firecrawl's JSON extractor sometimes HALLUCINATES a per-role
                      url by gluing the slug onto the employer's domain — those
                      resolve to unrelated sites, so we drop any off-board url.
  company_from_detail true for boards that hide the employer on the list page
                      (ai-jobs.net); fetch each kept role's detail page for it.
  prompt              extraction prompt override
Costs Firecrawl credits per scrape. Reads FIRECRAWL_API_KEY from the environment.
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
                    "comp": {"type": "string"},
                    "url": {"type": "string"},
                },
            },
        }
    },
}
_COMPANY_SCHEMA = {"type": "object", "properties": {"company": {"type": "string"}}}
_DEFAULT_PROMPT = (
    "Extract every job listing on this page: the job title, the hiring company "
    "name, the location, and the absolute URL to the posting."
)
_PLACEHOLDER_COMPANY = ("", "not specified", "n/a", "na", "unknown", "none", "-")


def _root(url: str) -> str:
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _host(url: str) -> str:
    h = urllib.parse.urlparse(url).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def _scrape(url: str, prompt: str, schema: Dict, wait_for: int, timeout: int) -> Dict:
    key = firecrawl_key()
    if not key:
        raise RuntimeError("FIRECRAWL_API_KEY not set")
    payload = {
        "url": url,
        "formats": ["json"],
        "onlyMainContent": True,
        "jsonOptions": {"prompt": prompt, "schema": schema},
    }
    if wait_for:
        payload["waitFor"] = wait_for
    req = urllib.request.Request(
        API, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return ((json.loads(resp.read().decode("utf-8")).get("data") or {}).get("json") or {})


def _scrape_jobs(url: str, prompt: str, wait_for: int, timeout: int = 180) -> List[Dict]:
    for attempt in range(2):  # JS SPAs sometimes return empty on the first render
        try:
            jobs = _scrape(url, prompt, _SCHEMA, wait_for, timeout).get("jobs") or []
            if jobs or attempt:
                return jobs
        except Exception:
            if attempt:
                raise
    return []


def _detail_company(detail_url: str, wait_for: int) -> str:
    try:
        c = _scrape(detail_url,
                    "Return ONLY the hiring company/employer name for this single job posting.",
                    _COMPANY_SCHEMA, wait_for, 90).get("company") or ""
        return c.strip()
    except Exception:
        return ""


# Real applicant-tracking / apply domains that aggregator boards (bloomberry,
# cargo) legitimately link OUT to — so a cross-domain link to one of these is a
# real apply page, not a hallucination.
_ATS_DOMAINS = (
    "ashbyhq.com", "greenhouse.io", "lever.co", "workable.com", "recruitee.com",
    "comeet.com", "ultipro.com", "myworkdayjobs.com", "smartrecruiters.com",
    "breezy.hr", "teamtailor.com", "bamboohr.com", "jobvite.com", "rippling.com",
    "linkedin.com/jobs", "naukri.com",
)


def _valid_link(link: str, board_url: str, must_contain: str, trust_ats: bool = False) -> str:
    """Return the apply URL only if it's trustworthy, else '' (drops hallucinations)."""
    link = (link or "").strip()
    if not link:
        return ""
    if link.startswith("/"):
        link = _root(board_url) + link
    low = link.lower()
    if must_contain:
        return link if must_contain.lower() in low else ""
    if _host(board_url) in low:
        return link  # same board domain
    if trust_ats and any(d in low for d in _ATS_DOMAINS):
        return link  # aggregator board linking out to a real ATS/apply page
    return ""


def fetch(entry: Dict) -> List[Dict]:
    limit = int(entry.get("limit", 25))
    keywords = entry.get("keywords") or []
    source = entry.get("source", "board")
    prompt = entry.get("prompt", _DEFAULT_PROMPT)
    wait_for = int(entry.get("wait_for", 0))
    must_contain = entry.get("url_must_contain", "")
    no_url = bool(entry.get("no_url"))  # board has no real per-role links (only category pages)
    trust_ats = bool(entry.get("trust_ats"))  # aggregator board links out to real ATS pages
    company_from_detail = bool(entry.get("company_from_detail"))
    name = entry.get("name", "firecrawl")
    urls = entry.get("urls") or ([entry["url"]] if entry.get("url") else [])

    out: List[Dict] = []
    for url in urls:
        try:
            jobs = _scrape_jobs(url, prompt, wait_for)
        except Exception:
            continue  # one board failing must not sink the run
        for j in jobs:
            title = (j.get("title") or "").strip()
            if not title:
                continue
            company = (j.get("company") or "").strip()
            if company.lower() in _PLACEHOLDER_COMPANY:
                company = ""
            location = (j.get("location") or "").strip()
            link = "" if no_url else _valid_link(j.get("url"), url, must_contain, trust_ats)
            if not passes_prefilter(" ".join([title, company, location]), keywords):
                continue
            if company_from_detail and not company and link:
                company = _detail_company(link, wait_for)  # employer hidden on the list page
            if not company:
                continue  # no real employer -> would be junk-gated anyway
            out.append(partial(
                title=title, company=company, url=link, location=location,
                comp=(j.get("comp") or "").strip(), source=source, source_detail=name,
            ))
            if len(out) >= limit:
                return out
    return out
