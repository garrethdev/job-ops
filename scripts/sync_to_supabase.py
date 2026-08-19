#!/usr/bin/env python3
"""Push the local JSONL store into Supabase (jobops_leads).

Upserts every eligible lead through the jobops_upsert_discovery RPC: new ids
are inserted (status='new', stage='new'), existing ids get ONLY their
pipeline-owned discovery fields refreshed (title/score/company research/...),
so re-scoring and Firecrawl company research reach rows already on the board.
Dashboard-owned fields (status, stage, notes, contact, warm, outreached_at,
updated_at) are never sent, so edits made in the dashboard are never clobbered.
Run after a scan or re-score to publish fresh data to the deployed dashboard.

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

RPC = "jobops_upsert_discovery"

# Pipeline-owned discovery fields: the ONLY columns the RPC updates on rows
# that already exist in Supabase.
DISCOVERY_COLS = ["title", "company", "url", "location", "comp", "posted",
                  "last_seen", "fit_score", "fit_rationale", "red_flags", "snippet",
                  "company_summary", "company_remote", "company_hq"]

# Insert-only provenance: sent so brand-new rows land with identity intact;
# the RPC ignores these on conflict (they never change after first insert).
INSERT_COLS = ["id", "schema_version", "lane", "source", "source_detail", "first_seen"]

# Dashboard-owned workflow fields. The RPC wouldn't apply them anyway, but
# keeping them out of the payload makes the ownership split auditable here.
DASHBOARD_OWNED = ("status", "stage", "notes", "contact", "warm",
                   "outreached_at", "updated_at")

# Statuses that never belong on the board: rejected (junk) and deferred (backlog,
# waiting for a quieter day). They stay in the local store but aren't published.
SKIP_STATUS = {"rejected", "deferred"}


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


def to_row(rec: dict) -> dict:
    """Build the RPC payload for one record: discovery fields + insert-only
    provenance, and nothing else. Pure (no I/O) so the split is unit-testable."""
    return {c: rec.get(c) for c in INSERT_COLS + DISCOVERY_COLS if c in rec}


def eligible_rows(recs: list) -> list:
    """Payloads for every record worth publishing (not locally rejected/deferred)."""
    return [to_row(r) for r in recs if r.get("status") not in SKIP_STATUS]


def main() -> int:
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY"):
        print("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env first.", file=sys.stderr)
        return 2
    recs = store.load()
    rows = eligible_rows(recs)
    print(f"store={len(recs)} to_upsert={len(rows)}")
    touched = 0
    for i in range(0, len(rows), 100):
        chunk = rows[i:i + 100]
        n = _req("POST", f"/rest/v1/rpc/{RPC}", {"rows": chunk})
        touched += n if isinstance(n, int) else 0
        print(f"  upserted {i + len(chunk)}/{len(rows)}")
    print(f"done. rows_touched={touched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
