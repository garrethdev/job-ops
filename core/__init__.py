"""job-ops shared core — store I/O, schema, dedupe, profiles, scoring, digest.

This is the ONLY code shared across modules. Modules import from `core`; they
never import from each other. The opportunities store (core.store) is the sole
inter-module contract.
"""
