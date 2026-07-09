"""WeWorkRemotely adapter — category RSS feeds (public, no auth).

Item <title> is "Company Name: Job Title". We split on the first ': ' to get
company vs. title. Feeds are listed per-source in sources.yaml.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Dict, List

from modules.web_checker.adapters.base import http_get, partial, passes_prefilter

DEFAULT_FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
]

_TAG_RE = re.compile(r"<[^>]+>")


def _text(el, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def fetch(entry: Dict) -> List[Dict]:
    limit = int(entry.get("limit", 40))
    keywords = entry.get("keywords") or []
    source = entry.get("source", "board")
    feeds = entry.get("feeds") or DEFAULT_FEEDS

    out: List[Dict] = []
    for feed in feeds:
        try:
            root = ET.fromstring(http_get(feed))
        except Exception:
            continue  # one bad feed shouldn't sink the run
        for item in root.iter("item"):
            raw_title = _text(item, "title")
            if ": " in raw_title:
                company, title = raw_title.split(": ", 1)
            else:
                company, title = "", raw_title
            location = _text(item, "region") or "Remote"
            desc = _TAG_RE.sub(" ", _text(item, "description"))
            blob = " ".join([raw_title, desc])
            if not passes_prefilter(blob, keywords):
                continue
            out.append(partial(
                title=title,
                company=company or "(see posting)",
                url=_text(item, "link"),
                location=location,
                posted=_text(item, "pubDate"),
                snippet=desc[:1500],
                source=source,
                source_detail=entry.get("name", "weworkremotely"),
            ))
            if len(out) >= limit:
                return out
    return out
