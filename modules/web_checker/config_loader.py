"""Load sources.yaml.

Prefers PyYAML (pinned in requirements.txt, present in CI). Falls back to a small
parser that supports the constrained subset used by sources.yaml (nested maps,
block lists of scalars, comments, quoted/bare scalars, bool/int). The fallback
exists only so the module can run in an environment without PyYAML; CI uses real
PyYAML and tests/test_config_loader.py pins the expected parse of sources.yaml.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

SOURCES_PATH = Path(__file__).resolve().parent / "sources.yaml"


def _coerce(scalar: str) -> Any:
    s = scalar.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", ""):
        return None
    try:
        return int(s)
    except ValueError:
        return s


def _strip_comment(line: str) -> str:
    # Remove trailing comments not inside quotes (sources.yaml uses no '#' in values).
    out = []
    in_s = in_d = False
    for ch in line:
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            break
        out.append(ch)
    return "".join(out).rstrip()


def _is_list_item(content: str) -> bool:
    return content == "-" or content.startswith("- ")


def _is_pair(content: str) -> bool:
    """True if `content` is a `key: value` mapping line (not a quoted scalar)."""
    if content[:1] in ("'", '"'):
        return False
    m = re.match(r"[^:'\"]+:(\s|$)", content)
    return bool(m)


def _mini_parse(text: str) -> Dict[str, Any]:
    # rows: list of [indent, content]; mutable so compact sequence maps can be
    # re-indented in place (YAML's "- key: val" case).
    rows: List[List[Any]] = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        rows.append([indent, line.strip()])

    pos = 0

    def parse_block(indent: int):
        nonlocal pos
        return parse_list(indent) if _is_list_item(rows[pos][1]) else parse_map(indent)

    def parse_map(indent: int) -> Dict[str, Any]:
        nonlocal pos
        m: Dict[str, Any] = {}
        while pos < len(rows) and rows[pos][0] == indent and not _is_list_item(rows[pos][1]):
            content = rows[pos][1]
            key, _, val = content.partition(":")
            key, val = key.strip(), val.strip()
            pos += 1
            if val == "":
                if pos < len(rows) and rows[pos][0] > indent:
                    m[key] = parse_block(rows[pos][0])
                else:
                    m[key] = None
            else:
                m[key] = _coerce(val)
        return m

    def parse_list(indent: int) -> List[Any]:
        nonlocal pos
        lst: List[Any] = []
        while pos < len(rows) and rows[pos][0] == indent and _is_list_item(rows[pos][1]):
            content = rows[pos][1][1:]  # drop leading '-'
            item_col = indent + (len(content) - len(content.lstrip(" "))) + 1
            item = content.strip()
            if item == "":
                pos += 1
                if pos < len(rows) and rows[pos][0] > indent:
                    lst.append(parse_block(rows[pos][0]))
                else:
                    lst.append(None)
            elif _is_pair(item):
                # compact block map: re-indent this row and parse a map here
                rows[pos] = [item_col, item]
                lst.append(parse_map(item_col))
            else:
                lst.append(_coerce(item))
                pos += 1
        return lst

    result = parse_block(rows[0][0]) if rows else {}
    return result if isinstance(result, dict) else {}


def load_sources(path: Path = SOURCES_PATH) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _mini_parse(text)


def enabled_adapters(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the list of source entries with enabled != false."""
    out = []
    for entry in (cfg.get("sources") or []):
        if entry.get("enabled", True):
            out.append(entry)
    return out
