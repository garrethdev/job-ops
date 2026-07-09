"""CLI: python -m modules.dashboard [--port 8787] [--host 127.0.0.1]"""
from __future__ import annotations

import argparse

from modules.dashboard.server import serve


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="modules.dashboard")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args(argv)
    try:
        serve(args.host, args.port)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
