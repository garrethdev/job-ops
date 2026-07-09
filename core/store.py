"""Opportunities store — JSONL, dedupe on write, atomic rewrite.

The store is the ONLY contract between modules. All access goes through here.

Durability: every mutation validates against the schema first, then rewrites
the whole file to a temp file in the same directory and os.replace()s it into
place. A crash mid-write leaves the previous file intact — a failing module can
never leave a half-written or schema-invalid store.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from core import dedupe
from core.config import STORE_PATH
from core.schema import validate_or_raise


@dataclass
class UpsertResult:
    added: int = 0
    merged: int = 0
    added_ids: List[str] = field(default_factory=list)


def load(path: Path = STORE_PATH) -> List[Dict[str, Any]]:
    """Read all records. Missing file == empty store. Skips blank lines."""
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno} is not valid JSON: {e}") from e
    return out


def _atomic_write(records: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".opps.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save(records: List[Dict[str, Any]], path: Path = STORE_PATH) -> None:
    """Validate every record, then atomically rewrite the store."""
    for r in records:
        validate_or_raise(r)
    _atomic_write(records, path)


def get_record(record_id: str, path: Path = STORE_PATH) -> Dict[str, Any] | None:
    for r in load(path):
        if r.get("id") == record_id:
            return r
    return None


def update_record(record_id: str, patch: Dict[str, Any], path: Path = STORE_PATH) -> Dict[str, Any] | None:
    """Shallow-merge `patch` into the record with `record_id`, then persist.

    Returns the updated record, or None if not found. Validated before write.
    """
    records = load(path)
    updated = None
    for r in records:
        if r.get("id") == record_id:
            r.update(patch)
            updated = r
            break
    if updated is not None:
        save(records, path)
    return updated


def delete_record(record_id: str, path: Path = STORE_PATH) -> bool:
    records = load(path)
    kept = [r for r in records if r.get("id") != record_id]
    if len(kept) == len(records):
        return False
    save(kept, path)
    return True


def upsert(incoming: List[Dict[str, Any]], path: Path = STORE_PATH) -> UpsertResult:
    """Add new records, merge re-sightings.

    Returns an UpsertResult with counts and the ids actually ADDED this call
    (so the digest can surface only genuinely-new opportunities, not re-sightings).
    Dedupe is evaluated against the current store AND within `incoming` (a single
    batch containing the same job twice collapses to one record).
    """
    records = load(path)
    ct_index, url_index = dedupe.build_index(records)
    res = UpsertResult()
    for rec in incoming:
        validate_or_raise(rec)
        idx = dedupe.find_duplicate(rec, records, ct_index, url_index)
        if idx is None:
            records.append(rec)
            new_idx = len(records) - 1
            ct_index[dedupe.company_title_key(rec)] = new_idx
            uk = dedupe.url_key(rec)
            if uk:
                url_index[uk] = new_idx
            res.added += 1
            res.added_ids.append(rec["id"])
        else:
            records[idx] = dedupe.merge(records[idx], rec)
            res.merged += 1
    save(records, path)
    return res
