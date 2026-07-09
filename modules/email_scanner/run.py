"""email-scanner orchestration: Gmail allowlist -> route -> classify -> store -> digest.

Routing (GAMEPLAN §3, allowlist.yaml):
  - exclude senders            -> never fetched (kept out of the query)
  - jobs-noreply status subj   -> STATUS UPDATE on an existing record, never new
  - scan senders / route label -> opportunity: parse -> score -> upsert

Imports `core` only. Subject-only extraction for now; the store dedupes overlap
with the web sources.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from core import digest as digest_mod
from core import store as store_mod
from core.config import STORE_PATH
from core.gmail import Gmail
from core.schema import new_record, normalize_company
from core.scoring import apply_scores
from core.yaml_loader import load_yaml
from modules.email_scanner import parse

ALLOWLIST = Path(__file__).resolve().parent / "allowlist.yaml"


@dataclass
class RunResult:
    scanned: int = 0
    opportunities: int = 0
    status_updates: int = 0
    added: int = 0
    merged: int = 0
    digest_title: str = ""
    digest_body: str = ""


def _build_query(allow: Dict[str, Any], days: int) -> str:
    senders = allow.get("senders", {}) or {}
    scan = senders.get("scan", []) or []
    exclude = senders.get("exclude", []) or []
    label = ((allow.get("labels", {}) or {}).get("route_in", {}) or {}).get("name", "")
    parts = [f"from:{s}" for s in scan]
    if label:
        parts.append(f'label:"{label}"')
    q = "(" + " OR ".join(parts) + ")"
    for e in exclude:
        q += f" -from:{e}"
    q += f" newer_than:{days}d"
    return q


def _apply_status_update(company: str, subject: str, store_path: Path) -> bool:
    """Mark an existing record for `company` as applied. Never creates a record."""
    if not company:
        return False
    target = normalize_company(company)
    for r in store_mod.load(store_path):
        if normalize_company(r.get("company", "")) == target:
            note = (r.get("notes", "") + f"\n[status] {subject.strip()}").strip()
            store_mod.update_record(r["id"], {"status": "applied", "notes": note}, store_path)
            return True
    return False


def run(days: int = 3, use_llm: bool = False, dry_run: bool = False,
        store_path: Path = STORE_PATH, digest_out: Path | None = None) -> RunResult:
    allow = load_yaml(ALLOWLIST)
    status_subjects = (allow.get("routing_rules", {}) or {}).get("status_update_subjects", []) or []

    gm = Gmail.from_env()
    query = _build_query(allow, days)
    ids = gm.search(query, max_results=200)

    result = RunResult(scanned=len(ids))
    opportunities: List[Dict[str, Any]] = []
    for mid in ids:
        msg = gm.message(mid)
        sender = parse.sender_email(msg["from"])
        subject = msg["subject"]

        if parse.is_status_update(sender, subject, status_subjects):
            company = parse.status_company(subject)
            if not dry_run and _apply_status_update(company, subject, store_path):
                result.status_updates += 1
            continue

        p = parse.parse_opportunity(subject)
        if not p:
            continue
        rec = new_record(title=p["title"], company=p["company"], comp=p.get("comp", ""),
                         source="email", source_detail=sender)
        rec["snippet"] = msg.get("snippet", "")
        opportunities.append(rec)

    result.opportunities = len(opportunities)
    apply_scores(opportunities, use_llm=use_llm)

    if dry_run:
        d = digest_mod.render(opportunities)
    else:
        up = store_mod.upsert(opportunities, path=store_path)
        result.added, result.merged = up.added, up.merged
        full = store_mod.load(store_path)
        d = digest_mod.render(full, only_new_ids=up.added_ids)

    result.digest_title, result.digest_body = d["title"], d["body"]
    if digest_out is not None:
        digest_out.parent.mkdir(parents=True, exist_ok=True)
        digest_out.write_text(result.digest_body, encoding="utf-8")
    return result
