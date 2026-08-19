import tests._bootstrap  # noqa: F401

import contextlib
import io
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
    assert res["fit_rationale"].startswith("[no LLM -> heuristic] ")
    assert res["lane"] == score_heuristic(r)["lane"]


def test_score_llm_parses_prose_wrapped_json(monkeypatch=None):
    # Real description so the thin-description cap doesn't interfere with the
    # parsing/coercion this test is actually exercising.
    r = _rec("AI Consultant", "We need an AI consultant. " * 12)
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


def test_score_llm_thin_description_caps_fit():
    # A high LLM score on a near-empty description is a guess -> capped at 3.
    r = _rec("GTM Engineer", "remote")  # < 200 chars of description
    orig = scoring._call_llm
    scoring._call_llm = lambda prompt: (
        '{"lane":"gtm-engineer","fit_score":9,"fit_rationale":"perfect","red_flags":[]}', "m", "deepseek")
    try:
        res = score_llm(r)
    finally:
        scoring._call_llm = orig
    assert res["fit_score"] == 3
    assert "thin description" in res["fit_rationale"].lower()


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


def test_ignore_location_skips_location_dealbreaker():
    # Default: an on-site-only posting trips the location deal-breaker red flag.
    base = _rec("Solutions Architect", "on-site only, in-office, dallas")
    default = score_heuristic(dict(base))
    assert any("on-site only" in f for f in default["red_flags"])
    # ignore_location: the SAME posting no longer flags location...
    ig = score_heuristic(dict(base, ignore_location=True))
    assert not any("on-site" in f for f in ig["red_flags"])


def test_ignore_location_only_affects_location_dealbreakers():
    # A non-location deal-breaker (e.g. 'unpaid') still fires under ignore_location.
    r = _rec("Unpaid Intern Architect", "unpaid intern on-site only")
    ig = score_heuristic(dict(r, ignore_location=True))
    assert any("unpaid" in f or "intern" in f for f in ig["red_flags"])


def test_llm_unparseable_reply_falls_back_not_crash(monkeypatch=None):
    # A non-JSON LLM reply must fall back to the heuristic, never raise.
    orig = scoring._call_llm
    scoring._call_llm = lambda prompt: ("I'm sorry, I can't help with that.", "openrouter", "deepseek")
    try:
        r = scoring.score_llm(_rec("GTM Engineer", "gtm revops automation remote"))
        assert isinstance(r["fit_score"], int) and 0 <= r["fit_score"] <= 10
        assert "heuristic" in r["fit_rationale"].lower()
    finally:
        scoring._call_llm = orig


def test_llm_network_error_falls_back(monkeypatch=None):
    def boom(prompt): raise RuntimeError("network down")
    orig = scoring._call_llm
    scoring._call_llm = boom
    try:
        r = scoring.score_llm(_rec("Solutions Architect", "platform distributed systems"))
        assert isinstance(r["fit_score"], int)
        assert "heuristic" in r["fit_rationale"].lower()
    finally:
        scoring._call_llm = orig


def test_llm_error_tagged_with_exception_class():
    # An LLM exception must be distinguishable from "no key configured".
    def boom(prompt): raise TimeoutError("api down")
    orig = scoring._call_llm
    scoring._call_llm = boom
    try:
        res = score_llm(_rec("Software Architect", "system design kubernetes remote"))
    finally:
        scoring._call_llm = orig
    assert res["fit_rationale"].startswith("[LLM error: TimeoutError -> heuristic] ")
    assert not res["fit_rationale"].startswith("[no LLM")


def test_apply_scores_warns_on_llm_errors():
    # A batch with LLM failures must print one WARNING (with the count) to stderr
    # so cron logs surface the outage.
    def boom(prompt): raise RuntimeError("network down")
    recs = [_rec("GTM Engineer", "growth engineer hubspot integrations remote"),
            _rec("AI Consultant", "ai consultant genai llm advisory remote")]
    orig = scoring._call_llm
    scoring._call_llm = boom
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            apply_scores(recs, use_llm=True)
    finally:
        scoring._call_llm = orig
    err = buf.getvalue()
    assert "WARNING" in err and "2" in err
    assert all(r["fit_rationale"].startswith("[LLM error: RuntimeError") for r in recs)


def test_apply_scores_no_warning_without_llm_errors():
    # Heuristic-only batches (and clean LLM batches) must stay silent on stderr.
    r = _rec("GTM Engineer", "growth engineer hubspot integrations remote")
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        apply_scores([r])
    assert "WARNING" not in buf.getvalue()


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
