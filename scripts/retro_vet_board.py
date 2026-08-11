#!/usr/bin/env python3
"""Apply the current vetting rules to leads already on the Supabase board.

Runs the SAME tested core.vetting.junk_reason over every non-rejected lead and
rejects the junk (off-lane roles, scraping artifacts, placeholders) so the board
matches what the pipeline would now let through. Never touches a lead the user
has engaged with (warm, staged, noted, or contact revealed).

  python -m scripts.retro_vet_board            # dry run: print what would go
  python -m scripts.retro_vet_board --apply    # actually reject them
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core.config  # noqa: E402  (loads .env)
from core.vetting import junk_reason  # noqa: E402

TABLE = "jobops_leads"


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
    """A lead the user has engaged with is never auto-rejected."""
    if r.get("warm"):
        return True
    if (r.get("stage") or "new") != "new":
        return True
    if (r.get("notes") or "").strip():
        return True
    c = r.get("contact") or {}
    return bool((c.get("linkedin") or "").strip() or (c.get("email") or "").strip())


def load_board() -> list:
    out, page = [], 0
    cols = "id,title,company,location,comp,fit_score,snippet,warm,stage,notes,contact,status"
    while True:
        rows = _req("GET", f"/rest/v1/{TABLE}?select={cols}&status=neq.rejected&limit=1000&offset={page*1000}")
        out.extend(rows)
        if len(rows) < 1000:
            break
        page += 1
    return out


def main() -> int:
    apply = "--apply" in sys.argv
    board = load_board()
    victims, reasons = [], Counter()
    for r in board:
        reason = junk_reason(r)
        if reason and not _touched(r):
            victims.append((r, reason))
            reasons[reason.split(" (")[0].split(":")[0][:40]] += 1

    print(f"board(non-rejected)={len(board)}  would_reject={len(victims)}  keep={len(board)-len(victims)}")
    print("\nby reason:")
    for reason, n in reasons.most_common():
        print(f"  {n:3d}  {reason}")
    print("\nsample (first 40):")
    for r, reason in victims[:40]:
        print(f"  [{r.get('fit_score')}] {r.get('title')!r} @ {r.get('company')!r}  -> {reason}")

    if not apply:
        print("\nDRY RUN. Re-run with --apply to reject these.")
        return 0

    ids = [r["id"] for r, _ in victims]
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        id_list = ",".join(f'"{x}"' for x in chunk)
        _req("PATCH", f"/rest/v1/{TABLE}?id=in.({id_list})",
             {"status": "rejected", "fit_rationale": "[retro vetting purge: off-lane/artifact]"})
        print(f"  rejected {i + len(chunk)}/{len(ids)}")
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
