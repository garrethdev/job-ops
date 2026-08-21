#!/usr/bin/env python3
"""Cloud watchdog: alert when recruiter outreach has silently stalled.

Runs in GitHub Actions (NOT on the laptop), so it still fires when the Claude
app is closed — which is exactly the failure it exists to catch: the local
hourly batch runner cannot run, cannot send, and cannot warn, all at once.

It only READS (Gmail scope here is gmail.readonly) and never sends recruiter
mail. Alerting is done by exiting non-zero so the workflow fails and GitHub
notifies, plus the workflow opens an issue.

Stalled means: recruiters are still waiting to be contacted AND no outreach
email has gone out in the last `--stale-days` days.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core.config  # noqa: E402  (loads .env)
from core.gmail import Gmail  # noqa: E402

SUBJECTS = [
    "Ex-Amazon AI engineer & software architect exploring opportunities",
    "Ex-Amazon AI engineer & software architect exploring Miami opportunities",
]


def uncontacted() -> List[str]:
    """Recruiter-lane contacts that still have a live email and were never emailed."""
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    q = "/rest/v1/jobops_leads?lane=eq.recruiter&stage=eq.new&status=neq.rejected&select=company,contact"
    req = urllib.request.Request(url + q, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.load(r)
    out = []
    for row in rows:
        c = row.get("contact") or {}
        if (c.get("email") or "").strip():
            out.append(f"{c.get('name') or '?'} ({row.get('company') or '?'})")
    return sorted(out)


def sent_recently(days: int) -> int:
    g = Gmail.from_env()
    total = 0
    for subj in SUBJECTS:
        query = f'in:sent subject:"{subj}" newer_than:{days}d'
        total += len(g.search(query, max_results=50))
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale-days", type=int, default=3,
                    help="alert if no outreach email in this many days")
    a = ap.parse_args()

    waiting = uncontacted()
    recent = sent_recently(a.stale_days)

    print(f"recruiters still uncontacted (with a live email): {len(waiting)}")
    print(f"outreach emails sent in the last {a.stale_days} days: {recent}")

    if not waiting:
        print("OK: nobody left to contact.")
        return 0
    if recent > 0:
        print("OK: outreach is moving.")
        return 0

    print("")
    print("=" * 70)
    print(f"STALLED: {len(waiting)} recruiters waiting and NOTHING sent in {a.stale_days} days.")
    print("The local batch runner only works while the Claude app is open on the Mac.")
    print("Fix: open the Claude app on a weekday with Chrome logged into Gmail /u/3/")
    print("and LinkedIn. The queued batch fires within the hour on its own.")
    print("=" * 70)
    for w in waiting[:15]:
        print("  waiting:", w)
    if len(waiting) > 15:
        print(f"  ...and {len(waiting) - 15} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
