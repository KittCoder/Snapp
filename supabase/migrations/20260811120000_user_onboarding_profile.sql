create table if not exists public.user_info (
  id uuid primary key references auth.users(id) on delete cascade,
  username text,
  zip_code text,
  household_size integer not null default 1,
  budget numeric,
  dietary_preference text not null default 'balanced',
  dietary_restrictions text not null default '',
  dietary_preferences text[] not null default '{}',
  onboarding_completed boolean not null default false,
  notifications_enabled boolean not null default true,
  store_number text,
  store_name text,
  store_address text,
  store_website text,
  store_distance_miles numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.user_info
  add column if not exists username text,
  add column if not exists zip_code text,
  add column if not exists household_size integer not null default 1,
  add column if not exists budget numeric,
  add column if not exists dietary_preference text not null default 'balanced',
  add column if not exists dietary_restrictions text not null default '',
  add column if not exists dietary_preferences text[] not null default '{}',
  add column if not exists onboarding_completed boolean not null default false,
  add column if not exists notifications_enabled boolean not null default true,
  add column if not exists store_number text,
  add column if not exists store_name text,
  add column if not exists store_address text,
  add column if not exists store_website text,
  add column if not exists store_distance_miles numeric,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

update public.user_info
set
  household_size = coalesce(household_size, 1),
  dietary_preference = coalesce(dietary_preference, 'balanced'),
  dietary_restrictions = coalesce(dietary_restrictions, ''),
  dietary_preferences = coalesce(dietary_preferences, '{}'),
  onboarding_completed = coalesce(onboarding_completed, false),
  notifications_enabled = coalesce(notifications_enabled, true),
  created_at = coalesce(created_at, now()),
  updated_at = coalesce(updated_at, now());

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'user_info_household_size_check'
      and conrelid = 'public.user_info'::regclass
  ) then
    alter table public.user_info
      add constraint user_info_household_size_check
      check (household_size between 1 and 20);
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'user_info_zip_code_check'
      and conrelid = 'public.user_info'::regclass
  ) then
    alter table public.user_info
      add constraint user_info_zip_code_check
      check (zip_code is null or zip_code = '' or zip_code ~ '^[0-9]{5}$');
  end if;
end $$;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists user_info_set_updated_at on public.user_info;
create trigger user_info_set_updated_at
before update on public.user_info
for each row execute function public.set_updated_at();

alter table public.user_info enable row level security;

drop policy if exists "Users can read their user info"
  on public.user_info;
create policy "Users can read their user info"
  on public.user_info
  for select
  using (auth.uid() = id);

drop policy if exists "Users can insert their user info"
  on public.user_info;
create policy "Users can insert their user info"
  on public.user_info
  for insert
  with check (auth.uid() = id);

drop policy if exists "Users can update their user info"
  on public.user_info;
create policy "Users can update their user info"
  on public.user_info
  for update
  using (auth.uid() = id)
  with check (auth.uid() = id);
