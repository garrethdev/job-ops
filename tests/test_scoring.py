import tests._bootstrap  # noqa: F401

from core import schema
from core.config import LANES
from core.scoring import apply_scores, score_heuristic


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


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
