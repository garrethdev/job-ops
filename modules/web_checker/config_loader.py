"""Load sources.yaml via the shared core YAML loader."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.yaml_loader import load_yaml

SOURCES_PATH = Path(__file__).resolve().parent / "sources.yaml"


def load_sources(path: Path = SOURCES_PATH) -> Dict[str, Any]:
    return load_yaml(path)


def enabled_adapters(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the list of source entries with enabled != false."""
    return [e for e in (cfg.get("sources") or []) if e.get("enabled", True)]
