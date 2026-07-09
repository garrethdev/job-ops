import tests._bootstrap  # noqa: F401  (path bootstrap for direct runs)

from core import schema


def test_make_id_stable_and_normalized():
    a = schema.make_id("Acme, Inc.", "Senior Backend Engineer")
    b = schema.make_id("acme inc", "senior backend engineer")
    assert a == b, "id must ignore punctuation / legal suffixes / case"


def test_normalize_url_strips_scheme_query_slash():
    assert schema.normalize_url("https://WWW.Example.com/jobs/1/?utm=x#top") == "example.com/jobs/1"


def test_new_record_has_required_fields_and_validates():
    r = schema.new_record(title="Platform Engineer", company="Foo", source="board")
    assert r["schema_version"] == schema.SCHEMA_VERSION
    assert r["status"] == "new"
    assert schema.validate(r) == []


def test_validate_rejects_bad_enums_and_ranges():
    r = schema.new_record(title="X", company="Y", source="board")
    r["source"] = "carrier-pigeon"
    r["fit_score"] = 99
    errs = schema.validate(r)
    assert any("invalid source" in e for e in errs)
    assert any("fit_score" in e for e in errs)


def test_validate_requires_lane_once_past_new():
    r = schema.new_record(title="X", company="Y", source="board")
    r["status"] = "enriched"  # lane still ""
    errs = schema.validate(r)
    assert any("lane must be set" in e for e in errs)


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
