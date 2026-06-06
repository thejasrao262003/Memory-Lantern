-- Memory Lantern — Supabase schema
-- Run this in the Supabase SQL Editor (Dashboard → SQL → New query).
-- The app connects with the supabase-py client library using the SERVICE-ROLE
-- key (server-side), so Row Level Security is bypassed by the backend.

-- ---------------------------------------------------------------------------
-- Reaction log: one row per caregiver reaction to a scene.
-- ---------------------------------------------------------------------------
create table if not exists public.reactions (
    id            bigint generated always as identity primary key,
    session_id    text        not null,
    scene_number  int         not null,
    reaction      text        not null check (reaction in ('smiled', 'unsettled', 'asleep')),
    notes         text        default '',
    reaction_date date        not null default current_date,
    created_at    timestamptz not null default now()
);

create index if not exists reactions_session_date_idx
    on public.reactions (session_id, reaction_date);

-- ---------------------------------------------------------------------------
-- Story metadata: one row per generated storybook (no photos, no full text).
-- ---------------------------------------------------------------------------
create table if not exists public.stories (
    id                  bigint generated always as identity primary key,
    session_id          text        not null,
    person_name         text        default '',
    scene_count         int         default 0,
    emotional_beats     jsonb       default '[]'::jsonb,
    adaptation_weights  jsonb       default '{}'::jsonb,
    created_at          timestamptz not null default now()
);

create index if not exists stories_session_idx on public.stories (session_id);

-- ---------------------------------------------------------------------------
-- Keep RLS ON (default). The backend uses the service-role key which bypasses
-- RLS; no anon policies are added, so the data is not publicly readable.
-- ---------------------------------------------------------------------------
alter table public.reactions enable row level security;
alter table public.stories   enable row level security;

-- ---------------------------------------------------------------------------
-- Object storage: create a bucket named "Memory-Lantern" for the generated assets.
-- Easiest via Dashboard → Storage → New bucket → name "Memory-Lantern".
-- (If you want shareable links without signing, mark it Public.) Names are
-- case-sensitive and must match app/storage/supabase_client.py (ASSET_BUCKET).
-- Or uncomment to create it from SQL:
-- insert into storage.buckets (id, name, public)
-- values ('Memory-Lantern', 'Memory-Lantern', true)
-- on conflict (id) do nothing;
