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


# --- artifact / mangled titles (real board examples) -----------------------

def test_mangled_titles_are_junk():
    # Truncated stubs, bare URLs, location-only, and scraped HN fragments that
    # were reaching the board at fit 6-7 on a decent snippet.
    for t in ("Full", "150", "The Role", "Application", "YC 19",
              "US Fully Remote", "REMOTE (worldwide)", "Remote (US Only)",
              "https://seeq.com", "https://futo.tech"):
        assert vetting.is_junk(_rec(t, "Acme")), t


def test_hiring_fragment_is_junk():
    assert vetting.is_junk(_rec("intelligence.com ) is hiring in Boston", "Air Space"))
    assert vetting.is_junk(_rec("Remote (US, Canada) We're building a platform", "Nova Credit"))


def test_domain_in_title_with_real_role_survives():
    # A domain-styled company name must not nuke a title that clearly has a role.
    for t in ("Scale.ai Forward Deployed Engineer", "Perplexity.ai Solutions Engineer",
              "Founding Engineer @ Cursor.com"):
        assert not vetting.is_junk(_rec(t, "Acme")), t


def test_bare_url_title_is_still_junk():
    # No role word alongside the domain -> still a URL artifact.
    for t in ("jobs.lever.co/acme", "https://seeq.com", "intelligence.com )"):
        assert vetting.is_junk(_rec(t, "Acme")), t


def test_short_real_titles_survive():
    # Legitimate short titles carry a role word and must NOT be flagged.
    for t in ("GTM Engineer", "Video Editor", "Data Architect", "Fractional CTO",
              "Growth Strategist", "AI Architect"):
        assert not vetting.is_junk(_rec(t, "Acme")), t


# --- off-lane roles ---------------------------------------------------------

def test_offlane_engineering_is_junk():
    for t in ("Senior Data Engineer", "Full Stack Engineer", "full stack engineer",
              "Senior DevOps Engineer", "Backend and Devops Mid", "Staff Frontend Engineer",
              "Staff Security Engineer", "Product Security Engineer, Application Security",
              "Architect, Security Products", "Staff Data Scientist", "Applied Data Scientist",
              "QA Engineer", "Network Engineer"):
        assert vetting.is_junk(_rec(t, "Acme")), t


def test_kept_categories_survive_offlane_gate():
    # Sales/solutions eng, applied-AI/ML eng, and any architect/consultant stay.
    for t in ("Senior Sales Engineer", "Sales Engineer (Pre-Sales)",
              "Remote Senior Sales Engineer - Cybersecurity SaaS",  # sales eng at a security co
              "ML / AI Engineer", "Applied AI Engineer", "AI Platform Engineer",
              "LLM Engineer", "AI Solutions Architect", "Staff Software Engineer",
              "Principal Software Engineer", "Consultant - Compliance Data Science & AI"):
        assert not vetting.is_junk(_rec(t, "Acme")), t


# --- staffing / recruiting firms ------------------------------------------

def test_staffing_firms_are_junk():
    for co in ("Randstad", "Jobot", "Robert Half", "Synergy Technologies",
               "Lorven Technologies Inc.", "XCUTIVES INC.", "ResourceTree Global Services",
               "Acme Staffing", "Foo Recruiting", "Bar Talent Solutions", "Insight Global"):
        assert vetting.is_junk(_rec("GTM Engineer", co)), co


def test_real_employers_are_not_staffing():
    for co in ("Anthropic", "Stripe", "Clay", "Databricks", "Notion Labs",
               "Vercel", "Ramp", "Rewind AI"):
        assert not vetting.is_junk(_rec("GTM Engineer", co)), co


# --- geography gate (US + Canada only) ------------------------------------

def _geo(location="", comp="", title="AI Consultant", company="Acme"):
    return schema.new_record(title=title, company=company, source="board",
                             location=location, comp=comp)


def test_geography_rejects_outside_us_canada():
    # the exact real failure: senior on-site AI role in Bangalore, paid in rupees
    assert vetting.is_junk(_geo("Bangalore, India", "INR 2500K-5000K"))
    assert vetting.is_junk(_geo("London, United Kingdom", "£90,000"))
    assert vetting.is_junk(_geo("Berlin, Germany", "€85,000"))
    assert vetting.is_junk(_geo("Remote (India)"))
    assert vetting.is_junk(_geo("Singapore", "S$120,000"))
    assert vetting.is_junk(_geo("Bengaluru"))
    assert vetting.is_junk(_geo(comp="₹ 30,00,000"))          # currency alone
    assert vetting.is_junk(_geo("Remote - EMEA"))
    assert vetting.is_junk(_geo("São Paulo, Brazil"))
    # blocklist gaps found by scanning the live board:
    assert vetting.is_junk(_geo("Belgrade"))
    assert vetting.is_junk(_geo("Costa Rica"))
    assert vetting.is_junk(_geo("Serbia"))


def test_geography_allows_us_and_canada():
    for loc, comp in [("Austin, TX", "$180k"), ("Remote - US", ""),
                      ("Toronto, Canada", "CAD 150,000"), ("Remote (US)", "$200,000"),
                      ("London, KY", "$120k"), ("Vancouver, BC", ""),
                      ("New York, NY", ""), ("Remote", "$150k"), ("", ""),
                      ("Atlanta, Georgia", ""),     # US state, not the country
                      ("Lebanon, NH", ""),          # US town, not the country
                      ("Remote - US & Canada", "")]:
        assert not vetting.is_junk(_geo(loc, comp)), (loc, comp)


def test_geography_rejects_latin_south_central_america():
    # bare 'america(s)' in the allow-list used to let these through
    assert vetting.is_junk(_geo("Remote - Latin America"))
    assert vetting.is_junk(_geo("Sao Paulo, South America"))
    assert vetting.is_junk(_geo("Remote (South America)"))
    assert vetting.is_junk(_geo("Remote (Central America)"))


def test_geography_still_allows_north_america_and_united_states():
    for loc in ("Remote - North America", "United States", "Remote, North America"):
        assert not vetting.is_junk(_geo(loc)), loc


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
