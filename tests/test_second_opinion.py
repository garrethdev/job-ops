import tests._bootstrap  # noqa: F401  (path bootstrap for direct runs)

import contextlib
import json
import os
import urllib.request

from scripts import second_opinion as so


class _FakeResp:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@contextlib.contextmanager
def _patched_urlopen(fn):
    """Swap urllib.request.urlopen for `fn`; always restore."""
    real = urllib.request.urlopen
    urllib.request.urlopen = fn
    try:
        yield
    finally:
        urllib.request.urlopen = real


@contextlib.contextmanager
def _fake_key():
    """Force a dummy OpenRouter key so no real secret leaks into payloads."""
    saved = os.environ.get("OPENROUTER_API_KEY")
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = saved


def _lead(**over):
    r = {
        "id": "lead-1",
        "title": "GTM Engineer",
        "company": "Acme",
        "lane": "gtm-engineer",
        "fit_score": 8,
        "snippet": "hubspot salesforce integrations outbound automation remote",
        "location": "Remote (US)",
        "comp": "$150k",
        "company_summary": "Acme sells CRM tooling",
        "company_remote": "remote",
    }
    r.update(over)
    return r


def test_prompt_contains_rubric_and_lead():
    prompt = so.build_prompt(_lead(), "## Match keywords\ngtm engineer, growth engineer")
    assert '"gtm-engineer"' in prompt
    assert "gtm engineer, growth engineer" in prompt
    assert "GTM Engineer" in prompt and "Acme" in prompt
    assert "ONLY a JSON object" in prompt


def test_prompt_truncates_snippet():
    prompt = so.build_prompt(_lead(snippet="x" * 5000), "rubric")
    assert "x" * 2000 in prompt and "x" * 2001 not in prompt


def test_score_payload_shape():
    p = so.score_payload("google/gemini-2.5-pro", "hello")
    assert p["model"] == "google/gemini-2.5-pro"
    assert p["temperature"] == 0
    assert p["messages"] == [{"role": "user", "content": "hello"}]


def test_gemini_score_sends_payload_and_parses_reply():
    seen = {}

    def fake(req, timeout=0):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        seen["body"] = json.loads(req.data.decode())
        return _FakeResp(
            {"choices": [{"message": {"content": 'noise {"score": 4, "reason": "weak fit"} tail'}}]}
        )

    with _fake_key(), _patched_urlopen(fake):
        score, reason = so.gemini_score("google/gemini-2.5-pro", _lead(), "rubric text")
    assert score == 4 and reason == "weak fit"
    assert seen["url"] == so.OPENROUTER_URL
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == "google/gemini-2.5-pro"
    assert seen["body"]["temperature"] == 0
    assert "rubric text" in seen["body"]["messages"][0]["content"]


def test_gemini_score_clamps_and_survives_garbage():
    def fake_high(req, timeout=0):
        return _FakeResp({"choices": [{"message": {"content": '{"score": 99, "reason": "r"}'}}]})

    def fake_garbage(req, timeout=0):
        return _FakeResp({"choices": [{"message": {"content": "not json at all"}}]})

    def fake_boom(req, timeout=0):
        raise OSError("network down")

    with _fake_key():
        with _patched_urlopen(fake_high):
            assert so.gemini_score("m", _lead(), "r")[0] == 10
        with _patched_urlopen(fake_garbage):
            assert so.gemini_score("m", _lead(), "r")[0] is None
        with _patched_urlopen(fake_boom):
            score, reason = so.gemini_score("m", _lead(), "r")
    assert score is None and "OSError" in reason


def test_resolve_model_prefers_best_listed():
    def listing(ids):
        def fake(req, timeout=0):
            return _FakeResp({"data": [{"id": i} for i in ids]})
        return fake

    with _patched_urlopen(listing(["google/gemini-2.5-pro", "google/gemini-3.1-pro-preview"])):
        assert so.resolve_model() == "google/gemini-3.1-pro-preview"
    with _patched_urlopen(listing(["google/gemini-2.5-pro", "other/model"])):
        assert so.resolve_model() == "google/gemini-2.5-pro"

    def fake_boom(req, timeout=0):
        raise OSError("offline")

    with _patched_urlopen(fake_boom):
        assert so.resolve_model() == so.GEMINI_CHAIN[0]


def _row(pipeline, gemini, id="x"):
    return {
        "id": id,
        "pipeline_score": pipeline,
        "gemini_score": gemini,
        "delta": (gemini - pipeline) if gemini is not None else None,
    }


def test_disagreement_math():
    rows = [
        _row(8, 5, id="down3"),    # delta -3 -> flagged (boundary)
        _row(4, 8, id="up4"),      # delta +4 -> flagged
        _row(7, 5, id="down2"),    # delta -2 -> not flagged
        _row(6, 6, id="same"),     # delta 0  -> not flagged
        _row(9, None, id="fail"),  # failed call -> never flagged
    ]
    flagged = so.disagreements(rows)
    assert [r["id"] for r in flagged] == ["up4", "down3"]  # biggest gap first


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
