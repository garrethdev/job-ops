"""CLI: python -m modules.email_scanner [--days N] [--dry-run] [--llm] [--digest-out P]

Requires GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN (see
docs/GMAIL_OAUTH.md). --dry-run fetches + parses + scores but does NOT write the
store. Default scorer is the free heuristic; --llm uses the configured LLM (billed).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from core.config import STORE_PATH
from core.gmail import GmailError
from modules.email_scanner.run import run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="modules.email_scanner")
    ap.add_argument("--days", type=int, default=3, help="scan mail newer than N days")
    ap.add_argument("--dry-run", action="store_true", help="don't write the store")
    ap.add_argument("--llm", action="store_true", help="use LLM scoring (billed)")
    ap.add_argument("--store", default=str(STORE_PATH))
    ap.add_argument("--digest-out", default="")
    args = ap.parse_args(argv)

    for v in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        if not os.environ.get(v):
            print(f"email-scanner BLOCKED: missing {v} (see docs/GMAIL_OAUTH.md)", file=sys.stderr)
            return 2

    digest_out = Path(args.digest_out) if args.digest_out else None
    try:
        res = run(days=args.days, use_llm=args.llm, dry_run=args.dry_run,
                  store_path=Path(args.store), digest_out=digest_out)
    except GmailError as e:
        print(f"email-scanner FAILED (Gmail): {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"email-scanner FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print("=" * 60)
    print(f"scanned={res.scanned} opportunities={res.opportunities} "
          f"status_updates={res.status_updates} added={res.added} merged={res.merged} "
          f"dry_run={args.dry_run}")
    print(f"digest: {res.digest_title}")
    print("=" * 60)
    print(res.digest_body)

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"added={res.added}\n")
            fh.write(f"digest_title={res.digest_title}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
