-- jobops_upsert_discovery: ownership-split upsert for the pipeline -> board sync.
--
-- Ownership contract for jobops_leads:
--   * PIPELINE-owned (discovery): title, company, url, location, comp, posted,
--     last_seen, fit_score, fit_rationale, red_flags, snippet,
--     company_summary, company_remote, company_hq.
--   * DASHBOARD-owned (workflow): status, stage, notes, contact, warm,
--     outreached_at, updated_at. NEVER touched on update by this function, so
--     re-running the sync after a re-score / company research pass refreshes
--     discovery data without clobbering edits made in the Vercel app.
--   * Insert-only provenance: id, schema_version, lane, source, source_detail,
--     first_seen. Written when a row is first created, left alone after.
--
-- New inserts get status='new', stage='new' (matching the table defaults).
-- Called by scripts/sync_to_supabase.py via POST /rest/v1/rpc/jobops_upsert_discovery
-- with {"rows": [...]}; returns the number of rows inserted or updated.

create or replace function public.jobops_upsert_discovery(rows jsonb)
returns integer
language sql
set search_path = public
as $$
with up as (
  insert into public.jobops_leads (
    id, schema_version, lane, source, source_detail,
    title, company, url, location, comp, posted,
    first_seen, last_seen, fit_score, fit_rationale, red_flags,
    snippet, company_summary, company_remote, company_hq,
    status, stage
  )
  select
    r->>'id',
    coalesce((r->>'schema_version')::int, 1),
    r->>'lane',
    r->>'source',
    r->>'source_detail',
    r->>'title',
    r->>'company',
    r->>'url',
    r->>'location',
    r->>'comp',
    r->>'posted',
    (r->>'first_seen')::timestamptz,
    (r->>'last_seen')::timestamptz,
    coalesce((r->>'fit_score')::int, 0),
    r->>'fit_rationale',
    coalesce(r->'red_flags', '[]'::jsonb),
    r->>'snippet',
    r->>'company_summary',
    r->>'company_remote',
    r->>'company_hq',
    'new',  -- dashboard-owned: set on insert only
    'new'   -- dashboard-owned: set on insert only
  from jsonb_array_elements(rows) as r
  on conflict (id) do update set
    title           = excluded.title,
    company         = excluded.company,
    url             = excluded.url,
    location        = excluded.location,
    comp            = excluded.comp,
    posted          = excluded.posted,
    last_seen       = excluded.last_seen,
    fit_score       = excluded.fit_score,
    fit_rationale   = excluded.fit_rationale,
    red_flags       = excluded.red_flags,
    snippet         = excluded.snippet,
    company_summary = excluded.company_summary,
    company_remote  = excluded.company_remote,
    company_hq      = excluded.company_hq
  returning 1
)
select coalesce(count(*), 0)::int from up;
$$;

-- Only the pipeline (service role) calls this; the dashboard edits its own
-- fields through PostgREST directly.
revoke execute on function public.jobops_upsert_discovery(jsonb) from public, anon, authenticated;
grant execute on function public.jobops_upsert_discovery(jsonb) to service_role;
