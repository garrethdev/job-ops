"""Reject obvious scraping artifacts before they can surface on the board.

This is a cheap deterministic gate that runs BEFORE the LLM scorer: a record that
is plainly not a single real job (a "Multiple Roles" listing index, a non-employer
"company" like a search engine, an empty/stub title) is stamped fit_score=1 and
never surfaces — no LLM call, no matter how the model might have rated it. The LLM
prompt is also tightened to reject non-matches, but this gate catches the artifacts
that shouldn't reach scoring at all (see [[scoring]]).
"""
from __future__ import annotations

import re
from typing import Any, Dict

# Titles that are listing-index / catch-all artifacts, not one concrete role.
_JUNK_TITLE = re.compile(
    r"^\s*(multiple|various|several|numerous|many|all|other|misc(ellaneous)?|see all|view all|browse)\b"
    r"|^\s*\d+\+?\s+(roles?|positions?|jobs?|openings?)\b"
    r"|\b(multiple|various|several|open|all)\s+(roles?|positions?|openings?)\b"
    r"|^\s*(roles?|positions?|openings?|opportunities|careers?|jobs?|vacancies|"
    r"we'?re hiring|hiring|now hiring|join us|join our team|open roles?)\s*$",
    re.I,
)

# Placeholder "companies" that are never a real employer. Deliberately does NOT
# list real firms (Google/Yahoo/etc. genuinely hire) — a listing scraped under a
# real company name is filtered by the title gate + relevance scoring, not here.
_JUNK_COMPANY = {
    "n/a", "na", "none", "unknown", "company", "various", "confidential",
    "see posting", "see description", "see above", "remote", "careers",
    "hiring", "now hiring", "startup", "tbd", "-", "?",
}


def junk_reason(record: Dict[str, Any]) -> str:
    """Return a short reason if the record is a scraping artifact, else ''."""
    title = (record.get("title") or "").strip()
    company = (record.get("company") or "").strip()
    if len(title) < 3:
        return "title missing/too short"
    if len(company) < 2:
        return "company missing/too short"
    if company.lower() in _JUNK_COMPANY:
        return f"'{company}' is not an employer (search engine / board / placeholder)"
    if _JUNK_TITLE.search(title):
        return f"'{title}' is a listing index, not a single role"
    return ""


def is_junk(record: Dict[str, Any]) -> bool:
    return bool(junk_reason(record))
