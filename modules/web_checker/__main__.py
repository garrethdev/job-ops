"""CLI: python -m modules.web_checker [--dry-run] [--llm] [--digest-out PATH]

--dry-run : fetch + score + render digest, but DO NOT write the store.
--llm     : use Claude for classification (requires ANTHROPIC_API_KEY; billed).
            Default is the free deterministic heuristic scorer.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from core.config import STORE_PATH
from modules.web_checker.run import run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="modules.web_checker")
    ap.add_argument("--dry-run", action="store_true", help="don't write the store")
    ap.add_argument("--llm", action="store_true", help="use Claude scoring (billed)")
    ap.add_argument("--store", default=str(STORE_PATH), help="store path override")
    ap.add_argument("--digest-out", default="", help="write digest markdown here")
    args = ap.parse_args(argv)

    digest_out = Path(args.digest_out) if args.digest_out else None
    try:
        res = run(
            dry_run=args.dry_run,
            use_llm=args.llm,
            store_path=Path(args.store),
            digest_out=digest_out,
        )
    except Exception as e:
        print(f"web-checker FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print("\n" + "=" * 60)
    print(f"fetched={res.fetched} added={res.added} merged={res.merged} "
          f"errors={len(res.errors)} dry_run={args.dry_run}")
    print(f"digest: {res.digest_title}")
    print("=" * 60)
    print(res.digest_body)

    # Expose results to the GitHub Actions step so the workflow can decide
    # whether to open a digest issue and commit the updated store.
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"added={res.added}\n")
            fh.write(f"merged={res.merged}\n")
            fh.write(f"errors={len(res.errors)}\n")
            fh.write(f"digest_title={res.digest_title}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
