import tests._bootstrap  # noqa: F401

from modules.web_checker.resolve import pick_posting


def test_picks_a_real_posting_over_noise():
    results = [
        {"url": "https://www.reddit.com/r/gtmengineering/comments/x", "description": "chatter"},
        {"url": "https://www.indeed.com/q-go-to-market-engineer-jobs.html", "description": "index"},
        {"url": "https://www.builtinnyc.com/job/go-market-engineer/3642967", "description": "Clay is hiring a GTM Engineer in NYC."},
    ]
    url, desc = pick_posting(results)
    assert url == "https://www.builtinnyc.com/job/go-market-engineer/3642967"
    assert "Clay" in desc


def test_prefers_ats_domain():
    results = [
        {"url": "https://news.example.com/article", "description": "n"},
        {"url": "https://jobs.ashbyhq.com/owner/abc123", "description": "GTM Engineer at Owner"},
    ]
    url, _ = pick_posting(results)
    assert "ashbyhq.com" in url


def test_returns_empty_when_only_noise():
    results = [
        {"url": "https://www.linkedin.com/posts/someone-activity-123", "description": ""},
        {"url": "https://en.wikipedia.org/wiki/Go-to-market", "description": ""},
    ]
    assert pick_posting(results) == ("", "")


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
