"""CLI entrypoint for Module A. BLOCKED on Gmail OAuth (see docs/SETUP.md).

Fails loudly rather than silently no-op'ing, so the workflow surfaces the blocker
instead of appearing to succeed with zero results.
"""
from __future__ import annotations

import argparse
import os
import sys

REQUIRED = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="modules.email_scanner")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--digest-out", default="")
    ap.parse_args(argv)

    missing = [v for v in REQUIRED if not os.environ.get(v)]
    if missing:
        print(
            "email-scanner is BLOCKED: missing Gmail OAuth secrets: "
            + ", ".join(missing)
            + "\nProvision OAuth for the gmail.com account (garreth.dottin@gmail.com /"
            " garrethdottin@gmail.com), not cryptomiami.net. See docs/SETUP.md.",
            file=sys.stderr,
        )
        return 2

    # Credentials present but the fetch/route/classify implementation is M3 work.
    print("email-scanner: credentials present; implementation is pending (M3).",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
