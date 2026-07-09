import tests._bootstrap  # noqa: F401

from core import schema
from core.scoring import apply_scores, score_heuristic


def test_architecture_job_classified_and_scored():
    r = schema.new_record(
        title="Staff Backend Engineer — Distributed Systems", company="Foo", source="board"
    )
    r["snippet"] = "kubernetes aws microservices platform api scalability"
    res = score_heuristic(r)
    assert res["lane"] == "architecture"
    assert res["fit_score"] >= 6


def test_video_ai_job_classified():
    r = schema.new_record(title="Creative Technologist, AI Video", company="Bar", source="board")
    r["snippet"] = "generative video diffusion comfyui ffmpeg render pipeline post-production"
    res = score_heuristic(r)
    assert res["lane"] == "video-ai"


def test_dealbreaker_lowers_score_and_flags():
    r = schema.new_record(title="Backend Engineer", company="Baz", source="board")
    r["snippet"] = "python api platform on-site only relocation required"
    res = score_heuristic(r)
    assert res["red_flags"], "deal-breaker keyword should raise a red flag"


def test_irrelevant_job_scores_low():
    r = schema.new_record(title="Line Cook", company="Diner", source="board")
    r["snippet"] = "prepare food kitchen"
    res = score_heuristic(r)
    assert res["fit_score"] <= 3


def test_apply_scores_only_touches_unscored():
    r = schema.new_record(title="Backend Engineer", company="Foo", source="board")
    r["snippet"] = "python platform api"
    apply_scores([r])
    assert r["fit_score"] > 0 and r["lane"]


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
