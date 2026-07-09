"""RemoteOK adapter — https://remoteok.com/api (public JSON, no auth).

The first element of the array is a legal/ToS notice, not a job. RemoteOK's ToS
asks for a link back; we store the canonical posting URL, satisfying that.
"""
from __future__ import annotations

import json
from typing import Dict, List

from modules.web_checker.adapters.base import http_get, partial, passes_prefilter

API = "https://remoteok.com/api"


def fetch(entry: Dict) -> List[Dict]:
    limit = int(entry.get("limit", 60))
    keywords = entry.get("keywords") or []
    source = entry.get("source", "board")
    raw = json.loads(http_get(API).decode("utf-8"))

    out: List[Dict] = []
    for item in raw:
        if not isinstance(item, dict) or "position" not in item:
            continue  # skips the leading legal-notice object
        title = item.get("position") or ""
        company = item.get("company") or ""
        tags = " ".join(item.get("tags", []) or [])
        desc = item.get("description", "") or ""
        blob = " ".join([title, company, tags])
        if not passes_prefilter(blob, keywords):
            continue
        comp = ""
        if item.get("salary_min") and item.get("salary_max"):
            comp = f"${item['salary_min']}-${item['salary_max']}"
        out.append(partial(
            title=title,
            company=company,
            url=item.get("url", "") or item.get("apply_url", ""),
            location=item.get("location", "") or "Remote",
            comp=comp,
            posted=str(item.get("date", "")),
            snippet=(tags + " " + desc)[:1500],
            source=source,
            source_detail="remoteok",
        ))
        if len(out) >= limit:
            break
    return out
