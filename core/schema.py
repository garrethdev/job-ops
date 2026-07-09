"""Opportunity record schema — the only inter-module contract.

Every record carries `schema_version`. Modules validate against this before
writing to the store. Bumping the schema is a deliberate, versioned change:
increment SCHEMA_VERSION and add a migration note in docs/.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.config import LANES, SOURCES, STATUSES

SCHEMA_VERSION = 1


def now_iso() -> str:
    """UTC timestamp, second precision, ISO-8601 with Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_company(company: str) -> str:
    """Lowercase, strip legal suffixes and punctuation, collapse whitespace."""
    s = (company or "").lower().strip()
    s = re.sub(r"[.,]", " ", s)
    # strip common legal/entity suffixes
    s = re.sub(r"\b(inc|llc|ltd|limited|gmbh|corp|co|company|plc|ab|as|oy|bv)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_title(title: str) -> str:
    """Lowercase, drop seniority/formatting noise that shouldn't split a dupe."""
    s = (title or "").lower().strip()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_url(url: str) -> str:
    """Scheme/host-insensitive, query+fragment stripped, no trailing slash."""
    s = (url or "").strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^www\.", "", s)
    s = s.split("#", 1)[0].split("?", 1)[0]
    s = s.rstrip("/")
    return s


def make_id(company: str, title: str) -> str:
    """Stable id = sha1(normalized company + '|' + normalized title)."""
    key = normalize_company(company) + "|" + normalize_title(title)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def new_record(
    *,
    title: str,
    company: str,
    url: str = "",
    source: str,
    lane: str = "",
    location: str = "",
    comp: str = "",
    posted: str = "",
    source_detail: str = "",
) -> Dict[str, Any]:
    """Construct a fresh record with server-side fields filled in.

    lane/fit_score/fit_rationale/red_flags are populated later by scoring.
    contact is populated later by contact_enricher.
    """
    ts = now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "id": make_id(company, title),
        "lane": lane,                # set by scoring
        "source": source,           # email | board | marketplace
        "source_detail": source_detail,  # adapter / sender that produced it
        "title": title,
        "company": company,
        "url": url,
        "location": location,
        "comp": comp,
        "posted": posted,
        "first_seen": ts,
        "last_seen": ts,
        "fit_score": 0,
        "fit_rationale": "",
        "red_flags": [],
        "contact": {"name": "", "title": "", "email": "", "linkedin": ""},
        "status": "new",
    }


REQUIRED_FIELDS = (
    "schema_version", "id", "lane", "source", "title", "company",
    "url", "first_seen", "last_seen", "fit_score", "status", "contact",
)


class SchemaError(ValueError):
    """Raised when a record fails validation before a store write."""


def validate(record: Dict[str, Any]) -> List[str]:
    """Return a list of problems; empty list == valid.

    Strict on enums and required keys so a malformed record can never reach
    the store (isolation rule: one module cannot corrupt the shared file).
    """
    errs: List[str] = []
    for f in REQUIRED_FIELDS:
        if f not in record:
            errs.append(f"missing required field: {f}")
    if not errs:
        if record["schema_version"] != SCHEMA_VERSION:
            errs.append(
                f"schema_version {record['schema_version']} != {SCHEMA_VERSION}"
            )
        if record["source"] not in SOURCES:
            errs.append(f"invalid source: {record['source']!r}")
        if record["status"] not in STATUSES:
            errs.append(f"invalid status: {record['status']!r}")
        # lane may be empty ("") only while status == new (pre-scoring)
        if record["lane"] and record["lane"] not in LANES:
            errs.append(f"invalid lane: {record['lane']!r}")
        if record["lane"] == "" and record["status"] != "new":
            errs.append("lane must be set once status advances past 'new'")
        if not isinstance(record["fit_score"], int) or not (0 <= record["fit_score"] <= 10):
            errs.append(f"fit_score out of range: {record['fit_score']!r}")
        c = record.get("contact")
        if not isinstance(c, dict) or set(("name", "title", "email", "linkedin")) - set(c):
            errs.append("contact must have name/title/email/linkedin keys")
        if not record["title"] or not record["company"]:
            errs.append("title and company are required and non-empty")
    return errs


def validate_or_raise(record: Dict[str, Any]) -> None:
    errs = validate(record)
    if errs:
        raise SchemaError("; ".join(errs))
