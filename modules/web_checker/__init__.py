"""Module B — web-checker.

Fetches opportunities from configured API/RSS sources (sources.yaml), classifies
and scores them against the lane profiles, dedupes, writes to the store, and
emits a digest. Standalone: imports `core` only.

Fetch-strategy priority (see GAMEPLAN §3): official APIs/RSS first, Firecrawl for
JS-rendered pages, per-site adapters only where allowed. This milestone ships the
three no-auth API/RSS sources: RemoteOK, WeWorkRemotely, HN "Who is hiring".
"""
