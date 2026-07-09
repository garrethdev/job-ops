"""Central paths and environment access for job-ops.

core/ is the ONLY shared code. Modules import from core, never from each other.
"""
from __future__ import annotations

import os
from pathlib import Path

# Repo root = parent of core/
ROOT = Path(__file__).resolve().parent.parent

STORE_PATH = ROOT / "store" / "opportunities.jsonl"
PROFILES_DIR = ROOT / "profiles"

# Fit-score threshold at/above which a record is worth enriching + surfacing.
DEFAULT_FIT_THRESHOLD = int(os.environ.get("JOBOPS_FIT_THRESHOLD", "6"))

# Valid enum values, single source of truth (schema.py imports these).
LANES = ("architecture", "video-ai")
SOURCES = ("email", "board", "marketplace")
STATUSES = ("new", "enriched", "queued_for_apply", "applied", "rejected")


def anthropic_key() -> str | None:
    """Return the Anthropic API key if present, else None (heuristic fallback)."""
    return os.environ.get("ANTHROPIC_API_KEY") or None
