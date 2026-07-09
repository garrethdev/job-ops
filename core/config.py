"""Central paths and environment access for job-ops.

core/ is the ONLY shared code. Modules import from core, never from each other.
"""
from __future__ import annotations

import os
from pathlib import Path

# Repo root = parent of core/
ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Load a local .env for convenience (stdlib only, no dependency).

    Only sets keys that are NOT already in the environment, so real shell env and
    GitHub Actions secrets always win — the file is a local fallback, never an
    override. Supports `KEY=value`, `export KEY=value`, comments, and quotes.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv(ROOT / ".env")

STORE_PATH = ROOT / "store" / "opportunities.jsonl"
PROFILES_DIR = ROOT / "profiles"

# Fit-score threshold at/above which a record is worth enriching + surfacing.
DEFAULT_FIT_THRESHOLD = int(os.environ.get("JOBOPS_FIT_THRESHOLD", "6"))

# Target role categories (the `lane` field). Single source of truth: schema
# validation, scoring, digest grouping, and profile filenames all key off this.
# Each value maps to profiles/<lane>.md.
LANES = ("gtm-engineer", "software-architect", "ai-consultant", "ai-video-editor")
SOURCES = ("email", "board", "marketplace")
STATUSES = ("new", "enriched", "queued_for_apply", "applied", "rejected")

# Only remote or hybrid roles are wanted. Scoring boosts remote/hybrid and treats
# on-site-only / relocation-required as deal-breakers (see the profiles).
LOCATION_POLICY = "remote-or-hybrid"

# LLM scoring provider (used with --llm). OpenRouter/DeepSeek preferred if set.
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def anthropic_key() -> str | None:
    """Return the Anthropic API key if present, else None."""
    return os.environ.get("ANTHROPIC_API_KEY") or None


def openrouter_key() -> str | None:
    """Return the OpenRouter API key if present, else None."""
    return os.environ.get("OPENROUTER_API_KEY") or None


def apollo_key() -> str | None:
    """Return the Apollo API key if present, else None."""
    return os.environ.get("APOLLO_API_KEY") or None
