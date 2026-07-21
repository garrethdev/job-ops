import tests._bootstrap  # noqa: F401

from modules.web_checker.adapters.firecrawl import _valid_link, _host


def test_host_strips_www_without_mangling():
    assert _host("https://www.workatastartup.com/jobs") == "workatastartup.com"
    assert _host("https://aijobs.net/") == "aijobs.net"


def test_same_domain_url_is_kept():
    board = "https://www.workatastartup.com/jobs"
    assert _valid_link("https://www.workatastartup.com/jobs/95705", board, "") == "https://www.workatastartup.com/jobs/95705"


def test_cross_domain_hallucination_is_dropped():
    # Firecrawl gluing a slug onto the employer's domain -> not the board -> drop it.
    board = "https://nextplay.so/jobs"
    assert _valid_link("https://bendingspoons.com/jobs/chief-of-staff", board, "") == ""
    assert _valid_link("https://casadellibro.com/anything", board, "") == ""


def test_must_contain_override():
    board = "https://wellfound.com/jobs"
    assert _valid_link("https://wellfound.com/jobs/123-eng", board, "wellfound.com/jobs/") == "https://wellfound.com/jobs/123-eng"
    assert _valid_link("https://evil.com/jobs/123", board, "wellfound.com/jobs/") == ""


def test_relative_link_resolved_against_board():
    board = "https://aijobs.net/"
    assert _valid_link("/job/ai-architect-236102", board, "") == "https://aijobs.net/job/ai-architect-236102"


def test_empty_link_stays_empty():
    assert _valid_link("", "https://nextplay.so/jobs", "") == ""
    assert _valid_link(None, "https://nextplay.so/jobs", "") == ""


def test_trust_ats_keeps_out_of_domain_ats_links():
    board = "https://bloomberry.com/gtm_jobs.html"
    ats = "https://jobs.ashbyhq.com/owner/12650f0b"
    # without trust_ats, a cross-domain link is dropped; with it, ATS links pass
    assert _valid_link(ats, board, "") == ""
    assert _valid_link(ats, board, "", trust_ats=True) == ats
    assert _valid_link("https://job-boards.greenhouse.io/fireworksai/jobs/1", board, "", trust_ats=True).endswith("/jobs/1")
    # a random non-ATS domain is still dropped even with trust_ats
    assert _valid_link("https://casadellibro.com/x", board, "", trust_ats=True) == ""


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
