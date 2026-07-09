"""CLI entrypoint for Module C. BLOCKED on APOLLO_API_KEY (see docs/SETUP.md)."""
from __future__ import annotations

import argparse
import os
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="modules.contact_enricher")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-lookups", type=int,
                    default=int(os.environ.get("JOBOPS_APOLLO_MAX_LOOKUPS", "25")))
    ap.parse_args(argv)

    if not os.environ.get("APOLLO_API_KEY"):
        print("contact-enricher is BLOCKED: missing APOLLO_API_KEY. See docs/SETUP.md.",
              file=sys.stderr)
        return 2

    print("contact-enricher: APOLLO_API_KEY present; implementation is pending (M4).",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
