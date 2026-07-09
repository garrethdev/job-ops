import tests._bootstrap  # noqa: F401

from modules.web_checker.config_loader import enabled_adapters, load_sources


def test_sources_yaml_parses_expected_shape():
    cfg = load_sources()
    assert "sources" in cfg
    names = {s["name"] for s in cfg["sources"]}
    assert {"remoteok", "weworkremotely-programming", "hn-whoishiring"} <= names


def test_each_source_has_adapter_and_limit():
    cfg = load_sources()
    for s in cfg["sources"]:
        assert s["adapter"], f"{s['name']} missing adapter"
        assert isinstance(s["limit"], int)
        assert isinstance(s["keywords"], list) and s["keywords"]


def test_enabled_filter():
    cfg = load_sources()
    assert len(enabled_adapters(cfg)) == len(cfg["sources"])  # all enabled by default


def test_wwr_feeds_are_list_of_urls():
    cfg = load_sources()
    wwr = next(s for s in cfg["sources"] if s["name"] == "weworkremotely-programming")
    assert isinstance(wwr["feeds"], list) and wwr["feeds"][0].startswith("https://")


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
