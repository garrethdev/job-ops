"""Dedupe + merge logic for the opportunities store.

Two records are the same opportunity if EITHER:
  - normalized(company)+normalized(title) match, OR
  - normalized(url) matches (and both have a url)

This catches the "same job via email alert AND board scrape" case: the URL key
merges them even when company/title strings differ slightly between sources.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.schema import normalize_company, normalize_title, normalize_url


def company_title_key(record: Dict[str, Any]) -> str:
    return normalize_company(record.get("company", "")) + "|" + normalize_title(record.get("title", ""))


def url_key(record: Dict[str, Any]) -> Optional[str]:
    u = normalize_url(record.get("url", ""))
    return u or None


def build_index(records: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Return (company_title -> idx, url -> idx) lookup maps over `records`."""
    ct: Dict[str, int] = {}
    by_url: Dict[str, int] = {}
    for i, r in enumerate(records):
        ct[company_title_key(r)] = i
        uk = url_key(r)
        if uk:
            by_url[uk] = i
    return ct, by_url


def find_duplicate(
    record: Dict[str, Any],
    records: List[Dict[str, Any]],
    ct_index: Dict[str, int],
    url_index: Dict[str, int],
) -> Optional[int]:
    """Return the index of an existing duplicate of `record`, or None."""
    idx = ct_index.get(company_title_key(record))
    if idx is not None:
        return idx
    uk = url_key(record)
    if uk is not None:
        return url_index.get(uk)
    return None


# Fields that a re-sighting is allowed to fill in if the stored value is empty.
_FILLABLE = ("url", "location", "comp", "posted", "source_detail")


def merge(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a re-sighting into the stored record. Non-destructive.

    - Keeps the earliest first_seen, advances last_seen.
    - Fills empty fields from the incoming record but never overwrites
      human/scoring/enrichment progress (lane, fit_score, contact, status).
    - Records that the opportunity was seen from more than one source.
    """
    merged = dict(existing)
    merged["last_seen"] = incoming.get("last_seen", existing.get("last_seen"))
    for f in _FILLABLE:
        if not merged.get(f) and incoming.get(f):
            merged[f] = incoming[f]
    # Track multi-source sightings without losing the original source.
    if incoming.get("source") and incoming["source"] != existing.get("source"):
        seen = set(existing.get("also_seen_via", []))
        seen.add(incoming["source"])
        merged["also_seen_via"] = sorted(seen)
    return merged
