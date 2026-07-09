"""Parse job alert emails into records + detect application-status updates.

Grounded in the real subject formats observed in the inbox:
  LinkedIn alerts : "Solution Architect - AI at OMW Consulting: up to $400K/year"
  LinkedIn jobs   : "Garreth, apply to ML Solutions Architect at Jobot and more"
                    "Your application was viewed by Telon"          (status update)
                    "Garreth, your application was sent to Mine & Yours" (status)
  Wellfound       : "New jobs: Python Full Stack Engineer at Trustume and 0 more jobs"
  Indeed          : "Staff Software Engineer - AI Marketing @ Luxury Presence"

Subject-only extraction (the headline job per email). Multi-job bodies are a
future enhancement; the store dedupes anything a board also surfaces.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

# sender that mixes opportunity mail and application-status updates
STATUS_SENDER = "jobs-noreply@linkedin.com"

_ADDR_RE = re.compile(r"<([^>]+)>")
_COMP_RE = re.compile(r":\s*((?:up to\s*)?\$[\d,]+.*)$", re.I)
_PREFIX_RE = re.compile(
    r"^\s*(garreth,\s*)?"
    r"(apply now to|apply to|new jobs? similar to|new jobs?:|new job:|"
    r"featured ai job:|featured job:)\s*",
    re.I,
)
_QUOTES = "'\"‘’“”"
_SUFFIX_RE = re.compile(r"\s+and\s+(\d+\s+)?more(\s+jobs?)?\s*$", re.I)
_SPLIT_RE = re.compile(r"^(.*\S)\s+(?:at|@)\s+(\S.*)$")
_STATUS_CO_RE = re.compile(r"(?:sent to|viewed by)\s+(.+?)\s*$", re.I)


def sender_email(from_header: str) -> str:
    """Extract the bare address from a From header ('Name <a@b.com>' -> 'a@b.com')."""
    m = _ADDR_RE.search(from_header or "")
    return (m.group(1) if m else (from_header or "")).strip().lower()


def is_status_update(sender: str, subject: str, status_subjects) -> bool:
    if sender != STATUS_SENDER:
        return False
    low = (subject or "").lower()
    return any(p.lower() in low for p in (status_subjects or []))


def status_company(subject: str) -> str:
    m = _STATUS_CO_RE.search(subject or "")
    return m.group(1).strip() if m else ""


def parse_opportunity(subject: str) -> Optional[Dict[str, str]]:
    """Return {title, company, comp} from a job-alert subject, or None if unparseable."""
    s = (subject or "").strip()
    if not s:
        return None
    # Strip prefixes + surrounding quotes, twice (handles nested cases like
    # "Garreth, apply now to 'Featured AI Job: ...'").
    for _ in range(2):
        s = _PREFIX_RE.sub("", s).strip().strip(_QUOTES).strip()

    comp = ""
    m = _COMP_RE.search(s)
    if m:
        comp = m.group(1).strip()
        s = s[: m.start()].strip()

    s = _SUFFIX_RE.sub("", s).strip()

    m = _SPLIT_RE.match(s)
    if not m:
        return None
    title = m.group(1).strip(" -–," + _QUOTES)
    company = m.group(2).strip(_QUOTES).strip()
    # trim Wellfound's "- Well"/"- Wellfound" truncation and trailing punctuation
    company = re.sub(r"\s*[-–]\s*Well(found)?$", "", company).strip(" -–," + _QUOTES)
    if not title or not company or len(company) > 80:
        return None
    return {"title": title, "company": company, "comp": comp}
