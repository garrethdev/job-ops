"""Source adapters. Each exposes `fetch(entry: dict) -> List[dict]` returning
partial records (title, company, url, location, comp, posted, snippet, source,
source_detail). Adapters do fetching + normalization only — scoring, dedupe, and
storage happen in run.py via core.
"""
from importlib import import_module
from typing import Callable, Dict, List

# Registry: adapter name -> module path
_ADAPTERS = {
    "remoteok": "modules.web_checker.adapters.remoteok",
    "weworkremotely": "modules.web_checker.adapters.weworkremotely",
    "hn_whoishiring": "modules.web_checker.adapters.hn_whoishiring",
}


def get_adapter(name: str) -> Callable[[Dict], List[Dict]]:
    if name not in _ADAPTERS:
        raise KeyError(f"unknown adapter: {name!r} (known: {sorted(_ADAPTERS)})")
    mod = import_module(_ADAPTERS[name])
    return mod.fetch
