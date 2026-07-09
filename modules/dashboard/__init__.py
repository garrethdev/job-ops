"""Lead dashboard — a local web app to work the opportunities as leads.

Each lead is one job opportunity (row) from the store. Per lead you can:
  - Find LinkedIn : Apollo find_contact -> saves name + LinkedIn + email (1 credit)
  - Find Email    : shows the cached email (free after the reveal above)
  - Add notes     : free-text saved on the lead
  - Delete        : removes the lead

Local-only: needs a running server because the Apollo key can't live in the
browser. Imports `core` only (store + apollo + config) — no sibling-module imports.
Run: `python -m modules.dashboard` then open http://127.0.0.1:8787
"""
