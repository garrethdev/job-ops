import os
import tempfile
from pathlib import Path

import tests._bootstrap  # noqa: F401

from core import schema, store
import modules.web_checker.run as run
from modules.web_checker.company import _profile_to_fields


def _lead(title, company, fit, status="new", lane="gtm-engineer"):
    r = schema.new_record(title=title, company=company, source="board")
    r["fit_score"] = fit
    r["lane"] = lane
    r["status"] = status
    return r


# --- company gate ----------------------------------------------------------

def test_company_gate_rejects_flagged():
    r = _lead("GTM Engineer", "Acme", 8)
    r["_company_reject"] = "staffing/recruiting agency (company research)"
    assert run._apply_company_gate([r]) == 1
    assert r["status"] == "rejected" and r["fit_score"] == 1
    assert any("staffing" in f for f in r["red_flags"])


def test_research_attaches_fields_and_flags(monkeypatch=None):
    r1 = schema.new_record(title="GTM Engineer", company="Acme AI", source="board")
    # neutral name the name-gate can't catch; only the research flags it staffing
    r2 = schema.new_record(title="Solutions Architect", company="Pinnacle Group", source="board")
    r3 = schema.new_record(title="Backend Engineer", company="RealCo", source="board")  # off-lane -> skipped
    profiles = {
        "acme ai": {"company_summary": "AI sales tools", "company_remote": "remote",
                    "company_hq": "NYC", "is_staffing": False, "researched": True},
        "pinnacle group": {"company_summary": "we place engineers", "company_remote": "unknown",
                           "company_hq": "", "is_staffing": True, "researched": True},
    }
    orig_r, orig_c = run.research_company, run.load_cache
    run.load_cache = lambda: {}
    run.research_company = lambda name, url="", cache=None: profiles.get(
        schema.normalize_company(name), {"researched": False})
    try:
        run._research_companies([r1, r2, r3])
    finally:
        run.research_company, run.load_cache = orig_r, orig_c
    assert r1["company_summary"] == "AI sales tools" and r1["company_remote"] == "remote"
    assert not r1.get("_company_reject")
    assert r2.get("_company_reject") and "staffing" in r2["_company_reject"]
    assert not r3.get("company_summary")  # off-lane role never researched


def test_onsite_company_is_flagged(monkeypatch=None):
    r = schema.new_record(title="AI Consultant", company="OnsiteCo", source="board")
    orig_r, orig_c = run.research_company, run.load_cache
    run.load_cache = lambda: {}
    run.research_company = lambda name, url="", cache=None: {
        "company_summary": "consultancy", "company_remote": "onsite",
        "company_hq": "Dallas", "is_staffing": False, "researched": True}
    try:
        run._research_companies([r])
    finally:
        run.research_company, run.load_cache = orig_r, orig_c
    assert r.get("_company_reject") and "on-site" in r["_company_reject"]


# --- daily cap + backlog ---------------------------------------------------

def _tmp_store(recs):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    p = Path(path)
    store.save(recs, p)
    return p


def test_daily_cap_defers_extras():
    recs = [_lead(f"GTM Engineer {i}", f"Co{i}", 7 + (i % 3)) for i in range(7)]
    p = _tmp_store(recs)
    try:
        added = [r["id"] for r in recs]
        surfaced, deferred_now, promoted = run._enforce_daily_cap(p, added, cap=5, threshold=7)
        assert len(surfaced) == 5 and deferred_now == 2 and promoted == 0
        live = [r for r in store.load(p) if r["status"] == "new"]
        assert len(live) == 5
    finally:
        p.unlink()


def test_daily_cap_promotes_backlog_on_quiet_day():
    today = [_lead("GTM Engineer A", "CoA", 9), _lead("GTM Engineer B", "CoB", 8)]  # 2 new
    backlog = [_lead(f"Old Arch {i}", f"Old{i}", 7, status="deferred", lane="software-architect")
               for i in range(4)]  # 4 waiting
    p = _tmp_store(today + backlog)
    try:
        added = [r["id"] for r in today]
        surfaced, deferred_now, promoted = run._enforce_daily_cap(p, added, cap=5, threshold=7)
        assert deferred_now == 0 and promoted == 3  # 2 new + 3 promoted = cap 5
        live = [r for r in store.load(p) if r["status"] == "new"]
        assert len(live) == 5
    finally:
        p.unlink()


# --- profile parsing -------------------------------------------------------

def test_profile_to_fields_normalizes_remote():
    f = _profile_to_fields("https://x.com", {"summary": "does X", "remote_policy": "REMOTE",
                                             "hq": "SF", "is_staffing_agency": True})
    assert f["company_remote"] == "remote" and f["is_staffing"] is True and f["researched"]
    bad = _profile_to_fields("https://x.com", {"remote_policy": "flexible"})  # not an enum value
    assert bad["company_remote"] == "unknown"


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
