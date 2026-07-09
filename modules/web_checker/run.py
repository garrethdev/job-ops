"""web-checker orchestration: fetch -> build records -> score -> dedupe/store -> digest.

Returns a RunResult so __main__ can set exit codes and the workflow can decide
whether to open a digest issue or a failure issue.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from core import digest as digest_mod
from core import store as store_mod
from core.config import STORE_PATH
from core.schema import new_record
from core.scoring import apply_scores
from modules.web_checker.adapters import get_adapter
from modules.web_checker.config_loader import enabled_adapters, load_sources


@dataclass
class RunResult:
    fetched: int = 0
    added: int = 0
    merged: int = 0
    errors: List[str] = field(default_factory=list)
    digest_title: str = ""
    digest_body: str = ""
    records: List[Dict[str, Any]] = field(default_factory=list)


def _build_records(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    fetch = get_adapter(entry["adapter"])
    records: List[Dict[str, Any]] = []
    for p in fetch(entry):
        if not p.get("title") or not p.get("company"):
            continue
        rec = new_record(
            title=p["title"], company=p["company"], url=p.get("url", ""),
            source=p.get("source", "board"), location=p.get("location", ""),
            comp=p.get("comp", ""), posted=p.get("posted", ""),
            source_detail=p.get("source_detail", entry.get("name", "")),
        )
        rec["snippet"] = p.get("snippet", "")  # used by scoring, kept in record
        records.append(rec)
    return records


def run(
    dry_run: bool = False,
    use_llm: bool = False,
    store_path: Path = STORE_PATH,
    digest_out: Path | None = None,
) -> RunResult:
    cfg = load_sources()
    entries = enabled_adapters(cfg)
    result = RunResult()

    collected: List[Dict[str, Any]] = []
    for entry in entries:
        try:
            recs = _build_records(entry)
            collected.extend(recs)
            print(f"[{entry['name']}] fetched {len(recs)}")
        except Exception as e:  # one source failing must not sink the run
            msg = f"{entry.get('name', entry.get('adapter'))}: {type(e).__name__}: {e}"
            result.errors.append(msg)
            print(f"[ERROR] {msg}")

    if entries and len(result.errors) == len(entries):
        # every configured source failed -> hard failure (workflow opens an issue)
        raise RuntimeError("all web-checker sources failed: " + " | ".join(result.errors))

    result.fetched = len(collected)
    apply_scores(collected, use_llm=use_llm)
    result.records = collected

    if dry_run:
        d = digest_mod.render(collected)
    else:
        up = store_mod.upsert(collected, path=store_path)
        result.added, result.merged = up.added, up.merged
        # Digest surfaces only records actually added this run, not re-sightings,
        # so a daily cron doesn't re-email the same jobs every day.
        full = store_mod.load(store_path)
        d = digest_mod.render(full, only_new_ids=up.added_ids)

    result.digest_title, result.digest_body = d["title"], d["body"]
    if digest_out is not None:
        digest_out.parent.mkdir(parents=True, exist_ok=True)
        digest_out.write_text(result.digest_body, encoding="utf-8")
    return result
