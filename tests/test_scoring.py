import tests._bootstrap  # noqa: F401

import os

from core import schema, scoring
from core.config import LANES
from core.scoring import apply_scores, score_heuristic, score_llm


class _NoKeys:
    """Context manager: clear LLM keys from env (the .env has real ones)."""
    def __enter__(self):
        self._saved = {k: os.environ.pop(k, None) for k in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY")}
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v


def _rec(title, snippet):
    r = schema.new_record(title=title, company="Foo", source="board")
    r["snippet"] = snippet
    return r


def test_software_architect_classified():
    r = _rec("Staff Software Architect — Distributed Systems",
             "system design microservices kubernetes aws platform remote")
    res = score_heuristic(r)
    assert res["lane"] == "software-architect"
    assert res["fit_score"] >= 6


def test_ai_video_editor_classified():
    r = _rec("AI Video Editor (Remote)",
             "generative video ai video editing capcut runway ffmpeg short-form reels")
    res = score_heuristic(r)
    assert res["lane"] == "ai-video-editor"


def test_gtm_engineer_classified():
    r = _rec("GTM Engineer",
             "go-to-market growth engineer hubspot salesforce integrations outbound automation remote")
    res = score_heuristic(r)
    assert res["lane"] == "gtm-engineer"


def test_ai_consultant_classified():
    r = _rec("Generative AI Consultant",
             "ai consultant genai llm ai strategy ai implementation advisory client-facing remote")
    res = score_heuristic(r)
    assert res["lane"] == "ai-consultant"


def test_onsite_dealbreaker_flags_and_lowers():
    r = _rec("Software Architect",
             "system design platform api on-site only relocation required")
    res = score_heuristic(r)
    assert res["red_flags"], "on-site-only / relocation must raise a red flag"


def test_irrelevant_job_scores_low():
    r = _rec("Line Cook", "prepare food kitchen restaurant")
    res = score_heuristic(r)
    assert res["fit_score"] <= 3


def test_apply_scores_only_touches_unscored():
    r = _rec("GTM Engineer", "growth engineer hubspot integrations remote")
    apply_scores([r])
    assert r["fit_score"] > 0 and r["lane"] in LANES


def test_score_llm_falls_back_to_heuristic_without_keys():
    r = _rec("Software Architect", "system design microservices kubernetes remote")
    with _NoKeys():
        res = score_llm(r)
    assert res["fit_rationale"].startswith("[no LLM key -> heuristic] ")
    assert res["lane"] == score_heuristic(r)["lane"]


def test_score_llm_parses_prose_wrapped_json(monkeypatch=None):
    r = _rec("X", "y")
    orig = scoring._call_llm
    scoring._call_llm = lambda prompt: (
        'Sure!\n{"lane":"ai-consultant","fit_score":"7","fit_rationale":"good",'
        '"red_flags":["a","b","c","d","e","f","g"]}\ndone', "openrouter", "deepseek")
    try:
        res = score_llm(r)
    finally:
        scoring._call_llm = orig
    assert res["lane"] == "ai-consultant"
    assert res["fit_score"] == 7 and isinstance(res["fit_score"], int)  # "7" coerced
    assert res["fit_rationale"].startswith("[deepseek] ")
    assert len(res["red_flags"]) == 6  # truncated to 6


def test_score_llm_bad_lane_falls_back_to_heuristic_lane():
    r = _rec("Software Architect", "system design kubernetes aws platform remote")
    orig = scoring._call_llm
    scoring._call_llm = lambda prompt: ('{"lane":"banana","fit_score":9,"fit_rationale":"x","red_flags":[]}', "m", "m")
    try:
        res = score_llm(r)
    finally:
        scoring._call_llm = orig
    assert res["lane"] == score_heuristic(r)["lane"]


def test_llm_backend_selection():
    with _NoKeys():
        os.environ["OPENROUTER_API_KEY"] = "or"
        os.environ["ANTHROPIC_API_KEY"] = "an"
        assert scoring._llm_backend()[0] == "openrouter"
        del os.environ["OPENROUTER_API_KEY"]
        assert scoring._llm_backend()[0] == "anthropic"
        del os.environ["ANTHROPIC_API_KEY"]
        assert scoring._llm_backend() == (None, None, None)


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
