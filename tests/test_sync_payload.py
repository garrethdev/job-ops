import tests._bootstrap  # noqa: F401  (path bootstrap for direct runs)

from core import config, schema
from scripts.sync_to_supabase import (
    DASHBOARD_OWNED,
    DISCOVERY_COLS,
    SKIP_STATUS,
    eligible_rows,
    to_row,
)


def _record(**over):
    """A scored record as it looks after a full pipeline pass, plus the
    dashboard-owned columns a row would carry if it round-tripped from Supabase.
    to_row must strip every one of the dashboard fields."""
    r = schema.new_record(
        title="Platform Engineer", company="Foo", url="https://foo.com/j/1",
        source="board", lane="software-architect", snippet="python api platform",
    )
    r.update({
        "fit_score": 8,
        "fit_rationale": "heuristic: strong match",
        "red_flags": ["thin description"],
        "company_summary": "Foo builds APIs",
        "company_remote": "remote",
        "company_hq": "Miami, US",
        # dashboard-owned (status is also local; stage/warm/updated_at only
        # exist on Supabase rows but must be dropped if ever present)
        "status": "enriched",
        "stage": "wip",
        "notes": "spoke to CTO",
        "warm": True,
        "outreached_at": "2026-08-18T12:00:00Z",
        "updated_at": "2026-08-18T12:00:00Z",
    })
    r.update(over)
    return r


def test_payload_contains_discovery_fields_and_identity():
    row = to_row(_record())
    for c in DISCOVERY_COLS:
        assert c in row, f"discovery field missing from payload: {c}"
    # insert-only identity/provenance rides along for brand-new rows
    for c in ("id", "first_seen", "lane", "source"):
        assert c in row
    assert row["company_summary"] == "Foo builds APIs"
    assert row["fit_score"] == 8


def test_payload_never_contains_dashboard_owned_fields():
    row = to_row(_record())
    for c in DASHBOARD_OWNED:
        assert c not in row, f"dashboard-owned field leaked into payload: {c}"


def test_skip_status_keeps_rejected_and_deferred_local():
    assert SKIP_STATUS == {"rejected", "deferred"}
    recs = [_record(), _record(status="rejected"), _record(status="deferred")]
    rows = eligible_rows(recs)
    assert len(rows) == 1


def test_app_owned_lanes_and_sources_validate():
    # lanes/sources the Vercel app writes must pass core schema validation
    for lane in ("recruiter", "yc_gtm", "lookup"):
        assert lane in config.LANES
    for source in ("manual", "recruiter-direct"):
        assert source in config.SOURCES
    r = _record(lane="recruiter", source="manual")
    del r["stage"], r["warm"], r["updated_at"]  # Supabase-only columns
    assert schema.validate(r) == []


def test_empty_lane_allowance_intact():
    # lane may still be "" while status is new / rejected (pre-scoring / junk)
    r = schema.new_record(title="X", company="Y", source="board")
    assert schema.validate(r) == []
    r["status"] = "rejected"
    assert schema.validate(r) == []


def test_appended_lanes_never_win_heuristic_tiebreak():
    # App-owned lanes have no profiles/<lane>.md, so they score 0 hits; they
    # sit AFTER the profile lanes so max() can never pick them on a tie.
    from core import scoring
    r = schema.new_record(title="zzz", company="qqq", source="board")
    out = scoring.score_heuristic(r)
    assert out["lane"] in config.LANES[:4]


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
