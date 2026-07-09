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


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
