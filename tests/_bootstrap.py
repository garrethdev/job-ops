"""Shared bootstrap for running test files directly (python tests/test_x.py).

pytest uses conftest.py; direct execution imports this first.
"""
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_module(namespace):
    """Run every top-level test_* function in `namespace`. Returns exit code."""
    failures = 0
    for name, fn in sorted(namespace.items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok  {name}")
            except Exception:
                failures += 1
                print(f" FAIL {name}")
                traceback.print_exc()
    print(f"{'PASS' if not failures else 'FAIL'}: {failures} failure(s)")
    return 1 if failures else 0
