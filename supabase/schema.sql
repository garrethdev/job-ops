-- jobops_leads table contract, dumped from the live Supabase project
-- (xknavmpmekmxfvlrtjnk) via information_schema + pg_constraint on 2026-08-19.
-- Version-controlled reference only — NOT applied by tooling. If the live table
-- changes, re-dump and update this file in the same commit as the code change.
--
-- Ownership split (enforced by public.jobops_upsert_discovery, see
-- migrations/20260819_jobops_upsert_discovery.sql):
--   pipeline-owned discovery: title, company, url, location, comp, posted,
--     last_seen, fit_score, fit_rationale, red_flags, snippet,
--     company_summary, company_remote, company_hq
--   dashboard-owned workflow: status, stage, notes, contact, warm,
--     outreached_at, updated_at
--   insert-only provenance:   id, schema_version, lane, source, source_detail,
--     first_seen

create table public.jobops_leads (
  id              text not null,
  schema_version  integer not null default 1,
  lane            text,
  source          text,
  source_detail   text,
  title           text not null,
  company         text not null,
  url             text,
  location        text,
  comp            text,
  posted          text,
  first_seen      timestamptz,
  last_seen       timestamptz,
  fit_score       integer default 0,
  fit_rationale   text,
  red_flags       jsonb default '[]'::jsonb,
  contact         jsonb default '{}'::jsonb,
  notes           text default ''::text,
  status          text default 'new'::text,
  snippet         text,
  updated_at      timestamptz default now(),
  outreached_at   timestamptz,
  stage           text not null default 'new'::text,
  warm            boolean not null default false,
  company_summary text default ''::text,
  company_remote  text default ''::text,
  company_hq      text default ''::text,

  constraint jobops_leads_pkey primary key (id),
  constraint jobops_leads_stage_chk check (stage = any (array['new'::text, 'wip'::text, 'reached_out'::text]))
);
