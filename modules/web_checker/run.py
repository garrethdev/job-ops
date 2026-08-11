"""web-checker orchestration: fetch -> build records -> score -> dedupe/store -> digest.

Returns a RunResult so __main__ can set exit codes and the workflow can decide
whether to open a digest issue or a failure issue.
"""
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from core import digest as digest_mod
from core import store as store_mod
from core.config import DAILY_NEW_CAP, DEFAULT_FIT_THRESHOLD, STORE_PATH
from core.schema import new_record, normalize_company
from core.scoring import apply_scores, score_heuristic
from core.vetting import junk_reason
from modules.web_checker.adapters import get_adapter
from modules.web_checker.company import load_cache, research_company
from modules.web_checker.config_loader import enabled_adapters, load_sources
from modules.web_checker.detail import fetch_description
from modules.web_checker.resolve import resolve_posting

# Cheap title-heuristic bar a role must clear before we spend a page fetch on it.
# (Keeps page-before-score bounded: obviously off-lane titles never get fetched.)
PRESCORE_MIN = 4
_MIN_REAL_DESC = 200  # a snippet this long already IS the real description (API boards)
_PAGE_FETCH_WORKERS = 8


def _needs_page(r: Dict[str, Any]) -> bool:
    """A role worth spending a page fetch on before scoring: not already rejected,
    not an artifact, no real description yet, and its title carries lane signal."""
    return (
        r.get("status") != "rejected"
        and not junk_reason(r)
        and len((r.get("snippet") or "").strip()) < _MIN_REAL_DESC
        and score_heuristic(r)["fit_score"] >= PRESCORE_MIN
    )


def _research_companies(records: List[Dict[str, Any]]) -> int:
    """Research each unique real company once (Firecrawl, cached) and attach its
    summary / remote policy / HQ to every one of its roles. Off-lane/artifact/
    staffing-by-name roles are skipped (no spend). A company the research finds to
    be a staffing agency, or on-site only, is flagged for outright rejection.
    Returns how many companies were newly researched (cache misses)."""
    cache = load_cache()
    by_company: Dict[str, Dict[str, Any]] = {}
    n_new = 0
    for r in records:
        if junk_reason(r):  # already junk (off-lane/artifact/staffing name) -> no research
            continue
        key = normalize_company(r.get("company", ""))
        if not key:
            continue
        if key not in by_company:
            was_cached = key in cache
            prof = research_company(r.get("company", ""), r.get("url", ""), cache=cache)
            by_company[key] = prof
            if not was_cached and prof.get("researched"):
                n_new += 1
        prof = by_company[key]
        for f in ("company_summary", "company_remote", "company_hq"):
            if prof.get(f):
                r[f] = prof[f]
        if prof.get("is_staffing"):
            r["_company_reject"] = "staffing/recruiting agency (company research)"
        elif prof.get("company_remote") == "onsite":
            r["_company_reject"] = "company is on-site only (remote/hybrid required)"
    return n_new


def _apply_company_gate(records: List[Dict[str, Any]]) -> int:
    """Reject roles their company research disqualified (staffing / on-site-only),
    before any scoring spend. Returns how many were rejected."""
    n = 0
    for r in records:
        reason = r.pop("_company_reject", None)
        if reason:
            r["fit_score"] = 1
            r["fit_rationale"] = "company gate: " + reason
            r["red_flags"] = list(r.get("red_flags") or []) + [reason]
            r["status"] = "rejected"
            n += 1
    return n


def _prepare_for_scoring(records: List[Dict[str, Any]]) -> int:
    """Fetch the REAL job page BEFORE scoring, so the accept/reject decision is
    made on the actual description (remote/on-site, seniority, comp, true lane) —
    not just the title. Bounded to keep cost sane: skip junk, skip roles that
    already carry a real description (RemoteOK/WWR/HN/email), and skip titles with
    no lane signal at all. For a candidate with no link, resolve one first.
    Page fetches run in parallel. Returns how many pages were fetched."""
    candidates = [r for r in records if _needs_page(r)]

    def enrich(r: Dict[str, Any]) -> None:
        if not r.get("url"):
            url, desc = resolve_posting(r.get("title", ""), r.get("company", ""))
            if url:
                r["url"] = url
                if desc and not r.get("snippet"):
                    r["snippet"] = desc
        if r.get("url"):
            full = fetch_description(r["url"])
            if full:
                r["snippet"] = full

    if candidates:
        with concurrent.futures.ThreadPoolExecutor(max_workers=_PAGE_FETCH_WORKERS) as ex:
            list(ex.map(enrich, candidates))
    return len(candidates)


def _strip_transient(records: List[Dict[str, Any]]) -> None:
    for r in records:
        r.pop("fetch_detail", None)
        r.pop("ignore_location", None)
        r.pop("_company_reject", None)


def _enforce_daily_cap(store_path: Path, added_ids: List[str], cap: int, threshold: int):
    """Hold the day's NEW surfaced leads to <= cap. Among leads added this run that
    cleared the bar, keep the top `cap` by fit and defer the rest. If fewer than
    `cap` were added today, promote the highest-fit 'deferred' backlog leads to
    fill the day (so a strong lead is never lost, only delayed).
    Returns (surfaced_ids, deferred_now, promoted)."""
    records = store_mod.load(store_path)
    added = set(added_ids)
    rank = lambda r: (int(r.get("fit_score", 0)), r.get("first_seen", ""))
    new_today = sorted(
        (r for r in records if r.get("id") in added
         and r.get("status") == "new" and int(r.get("fit_score", 0)) >= threshold),
        key=rank, reverse=True,
    )
    surfaced = []
    deferred_now = 0
    for i, r in enumerate(new_today):
        if i < cap:
            surfaced.append(r["id"])
        else:
            r["status"] = "deferred"
            deferred_now += 1
    promoted = 0
    slots = cap - len(surfaced)
    if slots > 0:
        backlog = sorted(
            (r for r in records if r.get("status") == "deferred" and r.get("id") not in added),
            key=rank, reverse=True,
        )
        for r in backlog[:slots]:
            r["status"] = "new"
            surfaced.append(r["id"])
            promoted += 1
    store_mod.save(records, store_path)
    return surfaced, deferred_now, promoted


def _finalize_status(records: List[Dict[str, Any]], threshold: int) -> int:
    """Reject any sub-threshold lead at the source, so it never reaches the
    board (the dashboard shows every non-rejected record regardless of score).
    Only touches leads still at 'new' - a user-advanced status is never changed.
    Returns how many were rejected."""
    n = 0
    for r in records:
        if r.get("status") == "new" and int(r.get("fit_score", 0)) < threshold:
            r["status"] = "rejected"
            n += 1
    return n


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
            snippet=p.get("snippet", ""),  # scoring signal, now a schema field
        )
        # Transient per-source scoring/enrichment hints (stripped before store).
        if entry.get("ignore_location"):
            rec["ignore_location"] = True
        if entry.get("fetch_detail"):
            rec["fetch_detail"] = True
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
    researched = _research_companies(collected)       # Firecrawl company profiles (cached)
    print(f"researched {researched} new companies")
    gated = _apply_company_gate(collected)            # staffing / on-site-only -> rejected
    print(f"company gate: {gated} rejected (staffing / on-site)")
    fetched_pages = _prepare_for_scoring(collected)   # open the real page BEFORE scoring
    print(f"fetched {fetched_pages} job pages for page-based scoring")
    apply_scores(collected, use_llm=use_llm)          # scores on the real description now
    rejected = _finalize_status(collected, DEFAULT_FIT_THRESHOLD)  # sub-threshold -> rejected
    print(f"vetting: {rejected}/{len(collected)} rejected below fit {DEFAULT_FIT_THRESHOLD}")
    _strip_transient(collected)
    result.records = collected

    if dry_run:
        d = digest_mod.render(collected)
    else:
        up = store_mod.upsert(collected, path=store_path)
        result.added, result.merged = up.added, up.merged
        # Cap the day's NEW surfaced leads (extras held as a backlog, promoted
        # later). Digest surfaces exactly what went live today, not re-sightings.
        surfaced, deferred_now, promoted = _enforce_daily_cap(
            store_path, up.added_ids, DAILY_NEW_CAP, DEFAULT_FIT_THRESHOLD)
        print(f"daily cap {DAILY_NEW_CAP}: surfaced {len(surfaced)}, "
              f"deferred {deferred_now}, promoted {promoted} from backlog")
        full = store_mod.load(store_path)
        d = digest_mod.render(full, only_new_ids=surfaced)

    result.digest_title, result.digest_body = d["title"], d["body"]
    if digest_out is not None:
        digest_out.parent.mkdir(parents=True, exist_ok=True)
        digest_out.write_text(result.digest_body, encoding="utf-8")
    return result
