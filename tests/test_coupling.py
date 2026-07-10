import tests._bootstrap  # noqa: F401

import ast
import importlib

cc = importlib.import_module("scripts.check_coupling")


def _imports(code, relpath):
    return list(cc._absolute_imports(ast.parse(code), cc.ROOT / relpath))


def test_no_cross_module_imports():
    assert cc.check() == 0, "module isolation must hold"


def test_relative_sibling_import_resolves_to_sibling_module():
    names = _imports("from ..email_scanner import parse", "modules/web_checker/foo.py")
    assert "modules.email_scanner" in names  # would be flagged as a violation


def test_intra_package_relative_import_not_a_sibling():
    names = _imports("from . import config_loader", "modules/web_checker/foo.py")
    assert all(n == "modules.web_checker" or not n.startswith("modules.")
               for n in names), names


def test_absolute_sibling_import_still_detected():
    names = _imports("import modules.email_scanner.parse", "modules/web_checker/foo.py")
    assert "modules.email_scanner.parse" in names


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
