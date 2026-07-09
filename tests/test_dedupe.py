import tests._bootstrap  # noqa: F401

from core import dedupe, schema


def _rec(company, title, url="", source="board"):
    return schema.new_record(title=title, company=company, url=url, source=source)


def test_company_title_dupe_detected():
    a = _rec("Acme Inc", "Backend Engineer")
    b = _rec("acme, inc.", "backend engineer")
    ct, url = dedupe.build_index([a])
    assert dedupe.find_duplicate(b, [a], ct, url) == 0


def test_url_dupe_detected_across_different_company_strings():
    # Same job, two sources: email alert vs board scrape, differing company text.
    a = _rec("Acme (Remote)", "Engineer", url="https://acme.com/jobs/42")
    b = _rec("Acme Inc", "Sr Engineer", url="https://www.acme.com/jobs/42?ref=x")
    ct, url = dedupe.build_index([a])
    assert dedupe.find_duplicate(b, [a], ct, url) == 0, "URL key must merge cross-source"


def test_distinct_jobs_not_merged():
    a = _rec("Acme", "Backend Engineer", url="https://acme.com/1")
    b = _rec("Globex", "Frontend Engineer", url="https://globex.com/2")
    ct, url = dedupe.build_index([a])
    assert dedupe.find_duplicate(b, [a], ct, url) is None


def test_merge_preserves_progress_and_fills_gaps():
    existing = _rec("Acme", "Engineer", url="")
    existing["fit_score"] = 8
    existing["lane"] = "software-architect"
    existing["status"] = "enriched"
    incoming = _rec("Acme", "Engineer", url="https://acme.com/1", source="email")
    incoming["last_seen"] = "2026-07-09T00:00:00Z"
    merged = dedupe.merge(existing, incoming)
    assert merged["fit_score"] == 8 and merged["status"] == "enriched"
    assert merged["url"] == "https://acme.com/1"  # gap filled
    assert merged["also_seen_via"] == ["email"]


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
