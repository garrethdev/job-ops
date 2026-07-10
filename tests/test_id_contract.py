import tests._bootstrap  # noqa: F401

import json
from pathlib import Path

from core.schema import make_id, normalize_company

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "id_vectors.json"


def test_python_make_id_matches_golden_vectors():
    vectors = json.loads(FIXTURE.read_text())
    for v in vectors:
        assert make_id(v["company"], v["title"]) == v["id"], f"{v['company']!r}/{v['title']!r}"


def test_legal_suffix_variants_collapse():
    assert make_id("Acme Inc", "Engineer") == make_id("acme, inc.", "engineer")
    assert normalize_company("Vercel Inc") == normalize_company("vercel")


def test_fixture_is_the_shared_js_contract():
    # The same file is consumed by vercel-app/test/id-parity.test.js; if the two
    # implementations drift, one side's parity test fails. This asserts the
    # fixture exists and is non-trivial so a deletion can't silently pass both.
    vectors = json.loads(FIXTURE.read_text())
    assert len(vectors) >= 5
    assert any(v["company"] == "OpenAI" for v in vectors)


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))