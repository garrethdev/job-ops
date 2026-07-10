import tests._bootstrap  # noqa: F401

from core import digest, schema


def _scored(company, title, lane, fit, **extra):
    r = schema.new_record(title=title, company=company, source="board")
    r["lane"], r["fit_score"] = lane, fit
    r.update(extra)
    return r


def test_below_threshold_excluded_and_title_format():
    recs = [_scored("A", "Architect", "software-architect", 8),
            _scored("B", "Junior", "software-architect", 3)]
    d = digest.render(recs, threshold=6)
    assert d["title"] == "job-ops digest: 1 new"
    assert "(from 2 scanned)" in d["body"]
    assert "Architect" in d["body"] and "Junior" not in d["body"]


def test_only_new_ids_restricts_pool():
    a = _scored("A", "Architect", "software-architect", 8)
    b = _scored("B", "Consultant", "ai-consultant", 8)
    d = digest.render([a, b], threshold=6, only_new_ids=[a["id"]])
    assert "Architect" in d["body"] and "Consultant" not in d["body"]


def test_lanes_render_in_config_order_and_empty_lanes_skipped():
    from core.config import LANES
    recs = [_scored("A", "Arch", "software-architect", 8),
            _scored("C", "Cons", "ai-consultant", 8)]
    body = digest.render(recs, threshold=6)["body"]
    # both present, and software-architect header appears before ai-consultant per LANES order
    assert LANES.index("software-architect") < LANES.index("ai-consultant")
    assert body.index("## software-architect") < body.index("## ai-consultant")


def test_sub_lines_rendered_for_rich_record():
    r = _scored("Acme", "Architect", "software-architect", 9,
                url="https://acme.com/j", fit_rationale="great fit",
                red_flags=["on-site only"],
                contact={"name": "Jo", "title": "CTO", "email": "jo@acme.com", "linkedin": ""})
    body = digest.render([r], threshold=6)["body"]
    assert "https://acme.com/j" in body
    assert "_great fit_" in body
    assert "⚠" in body and "on-site only" in body
    assert "↳ contact:" in body and "Jo" in body


def test_sorted_by_fit_desc():
    recs = [_scored("A", "Low", "software-architect", 6),
            _scored("B", "High", "software-architect", 10)]
    body = digest.render(recs, threshold=6)["body"]
    assert body.index("High") < body.index("Low")


def test_no_records_over_threshold_message():
    d = digest.render([_scored("A", "X", "software-architect", 2)], threshold=6)
    assert "No new opportunities cleared the threshold" in d["body"]


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))