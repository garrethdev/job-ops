import tests._bootstrap  # noqa: F401

from core import schema
from modules.web_checker.run import _needs_page


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


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
