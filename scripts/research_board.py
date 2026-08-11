#!/usr/bin/env python3
"""Backfill Firecrawl company research onto the existing Supabase board.

For every unique company among the non-rejected leads, research it once (cached
in store/companies.jsonl), write company_summary / company_remote / company_hq
back to every one of its roles, and REJECT roles whose company is a staffing
agency or on-site only (never touching a lead the user has engaged with).

  python -m scripts.research_board --limit 5   # research only 5 companies (cost probe)
  python -m scripts.research_board              # research all, write fields, apply gate

BILLED: each new (uncached) company costs up to ~2 Firecrawl calls. Re-runs are
free for already-cached companies.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core.config  # noqa: E402  (loads .env)
from core.schema import normalize_company  # noqa: E402
from modules.web_checker.company import load_cache, research_company  # noqa: E402

TABLE = "jobops_leads"
WORKERS = 4


def _headers():
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _req(method, path, body=None):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else []


def _touched(r: dict) -> bool:
    if r.get("warm") or (r.get("stage") or "new") != "new" or (r.get("notes") or "").strip():
        return True
    c = r.get("contact") or {}
    return bool((c.get("linkedin") or "").strip() or (c.get("email") or "").strip())


def load_board() -> list:
    out, page = [], 0
    cols = "id,title,company,url,warm,stage,notes,contact,status"
    while True:
        rows = _req("GET", f"/rest/v1/{TABLE}?select={cols}&status=neq.rejected&limit=1000&offset={page*1000}")
        out.extend(rows)
        if len(rows) < 1000:
            break
        page += 1
    return out


def main() -> int:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    board = load_board()
    by_company = defaultdict(list)
    for r in board:
        key = normalize_company(r.get("company", ""))
        if key:
            by_company[key].append(r)
    companies = [(k, rows[0].get("company", ""), rows[0].get("url", "")) for k, rows in by_company.items()]
    if limit:
        companies = companies[:limit]
    print(f"board={len(board)} unique_companies={len(by_company)} researching={len(companies)}")

    cache = load_cache()
    profiles = {}

    def do(item):
        key, name, url = item
        profiles[key] = research_company(name, url, cache=cache)

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(do, companies))

    stats = Counter()
    for key, prof in profiles.items():
        rows = by_company[key]
        patch = {k: prof.get(k, "") for k in ("company_summary", "company_remote", "company_hq")}
        reject = None
        if prof.get("is_staffing"):
            reject = "staffing/recruiting agency (company research)"
        elif prof.get("company_remote") == "onsite":
            reject = "company is on-site only (remote/hybrid required)"
        stats["researched" if prof.get("researched") else "no_data"] += 1
        for r in rows:
            body = dict(patch)
            if reject and not _touched(r):
                body["status"] = "rejected"
                body["fit_rationale"] = "[company gate] " + reject
                stats["rejected_" + ("staffing" if "staffing" in reject else "onsite")] += 1
            _req("PATCH", f"/rest/v1/{TABLE}?id=eq.{r['id']}", body)

    print("\nresult:")
    for k, v in stats.most_common():
        print(f"  {v:4d}  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
