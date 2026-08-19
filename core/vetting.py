"""Reject junk BEFORE it can surface on the board.

A cheap deterministic gate that runs ahead of the LLM scorer. Three kinds of
junk are caught here, each stamped fit_score=1 with no LLM call, no matter how a
model might otherwise rate them:

  1. Scraping ARTIFACTS  - not a single real job: a "Multiple Roles" listing
     index, a non-employer "company", a mangled title the scraper truncated to
     "Full" / "150" / a bare URL / a location string.
  2. OFF-LANE roles      - a real job, but never one of the four target lanes
     (security, DevOps/SRE, data engineer/scientist, full-stack/front/back-end,
     QA, network, mobile/embedded). These get rationalised by the LLM into
     "architecture-adjacent" and slip through at fit 6 if not blocked first.
  3. Placeholder / location-as-company records.

The LLM prompt is also tightened (see [[scoring]]), but this gate is the reliable
floor: deterministic, testable, and it never spends a page fetch or an LLM call
on something it can already tell is junk.

Carve-outs are deliberate. The candidate WANTS these, so they are never blocked:
sales / solutions engineers, applied-AI / ML / GenAI / LLM engineers, and any
architect / staff / principal / founding title.
"""
from __future__ import annotations

import re
from typing import Any, Dict

# ---------------------------------------------------------------------------
# 1. Listing-index / catch-all titles (not one concrete role).
# ---------------------------------------------------------------------------
_JUNK_TITLE = re.compile(
    r"^\s*(multiple|various|several|numerous|many|all|other|misc(ellaneous)?|see all|view all|browse)\b"
    r"|^\s*\d+\+?\s+(roles?|positions?|jobs?|openings?)\b"
    r"|\b(multiple|various|several|open|all)\s+(roles?|positions?|openings?)\b"
    r"|^\s*(roles?|positions?|openings?|opportunities|careers?|jobs?|vacancies|"
    r"we'?re hiring|hiring|now hiring|join us|join our team|open roles?)\s*$",
    re.I,
)

# Placeholder "companies" that are never a real employer. Deliberately does NOT
# list real firms (Google/Yahoo/etc. genuinely hire).
_JUNK_COMPANY = {
    "n/a", "na", "none", "unknown", "company", "various", "confidential",
    "see posting", "see description", "see above", "remote", "careers",
    "hiring", "now hiring", "startup", "tbd", "-", "?",
}

# A "company" that is really a location, e.g. "Austin, TX, US".
_LOCATION_COMPANY = re.compile(r",\s*[A-Z]{2}(\s*,\s*(US|USA|UK))?\s*$")

# Staffing / recruiting body-shops: they place people at OTHER companies, so the
# "employer" is a middleman, not the real hiring org. Rejected by name here (free,
# no Firecrawl call); the company-research is_staffing flag catches the rest.
_STAFFING_WORD = re.compile(
    r"\b(staffing|recruit(ing|ment|ers)?|talent solutions|talent acquisition|"
    r"manpower|resourcing|workforce solutions|staffing solutions|headhunt(ing|ers)?|"
    r"placement services|body ?shop|consultancy services|it services and consulting)\b",
    re.I,
)
# Named firms seen polluting the board (matched as a whole token/phrase).
_STAFFING_KNOWN = (
    "randstad", "jobot", "robert half", "insight global", "teksystems", "adecco",
    "kelly services", "kforce", "apex systems", "cybercoders", "motion recruitment",
    "synergy technologies", "lorven technologies", "xcutives", "resourcetree",
    "bright vision technologies", "yd talent solutions", "recco consulting",
    "aroha technologies", "collabera", "mindlance", "diverse lynx", "nityo infotech",
    "compunnel", "sunrise systems", "empower professionals", "e-solutions inc",
)


def _is_staffing(company: str) -> bool:
    c = company.lower().strip()
    if any(k in c for k in _STAFFING_KNOWN):
        return True
    return bool(_STAFFING_WORD.search(company))

# ---------------------------------------------------------------------------
# 2. Mangled / artifact titles (real posting, but the title field is garbage).
# ---------------------------------------------------------------------------
# Words that mark a string as an ACTUAL job title rather than a scraped fragment.
_ROLE_WORD = (
    r"engineer|architect|develop(er|ment)|consult(ant|ing)|manager|lead|analyst|"
    r"specialist|scientist|designer|director|officer|head|founder|co-?founder|"
    r"cto|cio|ciso|vp|president|strateg(ist|y)|marketer|market(ing)?|editor|"
    r"producer|ops|operations|growth|product|principal|staff|sales|solutions?|"
    r"advisor|administrator|coordinator|representative|recruiter|writer|"
    r"researcher|programmer|technician|architecture|fde|forward deployed"
)
# Left-boundary only: a role root anywhere (so plurals "Engineers"/"Architects"
# and "Engineering" all count as carrying a role word).
_HAS_ROLE = re.compile(r"(?<!\w)(" + _ROLE_WORD + r")", re.I)

# Title is a bare URL / domain (e.g. "https://seeq.com", "intelligence.com )").
_URL_TITLE = re.compile(r"https?://|(?<!\w)[a-z0-9][a-z0-9-]*\.(com|io|ai|dev|tech|so|co|org|net|xyz|app)\b", re.I)
# Scraped narrative fragment, not a title ("... is hiring in Boston", "Hey HN!").
_HIRING_FRAGMENT = re.compile(r"\b(is hiring|we'?re hiring|we are hiring|we'?re building|hey hn|hacker news)\b", re.I)
# Title that is only a location / work-arrangement descriptor.
_LOCATION_ONLY = re.compile(r"^\s*(remote|hybrid|on-?site|fully remote|us(a)?|u\.s\.|worldwide|anywhere|global)\b", re.I)


def _artifact_reason(title: str) -> str:
    """Return a reason if the title is a scraping artifact, not a real role."""
    t = re.sub(r"\s+", " ", title).strip()
    has_role = bool(_HAS_ROLE.search(t))
    # A domain is only an artifact when no role word rides along: "Scale.ai
    # Forward Deployed Engineer" is a real role, "jobs.lever.co/acme" is not.
    if _URL_TITLE.search(t) and not has_role:
        return "title is a URL/domain, not a role"
    if _HIRING_FRAGMENT.search(t):
        return "title is a scraped hiring/HN fragment, not a role"
    if not has_role:
        # No role word at all: a truncated stub ("Full", "150", "The Role"),
        # a bare location ("US Fully Remote"), or a 1-3 word fragment.
        if len(t) < 6:
            return f"'{t}' is a truncated/stub title"
        if _LOCATION_ONLY.search(t):
            return f"'{t}' is a location, not a role"
        if len(t.split()) <= 3:
            return f"'{t}' has no role and reads as a fragment"
    return ""


# ---------------------------------------------------------------------------
# 3. Off-lane roles (real jobs, never one of the four lanes).
# ---------------------------------------------------------------------------
# Kept on purpose (candidate wants these): sales/solutions eng, applied-AI/ML,
# and any architect/consultant. Detected first and short-circuited.
_KEEP = re.compile(r"(?<!\w)(sales|architect|consultant|consulting)(?!\w)", re.I)
_AI_KEEP = re.compile(r"(?<!\w)(ai|a\.i\.|ml|genai|gen ai|machine learning|llm|applied ai)(?!\w)", re.I)

# Security is out regardless (the candidate does not want security roles).
_SECURITY = re.compile(
    r"(?<!\w)(security|infosec|appsec|cyber\s?security|devsecops)(?!\w).*"
    r"(?<!\w)(engineer|architect|analyst|specialist|lead|manager|administrator|operations|ops|consultant)s?(?!\w)"
    r"|(?<!\w)(engineer|architect|analyst)s?,?\s+security(?!\w)"
    r"|(?<!\w)(penetration testers?|pentesters?|devsecops)(?!\w)",
    re.I,
)
# Data science / data scientist (a consultant-titled data-science role is kept).
_DATA_SCI = re.compile(r"(?<!\w)data scien(ce|tists?)(?!\w)", re.I)
# DevOps / SRE, standalone (no "engineer" suffix needed).
_DEVOPS = re.compile(r"(?<!\w)(devops|dev ops|sre|site reliability|site-reliability)(?!\w)", re.I)
# Off-lane engineer families: "<family> engineer(s)". AI/ML variants are carved
# out by the caller so "AI Platform Engineer" survives.
_OFFLANE_ENG = re.compile(
    r"(?<!\w)(data|back-?end|front-?end|full[ -]?stack|network|qa|quality assurance|"
    r"mobile|ios|android|embedded|firmware|hardware|database|dba)\s+engineers?(?!\w)",
    re.I,
)


def _offlane_reason(title: str) -> str:
    """Return a reason if the title is a real role but off every target lane."""
    t = title or ""
    if _SECURITY.search(t):
        return "security role (off-lane)"
    if _KEEP.search(t):
        return ""  # sales / solutions / architect / consultant -> always kept
    if _DATA_SCI.search(t):
        return "data science role (off-lane)"
    if _DEVOPS.search(t):
        return "devops/sre role (off-lane)"
    if _OFFLANE_ENG.search(t) and not _AI_KEEP.search(t):
        return "off-lane engineering role (not one of the four lanes)"
    return ""


# ---------------------------------------------------------------------------
# 4. Geography gate. The candidate can only work in the US or Canada, so a role
#    anywhere else is rejected outright - no matter how well it fits the lane.
#    (A senior on-site AI role in Bangalore paying in rupees is still a hard no.)
# ---------------------------------------------------------------------------
# Salary quoted in a non-USD/CAD currency == the role is outside US/Canada.
_FOREIGN_CCY = re.compile(
    r"[₹€£¥₱₦₪₩฿]"          # ₹ € £ ¥ ₱ ₦ ₪ ₩ ฿
    r"|\b(INR|EUR|GBP|JPY|CNY|RMB|SGD|AED|SAR|QAR|PHP|MYR|IDR|THB|VND|BRL|"
    r"ZAR|MXN|NGN|PLN|SEK|NOK|DKK|CHF|ILS|KRW|TRY|RUB|HKD|TWD|AUD|NZD|"
    r"CZK|HUF|RON|PKR|LKR|EGP|KES|BDT)\b"
    r"|\bRs\.?\b"                                                        # rupees
    r"|(?<![A-Za-z])(S\$|A\$|NZ\$|R\$|HK\$|MX\$)"                        # non-US/CA prefixed $
    r"|zł\b",                                                       # zł zloty
    re.I,
)

# US states + DC and Canadian provinces (2-letter, matched after a comma), plus
# spelled-out US/Canada signals. Presence of one ALLOWS a location that would
# otherwise trip a foreign-city name (e.g. "London, KY" or "Paris, TX").
_ALLOW_CODES = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
    "ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "NT", "YT", "NU",
)
_US_CA_ALLOW = re.compile(
    r",\s*(" + "|".join(_ALLOW_CODES) + r")\b"
    r"|\b(united states|u\.?s\.?a\.?|usa|u\.s\.|us|"
    # NOTE: no bare "america(s)" - it would allow "Latin America" / "South America"
    r"north america|canada|canadian|remote\s*[-,/]?\s*(us|usa|united states|canada|na))\b",
    re.I,
)

# Countries / regions outside US+Canada. These never collide with US place names,
# so they reject unconditionally. NOTE: \bIndia\b won't match "Indiana".
_FOREIGN_COUNTRY = re.compile(
    r"\b(india|united kingdom|uk|england|scotland|wales|ireland|germany|france|"
    r"spain|italy|netherlands|poland|portugal|sweden|norway|denmark|finland|"
    r"switzerland|austria|belgium|romania|bulgaria|greece|czechia|hungary|"
    r"ukraine|turkey|israel|uae|united arab emirates|saudi|qatar|egypt|nigeria|"
    r"kenya|south africa|brazil|argentina|colombia|chile|peru|mexico|"
    r"australia|new zealand|singapore|hong kong|japan|china|south korea|korea|"
    r"taiwan|philippines|indonesia|malaysia|thailand|vietnam|pakistan|"
    r"bangladesh|sri lanka|nepal|"
    # Latin America (note: NOT 'georgia' - collides with the US state)
    r"costa rica|panama|uruguay|ecuador|venezuela|guatemala|honduras|"
    r"nicaragua|el salvador|bolivia|paraguay|dominican republic|"
    # Eastern Europe / Balkans / Baltics / Caucasus / Central Asia
    r"serbia|croatia|slovenia|slovakia|lithuania|latvia|estonia|armenia|"
    r"belarus|kazakhstan|uzbekistan|azerbaijan|bosnia|montenegro|"
    r"macedonia|albania|moldova|cyprus|malta|luxembourg|iceland|"
    # Africa / Middle East
    r"morocco|algeria|tunisia|ghana|uganda|tanzania|ethiopia|rwanda|"
    r"mauritius|jordan|lebanon|"
    r"emea|apac|latam|latin america|south america|central america|mena|europe|middle east)\b",
    re.I,
)
# Foreign cities (given without a country). Rejected unless a US/Canada state
# signal is also present (guards against US towns named London/Paris/Berlin).
_FOREIGN_CITY = re.compile(
    r"\b(bangalore|bengaluru|hyderabad|pune|mumbai|new delhi|delhi|noida|"
    r"gurgaon|gurugram|chennai|kolkata|ahmedabad|jaipur|"
    r"london|manchester|dublin|berlin|munich|frankfurt|paris|amsterdam|madrid|"
    r"barcelona|lisbon|warsaw|krakow|bucharest|prague|tel aviv|dubai|"
    r"bangkok|manila|jakarta|kuala lumpur|ho chi minh|hanoi|karachi|lahore|"
    r"são paulo|sao paulo|mexico city|buenos aires|bogota|lagos|nairobi|"
    r"belgrade|zagreb|ljubljana|sofia|vilnius|riga|tallinn|tbilisi|yerevan|"
    r"almaty|casablanca|accra|kampala|addis ababa|tunis|amman|beirut|"
    r"sarajevo|colombo|dhaka|kathmandu|phnom penh)\b",
    re.I,
)


def location_reason(record: Dict[str, Any]) -> str:
    """Reject a role whose geography is outside the US/Canada allow-list, else ''.
    Signals, strongest first: a non-USD/CAD salary, then an explicit foreign
    country/region, then a foreign city with no US/Canada state signal present."""
    loc = record.get("location") or ""
    comp = record.get("comp") or ""
    title = record.get("title") or ""
    # A foreign currency is decisive - it overrides even a US-looking location.
    if _FOREIGN_CCY.search(comp) or _FOREIGN_CCY.search(loc):
        return "salary in a non-USD/CAD currency (role is outside US/Canada)"
    # A real US/Canada state/province code (", NH") or explicit US/Canada name is
    # decisive the other way: it clears a location whose city/country name collides
    # with a US town (Lebanon NH, Panama City FL, London KY, Malta NY, ...).
    if _US_CA_ALLOW.search(loc):
        return ""
    for field in (loc, title):
        m = _FOREIGN_COUNTRY.search(field) or _FOREIGN_CITY.search(field)
        if m:
            return f"location outside US/Canada ({m.group(0)})"
    return ""


def junk_reason(record: Dict[str, Any]) -> str:
    """Return a short reason if the record must never surface, else ''.

    Covers scraping artifacts, placeholder/location companies, mangled titles,
    off-lane roles, staffing firms, and out-of-geography roles. Used by scoring
    (stamp fit_score=1, skip the LLM) and the page-fetch/research gates."""
    title = (record.get("title") or "").strip()
    company = (record.get("company") or "").strip()
    if len(title) < 3:
        return "title missing/too short"
    if len(company) < 2:
        return "company missing/too short"
    if company.lower() in _JUNK_COMPANY:
        return f"'{company}' is not an employer (search engine / board / placeholder)"
    if _LOCATION_COMPANY.search(company):
        return f"'{company}' looks like a location, not an employer"
    if _is_staffing(company):
        return f"'{company}' is a staffing/recruiting agency, not the hiring company"
    if _JUNK_TITLE.search(title):
        return f"'{title}' is a listing index, not a single role"
    artifact = _artifact_reason(title)
    if artifact:
        return artifact
    offlane = _offlane_reason(title)
    if offlane:
        return offlane
    geo = location_reason(record)
    if geo:
        return geo
    return ""


def is_junk(record: Dict[str, Any]) -> bool:
    return bool(junk_reason(record))
