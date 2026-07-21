import tests._bootstrap  # noqa: F401

from core import schema, vetting
from core.scoring import apply_scores


def _rec(title, company, snippet=""):
    r = schema.new_record(title=title, company=company, source="board")
    r["snippet"] = snippet
    return r


def test_multiple_roles_listing_is_junk():
    assert vetting.is_junk(_rec("Multiple Roles", "DuckDuckGo"))
    assert vetting.is_junk(_rec("Various Positions", "Acme"))
    assert vetting.is_junk(_rec("3 Open Roles", "Acme"))
    assert vetting.is_junk(_rec("Careers", "Acme"))


def test_placeholder_company_is_junk():
    for co in ("n/a", "Unknown", "Various", "Remote", "Confidential", "TBD"):
        assert vetting.is_junk(_rec("Software Architect", co)), co


def test_real_company_names_are_not_junk_by_company():
    # Real firms that ALSO run search/aggregators must not be auto-rejected;
    # the title gate + scoring handle relevance, not a company blocklist.
    for co in ("Google", "Yahoo", "DuckDuckGo", "LinkedIn"):
        assert not vetting.is_junk(_rec("Staff Software Architect", co)), co


def test_location_as_company_is_junk():
    for co in ("Austin, TX, US", "McLean, VA, US", "San Francisco, CA", "London, UK"):
        assert vetting.is_junk(_rec("GTM Engineer", co)), co
    # real companies (incl. legal suffixes) must NOT trip the location guard
    for co in ("Owner.com", "Acme, Inc", "Foo, LLC", "Fireworks AI"):
        assert not vetting.is_junk(_rec("GTM Engineer", co)), co


def test_real_role_is_not_junk():
    assert not vetting.is_junk(_rec("Staff Software Architect", "Baseten"))
    assert not vetting.is_junk(_rec("AI Solutions Architect", "LatentBridge"))
    assert not vetting.is_junk(_rec("Head of AI", "Kin Health"))
    # but a multi-role listing under a real company IS still junk (title gate)
    assert vetting.is_junk(_rec("Multiple Roles", "DuckDuckGo"))


def test_apply_scores_stamps_junk_fit1_without_llm():
    junk = _rec("Multiple Roles", "DuckDuckGo", "engineering roles")
    apply_scores([junk], use_llm=True)  # would bill, but junk short-circuits before any LLM call
    assert junk["fit_score"] == 1
    assert "vetting" in junk["fit_rationale"].lower()
    assert junk["red_flags"]


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
