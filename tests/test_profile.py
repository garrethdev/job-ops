import tests._bootstrap  # noqa: F401

import tempfile
from pathlib import Path

from core import profile


def _profiles_dir():
    d = Path(tempfile.mkdtemp())
    (d / "software-architect.md").write_text(
        "# Profile\n\n"
        "## Match keywords\n"
        "software architect, staff engineer / principal engineer\n"
        "- distributed systems\n\n"
        "## Boost keywords\n"
        "remote, contract\n\n"
        "## Deal-breakers\n"
        "on-site only\n\n"
        "## Comp floor\nTBD\n"
    )
    return d


def test_load_profile_text_unknown_lane_raises():
    try:
        profile.load_profile_text("not-a-lane")
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "unknown lane" in str(e)


def test_valid_lane_absent_file_returns_empty():
    d = Path(tempfile.mkdtemp())  # empty dir
    assert profile.load_profile_text("software-architect", d) == ""


def test_keywords_under_parses_commas_slashes_bullets():
    d = _profiles_dir()
    kw = profile.load_keywords("software-architect", d)
    for expected in ["software architect", "staff engineer", "principal engineer", "distributed systems"]:
        assert expected in kw["match"], f"missing {expected!r} in {kw['match']}"
    assert all(k == k.lower() for k in kw["match"])  # lowercased


def test_heading_boundaries_and_absent_heading():
    d = _profiles_dir()
    kw = profile.load_keywords("software-architect", d)
    # boost stops before Deal-breakers; deal-breakers captured; comp-floor text not leaking in
    assert "remote" in kw["boost"] and "on-site only" not in kw["boost"]
    assert "on-site only" in kw["deal_breakers"]
    assert "tbd" not in kw["match"]


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))