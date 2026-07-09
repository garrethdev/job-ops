#!/usr/bin/env python3
"""CI guard: enforce module isolation (GAMEPLAN §2).

Rules:
  1. A file in modules/<X>/ may import `core`, stdlib, third-party, and its OWN
     package (modules.<X>...), but NOT a sibling module (modules.<Y>, Y != X).
  2. core/ must NOT import from modules/ (the contract flows one way).

Exits non-zero on any violation. Wired into .github/workflows/ci.yml.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "modules"
CORE_DIR = ROOT / "core"


def _imported_names(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # relative import — resolve leading dots against caller later
                yield ("__rel__", node.level, node.module or "")
            elif node.module:
                yield node.module


def check() -> int:
    violations = []

    # Rule 1: no cross-module imports.
    for pkg in sorted(p for p in MODULES_DIR.iterdir() if p.is_dir()):
        own = f"modules.{pkg.name}"
        for py in pkg.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for name in _imported_names(tree):
                if isinstance(name, tuple):
                    continue  # relative imports stay within the package by construction
                if name == "modules" or (name.startswith("modules.") and not (
                    name == own or name.startswith(own + ".")
                )):
                    violations.append(
                        f"{py.relative_to(ROOT)} imports sibling module: {name}"
                    )

    # Rule 2: core must not import modules.
    for py in CORE_DIR.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for name in _imported_names(tree):
            if isinstance(name, tuple):
                continue
            if name == "modules" or name.startswith("modules."):
                violations.append(
                    f"{py.relative_to(ROOT)} (core) imports a module: {name}"
                )

    if violations:
        print("COUPLING CHECK FAILED — module isolation violated:")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("coupling check passed: no cross-module imports, core imports no module.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
