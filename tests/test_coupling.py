import tests._bootstrap  # noqa: F401

import importlib


def test_no_cross_module_imports():
    mod = importlib.import_module("scripts.check_coupling")
    assert mod.check() == 0, "module isolation must hold"


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
