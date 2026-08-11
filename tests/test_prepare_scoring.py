import tests._bootstrap  # noqa: F401

from core import schema
from modules.web_checker.run import _finalize_status, _needs_page


def _rec(title, company="Acme AI", snippet=""):
    r = schema.new_record(title=title, company=company, source="board")
    r["snippet"] = snippet
    return r


def test_thin_on_lane_role_needs_a_page():
    # A plausible lane title with only a thin card -> fetch the real page before scoring.
    assert _needs_page(_rec("GTM Engineer"))
    assert _needs_page(_rec("Senior Software Architect"))


def test_role_with_real_description_is_skipped():
    long_desc = "We are hiring a GTM Engineer. " * 20  # > 200 chars = already the real posting
    assert not _needs_page(_rec("GTM Engineer", snippet=long_desc))


def test_junk_is_skipped():
    assert not _needs_page(_rec("Multiple Roles", company="DuckDuckGo"))
    assert not _needs_page(_rec("GTM Engineer", company="n/a"))


def test_off_lane_title_is_skipped():
    # No lane signal in the title -> don't spend a page fetch on it.
    assert not _needs_page(_rec("Registered Nurse", company="Hospital"))
    assert not _needs_page(_rec("Warehouse Associate", company="Logistics Co"))


def test_finalize_status_rejects_below_threshold():
    strong = _rec("GTM Engineer"); strong["fit_score"] = 8; strong["lane"] = "gtm-engineer"
    weak = _rec("GTM Engineer"); weak["fit_score"] = 6; weak["lane"] = "gtm-engineer"
    junk = _rec("Multiple Roles", company="DuckDuckGo"); junk["fit_score"] = 1
    n = _finalize_status([strong, weak, junk], threshold=7)
    assert n == 2
    assert strong["status"] == "new"
    assert weak["status"] == "rejected" and junk["status"] == "rejected"


def test_finalize_status_never_touches_advanced_leads():
    # A user-advanced lead (applied/queued) is never auto-rejected, even if low.
    r = _rec("GTM Engineer"); r["fit_score"] = 4; r["lane"] = "gtm-engineer"; r["status"] = "applied"
    assert _finalize_status([r], threshold=7) == 0
    assert r["status"] == "applied"


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
