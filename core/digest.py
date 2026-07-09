"""Build the daily digest: new opportunities by lane, sorted by fit.

One notification channel (a GitHub issue), not three. A module run writes the
digest body to a file; its workflow posts it with `gh issue create`. Keeping the
rendering here (not in the workflow) means it's unit-testable.
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.config import DEFAULT_FIT_THRESHOLD, LANES


def _contact_line(rec: Dict[str, Any]) -> str:
    c = rec.get("contact") or {}
    if c.get("name") or c.get("email"):
        bits = [c.get("name", ""), c.get("title", ""), c.get("email", ""), c.get("linkedin", "")]
        return "  ↳ contact: " + " · ".join(b for b in bits if b)
    return ""


def render(
    records: List[Dict[str, Any]],
    threshold: int = DEFAULT_FIT_THRESHOLD,
    title_prefix: str = "job-ops digest",
    only_new_ids: List[str] | None = None,
) -> Dict[str, str]:
    """Return {title, body}. If only_new_ids is given, restrict to those ids."""
    pool = records
    if only_new_ids is not None:
        idset = set(only_new_ids)
        pool = [r for r in records if r.get("id") in idset]

    surfaced = [r for r in pool if r.get("fit_score", 0) >= threshold]
    surfaced.sort(key=lambda r: r.get("fit_score", 0), reverse=True)

    lines: List[str] = []
    lines.append(f"**{len(surfaced)}** opportunities at/above fit {threshold} "
                 f"(from {len(pool)} scanned).\n")
    for lane in LANES:
        lane_recs = [r for r in surfaced if r.get("lane") == lane]
        if not lane_recs:
            continue
        lines.append(f"## {lane} ({len(lane_recs)})\n")
        for r in lane_recs:
            head = f"- **[{r.get('fit_score')}]** {r.get('title')} — {r.get('company')}"
            loc = r.get("location")
            if loc:
                head += f" · {loc}"
            lines.append(head)
            if r.get("url"):
                lines.append(f"  {r['url']}")
            if r.get("fit_rationale"):
                lines.append(f"  _{r['fit_rationale']}_")
            if r.get("red_flags"):
                lines.append("  ⚠ " + "; ".join(r["red_flags"]))
            cl = _contact_line(r)
            if cl:
                lines.append(cl)
        lines.append("")

    if not surfaced:
        lines.append("_No new opportunities cleared the threshold this run._")

    body = "\n".join(lines).rstrip() + "\n"
    title = f"{title_prefix}: {len(surfaced)} new"
    return {"title": title, "body": body}
