"""Module A — email-scanner (M3, BLOCKED on Gmail OAuth).

Design (GAMEPLAN §3, email-allowlist.yaml):
  1. Gmail API (OAuth refresh token from Actions secrets) pulls messages from the
     configured sender/label allowlist since the last run.
  2. Route each message:
       - senders.exclude            -> drop, never shown to the classifier
       - jobs-noreply@linkedin.com with a status_update_subjects subject
                                    -> STATUS UPDATE on an existing record
                                       (company from subject); never a new record
       - senders.scan / labels.route_in / direct_outreach fallback
                                    -> classify -> lane -> score -> store (new)
  3. Token expiry must fail loudly (workflow opens an issue), never silently.

Imports `core` only. The allowlist lives beside this module as allowlist.yaml.
"""
