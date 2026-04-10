-- Melbourne Coffee Guide - Supabase schema
--
-- This file defines the database side of the migration:
--   1) cafes: canonical cafe content imported from data.json/data.csv
--   2) cafe_likes: viewer likes, one per viewer identity per cafe
--   3) cafe_comments: short viewer comments with moderation status
--
-- Notes:
-- - Uses snake_case column names.
-- - Designed for Supabase Postgres.
-- - Public frontend can read cafes; feedback writes can be enabled via RLS insert policies.
-- - The import script uses cafes.slug as the stable upsert key.

create extension if not exists pgcrypto;

-- Admin allowlist for authenticated management.
create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default timezone('utc', now())
);

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.admin_users au
    where au.user_id = auth.uid()
  );
$$;

-- Auto-update helper for updated_at columns.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

-- Canonical cafe data.
create table if not exists public.cafes (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  location text not null,
  suburb text not null,
  active boolean not null default true,
  spectrum numeric(3,1) not null check (spectrum >= 0 and spectrum <= 5),
  price smallint not null check (price >= 1 and price <= 5),
  atmosphere text not null,
  description text not null,
  one_liner text not null,
  tags text not null,
  image text,
  image_url text,
  image_path text,
  rating numeric(3,1) not null check (rating >= 0 and rating <= 5),
  reviews integer not null default 0 check (reviews >= 0),
  lat double precision,
  lng double precision,
  signature text,
  last_scraped_at timestamptz,
  updated_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists cafes_suburb_idx on public.cafes (suburb);
create index if not exists cafes_location_idx on public.cafes (location);
create index if not exists cafes_spectrum_idx on public.cafes (spectrum);
create index if not exists cafes_price_idx on public.cafes (price);
create index if not exists cafes_rating_idx on public.cafes (rating desc);
create index if not exists cafes_created_at_idx on public.cafes (created_at desc);
create index if not exists cafes_lat_lng_idx on public.cafes (lat, lng);

create trigger set_cafes_updated_at
before update on public.cafes
for each row
execute function public.set_updated_at();

-- Viewer likes.
-- viewer_id is a browser-generated or app-generated opaque identifier.
-- session_id is optional and can be used for server/session correlation.
-- viewer_key is a generated stable uniqueness key so a viewer can like a cafe once.
create table if not exists public.cafe_likes (
  id uuid primary key default gen_random_uuid(),
  cafe_id uuid not null references public.cafes(id) on delete cascade,
  viewer_id text,
  session_id uuid,
  viewer_key text generated always as (coalesce(viewer_id, session_id::text)) stored,
  source text not null default 'web',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint cafe_likes_viewer_present check (viewer_id is not null or session_id is not null),
  constraint cafe_likes_one_per_viewer unique (cafe_id, viewer_key)
);

create index if not exists cafe_likes_cafe_id_idx on public.cafe_likes (cafe_id);
create index if not exists cafe_likes_viewer_key_idx on public.cafe_likes (viewer_key);
create index if not exists cafe_likes_created_at_idx on public.cafe_likes (created_at desc);

create trigger set_cafe_likes_updated_at
before update on public.cafe_likes
for each row
execute function public.set_updated_at();

-- Viewer comments. Pending moderation by default.
create table if not exists public.cafe_comments (
  id uuid primary key default gen_random_uuid(),
  cafe_id uuid not null references public.cafes(id) on delete cascade,
  viewer_id text,
  session_id uuid,
  viewer_key text generated always as (coalesce(viewer_id, session_id::text)) stored,
  display_name text,
  comment_text text not null,
  status text not null default 'pending' check (status in ('pending', 'approved', 'hidden')),
  source text not null default 'web',
  moderation_note text,
  moderated_by text,
  moderated_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint cafe_comments_viewer_present check (viewer_id is not null or session_id is not null),
  constraint cafe_comments_text_length check (char_length(trim(comment_text)) between 1 and 140),
  constraint cafe_comments_one_per_viewer unique (cafe_id, viewer_key)
);

create index if not exists cafe_comments_cafe_id_idx on public.cafe_comments (cafe_id);
create index if not exists cafe_comments_status_idx on public.cafe_comments (status);
create index if not exists cafe_comments_created_at_idx on public.cafe_comments (created_at desc);
create index if not exists cafe_comments_viewer_key_idx on public.cafe_comments (viewer_key);

create trigger set_cafe_comments_updated_at
before update on public.cafe_comments
for each row
execute function public.set_updated_at();

-- Public-facing rollup for cards, map markers, and comments counts.
create or replace view public.cafes_with_feedback as
select
  c.*,
  coalesce(l.like_count, 0) as like_count,
  coalesce(cm.approved_comment_count, 0) as approved_comment_count,
  cm.latest_approved_comment_at,
  cm.latest_approved_comment_text
from public.cafes c
left join (
  select cafe_id, count(*)::integer as like_count
  from public.cafe_likes
  group by cafe_id
) l on l.cafe_id = c.id
left join (
  select
    cafe_id,
    count(*) filter (where status = 'approved')::integer as approved_comment_count,
    max(created_at) filter (where status = 'approved') as latest_approved_comment_at,
    (array_agg(comment_text order by created_at desc) filter (where status = 'approved'))[1] as latest_approved_comment_text
  from public.cafe_comments
  group by cafe_id
) cm on cm.cafe_id = c.id;

comment on table public.cafes is 'Canonical cafe dataset imported from the repo data.json / data.csv source files.';
comment on table public.cafe_likes is 'Viewer likes. Intended to support one like per viewer identity per cafe.';
comment on table public.cafe_comments is 'Short viewer comments with moderation status. Insert as pending, approve through moderation tooling.';
comment on view public.cafes_with_feedback is 'Cafe rows joined with aggregate feedback counts for frontend display.';

-- RLS guidance / starter policies:
-- - Cafes should be publicly readable.
-- - Likes should allow anonymous insert if the frontend uses Supabase anon key, but raw reads can stay restricted.
-- - Comments should allow anonymous insert as pending, with public read limited to approved rows or the aggregate view.
-- - Update/delete of feedback rows should generally be done only by service-role/admin tooling.
-- - The existing scraper/enrichment tools can now write to cafes via Supabase instead of Google Sheets.

alter table public.cafes enable row level security;
alter table public.cafe_likes enable row level security;
alter table public.cafe_comments enable row level security;

grant select, insert, update, delete on public.cafes to authenticated;
grant select, insert, update, delete on public.admin_users to authenticated;

grant select on public.cafes to anon, authenticated;
grant select on public.cafes_with_feedback to anon, authenticated;
grant select, insert, update, delete on public.cafe_likes to anon, authenticated;
grant select, insert, update, delete on public.cafe_comments to anon, authenticated;
grant select on public.cafe_comments to anon, authenticated;

drop policy if exists "public read cafes" on public.cafes;
drop policy if exists "admin read all cafes" on public.cafes;
drop policy if exists "admin manage cafes" on public.cafes;

create policy "public read active cafes"
  on public.cafes
  for select
  using (active = true);

create policy "admin read all cafes"
  on public.cafes
  for select
  using (is_admin());

create policy "admin manage cafes"
  on public.cafes
  for all
  using (is_admin())
  with check (is_admin());

-- Allow public like submission if you choose to use the anon key from the browser.
do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'cafe_likes' and policyname = 'public insert cafe likes'
  ) then
    create policy "public insert cafe likes"
      on public.cafe_likes
      for insert
      with check (viewer_id is not null or session_id is not null);
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'cafe_likes' and policyname = 'public update own cafe likes'
  ) then
    create policy "public update own cafe likes"
      on public.cafe_likes
      for update
      using (viewer_id is not null or session_id is not null)
      with check (viewer_id is not null or session_id is not null);
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'cafe_likes' and policyname = 'public select cafe likes'
  ) then
    create policy "public select cafe likes"
      on public.cafe_likes
      for select
      using (true);
  end if;
end $$;

-- Public can read like counts and raw likes.

-- Allow public comment submission as pending.
do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'cafe_comments' and policyname = 'public insert cafe comments'
  ) then
    create policy "public insert cafe comments"
      on public.cafe_comments
      for insert
      with check (
        (viewer_id is not null or session_id is not null)
        and status = 'pending'
        and char_length(trim(comment_text)) between 1 and 140
      );
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'cafe_comments' and policyname = 'public update own cafe comments'
  ) then
    create policy "public update own cafe comments"
      on public.cafe_comments
      for update
      using (viewer_id is not null or session_id is not null)
      with check (viewer_id is not null or session_id is not null);
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'cafe_comments' and policyname = 'public delete own cafe comments'
  ) then
    create policy "public delete own cafe comments"
      on public.cafe_comments
      for delete
      using (viewer_id is not null or session_id is not null);
  end if;
end $$;

-- Public can read approved comments only.
do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'cafe_comments' and policyname = 'public read approved cafe comments'
  ) then
    create policy "public read approved cafe comments"
      on public.cafe_comments
      for select
      using (status = 'approved' or viewer_id is not null or session_id is not null);
  end if;
end $$;

-- Keep update/delete off-limits for anon. Use service role or admin-only tooling for moderation.
