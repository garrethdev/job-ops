"""Apollo client — find the hiring decision-maker at a company (name + LinkedIn + email).

Three REST calls (stdlib only):
  1. org search   POST /mixed_companies/search   name -> primary_domain   (free)
  2. people search POST /mixed_people/api_search  domain+titles -> candidates (free, masked)
  3. people match  POST /people/match             candidate id -> full contact (1 CREDIT)

find_contact() runs all three and returns a `contact` dict ready to drop into a
record's `contact` field, plus metadata (credits_used, candidate pool size). A
single match returns LinkedIn AND email together, so one credit fills both.

Shared in core/ so the dashboard and the Module C cron both use it without a
cross-module import. Reads APOLLO_API_KEY from the environment.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, List, Optional

from core.config import apollo_key

BASE = "https://api.apollo.io/api/v1"

# Which decision-maker to target per role lane (best-fit first).
TITLES_BY_LANE = {
    "software-architect": [
        "VP Engineering", "VP of Engineering", "Head of Engineering",
        "Director of Engineering", "CTO", "Engineering Manager",
    ],
    "gtm-engineer": [
        "VP Sales", "Head of Growth", "Chief Revenue Officer", "VP Marketing",
        "Head of Revenue", "Head of Sales", "Founder",
    ],
    "ai-consultant": [
        "CTO", "Head of AI", "Chief AI Officer", "VP Engineering",
        "Head of Data", "Founder",
    ],
    "ai-video-editor": [
        "Head of Content", "Creative Director", "Head of Production",
        "Head of Social", "Head of Marketing", "Brand Director",
    ],
}
_FALLBACK_TITLES = ["Founder", "CEO", "CTO", "Head of Talent", "Recruiter", "Hiring Manager"]


class ApolloError(RuntimeError):
    pass


def _post(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    key = apollo_key()
    if not key:
        raise ApolloError("APOLLO_API_KEY not set")
    req = urllib.request.Request(
        f"{BASE}/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"X-Api-Key": key, "Content-Type": "application/json", "Cache-Control": "no-cache"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, dict) and data.get("error"):
        raise ApolloError(str(data["error"]))
    return data


def resolve_domain(company: str) -> Optional[str]:
    """Company name -> primary domain (free). None if not found."""
    data = _post("mixed_companies/search", {"q_organization_name": company, "per_page": 1})
    orgs = data.get("organizations") or data.get("accounts") or []
    for o in orgs:
        if o.get("primary_domain"):
            return o["primary_domain"]
    return None


def search_people(
    domain: Optional[str],
    company: str,
    titles: Optional[List[str]] = None,
    seniorities: Optional[List[str]] = None,
    per_page: int = 5,
) -> List[Dict[str, Any]]:
    """Candidate decision-makers (free, last names masked). Prefers domain filter."""
    payload: Dict[str, Any] = {"per_page": per_page, "page": 1}
    if titles:
        payload["person_titles"] = titles
    if seniorities:
        payload["person_seniorities"] = seniorities
    if domain:
        payload["q_organization_domains_list"] = [domain]
    else:
        payload["q_keywords"] = company
    data = _post("mixed_people/api_search", payload)
    return data.get("people", []) or []


def match_person(person_id: str) -> Dict[str, Any]:
    """Reveal full contact for a candidate id. COSTS 1 CREDIT on a match."""
    data = _post("people/match", {"id": person_id, "reveal_personal_emails": True})
    return data.get("person") or {}


def find_contact(company: str, lane: str = "", per_page: int = 5) -> Dict[str, Any]:
    """Find + reveal the best hiring decision-maker at `company`.

    Returns {contact, meta}. contact = {name, title, email, linkedin}. Credit is
    spent only when a candidate is found and matched (0 credits on no match).
    """
    titles = TITLES_BY_LANE.get(lane, _FALLBACK_TITLES)
    domain = resolve_domain(company)

    # Progressive broadening — all searches are free, so try harder before giving up:
    # 1) role-specific titles  2) generic leadership titles  3) any senior person.
    candidates = search_people(domain, company, titles=titles, per_page=per_page)
    tier = "role-titles"
    if not candidates:
        candidates = search_people(domain, company, titles=_FALLBACK_TITLES, per_page=per_page)
        tier = "leadership-titles"
    if not candidates:
        candidates = search_people(
            domain, company,
            seniorities=["c_suite", "vp", "head", "director", "owner", "partner", "founder"],
            per_page=per_page,
        )
        tier = "any-senior"
    meta = {"domain": domain, "candidates": len(candidates), "match_tier": tier, "credits_used": 0}

    if not candidates:
        return {"contact": None, "meta": {**meta, "reason": "no decision-maker found"}}

    top = candidates[0]
    person = match_person(top["id"])
    meta["credits_used"] = 1 if person else 0
    if not person:
        return {"contact": None, "meta": {**meta, "reason": "match failed"}}

    contact = {
        "name": person.get("name", "") or f"{person.get('first_name','')} {person.get('last_name','')}".strip(),
        "title": person.get("title", "") or top.get("title", ""),
        "email": person.get("email", "") or "",
        "linkedin": person.get("linkedin_url", "") or "",
    }
    return {"contact": contact, "meta": meta}
