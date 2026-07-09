"""Shared adapter helpers: HTTP GET and keyword pre-filter."""
from __future__ import annotations

import urllib.request
from typing import Dict, List

USER_AGENT = "job-ops/0.1 (+https://github.com/; personal job search)"


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def passes_prefilter(text: str, keywords: List[str]) -> bool:
    """True if no keywords configured, or text contains at least one."""
    if not keywords:
        return True
    low = (text or "").lower()
    return any(k.lower() in low for k in keywords)


def partial(
    *, title: str, company: str, url: str = "", location: str = "", comp: str = "",
    posted: str = "", snippet: str = "", source: str = "board", source_detail: str = "",
) -> Dict:
    return {
        "title": title.strip(), "company": company.strip(), "url": url.strip(),
        "location": location.strip(), "comp": comp.strip(), "posted": posted.strip(),
        "snippet": snippet.strip(), "source": source, "source_detail": source_detail,
    }
