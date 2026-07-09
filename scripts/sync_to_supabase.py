#!/usr/bin/env python3
"""Push the local JSONL store into Supabase (jobops_leads).

Inserts only NEW leads (ids not already in Supabase), so edits made in the
dashboard (contact, notes, status) are never clobbered. Run after a scan to
publish fresh leads to the deployed dashboard.

Needs SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment (.env).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core.config  # noqa: E402  (loads .env)
from core import store  # noqa: E402

TABLE = "jobops_leads"
COLS = ["id", "schema_version", "lane", "source", "source_detail", "title", "company",
        "url", "location", "comp", "posted", "first_seen", "last_seen", "fit_score",
        "fit_rationale", "red_flags", "contact", "notes", "status", "snippet"]


def _headers():
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _req(method, path, body=None):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else []


def existing_ids() -> set:
    out, page = set(), 0
    while True:
        rows = _req("GET", f"/rest/v1/{TABLE}?select=id&limit=1000&offset={page*1000}")
        if not rows:
            break
        out.update(r["id"] for r in rows)
        if len(rows) < 1000:
            break
        page += 1
    return out


def to_row(rec: dict) -> dict:
    return {c: rec.get(c) for c in COLS if c in rec}


def main() -> int:
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY"):
        print("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env first.", file=sys.stderr)
        return 2
    recs = store.load()
    have = existing_ids()
    new = [to_row(r) for r in recs if r.get("id") not in have]
    print(f"store={len(recs)} already_in_supabase={len(have)} to_insert={len(new)}")
    for i in range(0, len(new), 100):
        chunk = new[i:i + 100]
        _req("POST", f"/rest/v1/{TABLE}", chunk)
        print(f"  inserted {i + len(chunk)}/{len(new)}")
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
