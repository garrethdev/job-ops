import tests._bootstrap  # noqa: F401

from modules.email_scanner import parse

STATUS = ["your application was sent", "your application was viewed"]


def test_sender_email_extracted_from_header():
    assert parse.sender_email("LinkedIn <jobs-noreply@linkedin.com>") == "jobs-noreply@linkedin.com"
    assert parse.sender_email("plain@x.com") == "plain@x.com"


def test_linkedin_alert_with_comp():
    p = parse.parse_opportunity("Solution Architect - Agentic AI & Data at XCUTIVES INC.: up to $210K/year")
    assert p["title"] == "Solution Architect - Agentic AI & Data"
    assert p["company"] == "XCUTIVES INC."
    assert "210K" in p["comp"]


def test_apply_prefix_and_and_more_suffix():
    p = parse.parse_opportunity("Garreth, apply to ML Solutions Architect at Jobot and more")
    assert p == {"title": "ML Solutions Architect", "company": "Jobot", "comp": ""}


def test_new_jobs_similar_to_and_at_split():
    p = parse.parse_opportunity("New jobs similar to Enterprise AI Solutions Consultant at Recco Consulting Inc.")
    assert p["title"] == "Enterprise AI Solutions Consultant"
    assert p["company"] == "Recco Consulting Inc."


def test_nested_quotes_and_featured_prefix():
    p = parse.parse_opportunity(
        "Garreth, apply now to 'Featured AI Job: Ocean Video AI Project Manager at Colorado AI News'")
    assert p["company"] == "Colorado AI News"
    assert "Ocean Video AI Project Manager" in p["title"]


def test_indeed_at_symbol_and_wellfound_truncation():
    assert parse.parse_opportunity("Architect @ Avalara")["company"] == "Avalara"
    p = parse.parse_opportunity("Principal TPM at Prime Video & Amazon Studios - Wellfound")
    assert p["company"] == "Prime Video & Amazon Studios"


def test_status_update_routing_and_company():
    assert parse.is_status_update("jobs-noreply@linkedin.com", "Your application was viewed by Telon", STATUS)
    assert not parse.is_status_update("jobalerts-noreply@linkedin.com", "Architect at Foo", STATUS)
    assert parse.status_company("Garreth, your application was sent to Mine & Yours") == "Mine & Yours"


def test_unparseable_returns_none():
    assert parse.parse_opportunity("Weekly newsletter digest") is None


if __name__ == "__main__":
    raise SystemExit(tests._bootstrap.run_module(dict(globals())))
