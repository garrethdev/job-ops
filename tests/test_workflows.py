"""Regression guards for the Actions workflows.

- web-check and email-scan both commit the store back to the repo; they must
  share ONE concurrency group so GitHub serializes them (no push clobbering).
- enrich's commit step must use the same fetch/reset retry loop and be
  continue-on-error, matching the other store writers.
- email-scan's header must not claim it is blocked: its cron is live.
"""
import tests._bootstrap  # noqa: F401

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _read(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _concurrency_group(name):
    m = re.search(r"^concurrency:\n(?:\s*#.*\n)*\s*group:\s*(\S+)", _read(name), re.M)
    assert m, f"{name}: no concurrency group found"
    return m.group(1)


def test_store_writers_share_one_concurrency_group():
    assert (
        _concurrency_group("web-check.yml")
        == _concurrency_group("email-scan.yml")
        == "store-writers"
    ), "web-check and email-scan must serialize on the same group"


def test_enrich_commit_step_matches_other_store_writers():
    text = _read("enrich.yml")
    assert "continue-on-error: true" in text, "commit step must not fail the run"
    assert "git fetch origin" in text and "git reset --hard" in text, \
        "fetch/reset retry pattern missing"
    assert "for i in 1 2 3 4 5" in text, "push retry loop missing"


def test_email_scan_header_reflects_live_cron():
    text = _read("email-scan.yml")
    header = text.split("\non:", 1)[0]
    assert "BLOCKED" not in header, "stale header: email-scan runs daily"
    assert re.search(r'^\s*- cron: "30 11 \* \* \*"', text, re.M), \
        "daily schedule must be live (not commented out)"


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
