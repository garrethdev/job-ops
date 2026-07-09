"""Module C — contact-enricher (M4, BLOCKED on APOLLO_API_KEY).

Design (GAMEPLAN §3):
  1. For each store record with fit_score >= threshold and an empty contact:
     Apollo organizations/enrich -> people/match, filtered to decision-maker
     titles (CTO, VP Engineering, Head of AI/ML, Lead/Principal Engineer; for the
     video-ai lane, Head of Post-Production / Creative Technology).
  2. Store verified business email + LinkedIn on the record; set status=enriched.
  3. Cap Apollo lookups per run (JOBOPS_APOLLO_MAX_LOOKUPS) to bound credit spend.
  4. Business contact info for 1:1 outreach only — no bulk blasts.

Imports `core` only (reads/writes the store via core.store).
"""
