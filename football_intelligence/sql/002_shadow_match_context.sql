-- Adds human-readable match metadata and the Gemini opinion to existing
-- Football Intelligence shadow snapshots. Safe to run more than once.

alter table public.football_intelligence_shadow_snapshots
    add column if not exists home_team text,
    add column if not exists away_team text,
    add column if not exists league_name text,
    add column if not exists kickoff timestamptz,
    add column if not exists gemini_text text;

create index if not exists idx_fi_shadow_home_away
    on public.football_intelligence_shadow_snapshots (home_team, away_team);
