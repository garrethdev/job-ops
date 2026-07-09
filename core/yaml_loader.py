"""YAML loading, shared across modules (so no module owns it / no cross-imports).

Prefers PyYAML (pinned in requirements.txt, present in CI). Falls back to a small
parser supporting the constrained subset our config files use (nested maps, block
lists of scalars, compact `- key: val` sequence maps, comments, quoted/bare
scalars, bool/int). The fallback only exists so modules run without PyYAML; CI
uses real PyYAML.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List


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
    if content[:1] in ("'", '"'):
        return False
    return bool(re.match(r"[^:'\"]+:(\s|$)", content))


def _mini_parse(text: str) -> Dict[str, Any]:
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
            content = rows[pos][1][1:]
            item_col = indent + (len(content) - len(content.lstrip(" "))) + 1
            item = content.strip()
            if item == "":
                pos += 1
                if pos < len(rows) and rows[pos][0] > indent:
                    lst.append(parse_block(rows[pos][0]))
                else:
                    lst.append(None)
            elif _is_pair(item):
                rows[pos] = [item_col, item]
                lst.append(parse_map(item_col))
            else:
                lst.append(_coerce(item))
                pos += 1
        return lst

    result = parse_block(rows[0][0]) if rows else {}
    return result if isinstance(result, dict) else {}


def parse_yaml(text: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _mini_parse(text)


def load_yaml(path: Path) -> Dict[str, Any]:
    return parse_yaml(Path(path).read_text(encoding="utf-8"))
