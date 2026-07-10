import tests._bootstrap  # noqa: F401

import tempfile
from pathlib import Path

from core import schema, store


def _tmp_store():
    d = tempfile.mkdtemp()
    return Path(d) / "opportunities.jsonl"


def _rec(company, title, url="", source="board"):
    return schema.new_record(title=title, company=company, url=url, source=source)


def test_upsert_adds_then_dedupes():
    path = _tmp_store()
    r = store.upsert([_rec("Acme", "Engineer", "https://acme.com/1")], path)
    assert (r.added, r.merged) == (1, 0)
    assert len(r.added_ids) == 1
    # same job again -> merged, not added, and reports zero new ids
    r = store.upsert([_rec("Acme Inc", "Engineer", "https://acme.com/1?x=1")], path)
    assert (r.added, r.merged) == (0, 1)
    assert r.added_ids == []
    assert len(store.load(path)) == 1


def test_within_batch_dedup():
    path = _tmp_store()
    batch = [
        _rec("Acme", "Engineer", "https://acme.com/1"),
        _rec("Acme", "Engineer", "https://acme.com/1"),  # dup in same batch
        _rec("Globex", "Designer", "https://globex.com/2"),
    ]
    r = store.upsert(batch, path)
    assert r.added == 2 and r.merged == 1
    assert len(store.load(path)) == 2


def test_atomic_write_roundtrip_and_sorted_keys():
    path = _tmp_store()
    store.save([_rec("Acme", "Engineer")], path)
    text = path.read_text()
    # keys are sorted for stable diffs
    assert text.index('"company"') < text.index('"title"')
    assert len(store.load(path)) == 1


def test_save_rejects_invalid_record():
    path = _tmp_store()
    bad = _rec("Acme", "Engineer")
    bad["status"] = "bogus"
    try:
        store.save([bad], path)
        assert False, "should have raised SchemaError"
    except schema.SchemaError:
        pass
    assert not path.exists(), "invalid batch must not create/overwrite the store"


def test_get_record():
    path = _tmp_store()
    store.upsert([_rec("Acme", "Engineer", "https://acme.com/1")], path)
    rid = store.load(path)[0]["id"]
    assert store.get_record(rid, path)["company"] == "Acme"
    assert store.get_record("missing", path) is None


def test_update_record_persists_and_returns():
    path = _tmp_store()
    store.upsert([_rec("Acme", "Engineer")], path)
    rid = store.load(path)[0]["id"]
    updated = store.update_record(rid, {"notes": "reached out"}, path)
    assert updated["notes"] == "reached out"
    assert store.load(path)[0]["notes"] == "reached out"  # persisted


def test_update_missing_returns_none_and_leaves_file_unchanged():
    path = _tmp_store()
    store.upsert([_rec("Acme", "Engineer")], path)
    before = path.read_bytes()
    assert store.update_record("nope", {"notes": "x"}, path) is None
    assert path.read_bytes() == before


def test_invalid_update_raises_and_file_byte_unchanged():
    path = _tmp_store()
    store.upsert([_rec("Acme", "Engineer")], path)  # lane is "" (status new)
    rid = store.load(path)[0]["id"]
    before = path.read_bytes()
    try:
        store.update_record(rid, {"status": "enriched"}, path)  # lane still empty -> invalid
        assert False, "should have raised SchemaError"
    except schema.SchemaError:
        pass
    assert path.read_bytes() == before  # atomic: nothing written


def test_delete_record():
    path = _tmp_store()
    store.upsert([_rec("Acme", "Engineer"), _rec("Globex", "Designer")], path)
    rid = store.load(path)[0]["id"]
    assert store.delete_record(rid, path) is True
    assert all(r["id"] != rid for r in store.load(path))
    before = path.read_bytes()
    assert store.delete_record("missing", path) is False
    assert path.read_bytes() == before


def test_load_skips_blank_and_flags_malformed_lineno():
    path = _tmp_store()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n{"id":"a"}\n\nNOT JSON\n')
    try:
        store.load(path)
        assert False, "should raise ValueError for malformed line"
    except ValueError as e:
        assert ":4" in str(e)  # reports path:lineno


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
