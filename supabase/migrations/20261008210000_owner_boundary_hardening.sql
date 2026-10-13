-- Review/apply in Supabase; this file does not assert deployed policy state.
begin;
create table if not exists public.user_pantry_items (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 name text not null, quantity text not null,
 created_at timestamptz not null default now()
);
create table if not exists public.user_stores (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 store_key text not null, name text not null, address text,
 latitude double precision, longitude double precision, website text,
 distance_miles double precision, created_at timestamptz not null default now(),
 unique(user_id,store_key)
);
create table if not exists public.user_scheduled_meals (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 meal_name text not null, scheduled_day text not null, meal_data jsonb not null,
 created_at timestamptz not null default now()
);
-- A restrictive policy prevents any older permissive policy from widening ownership.
do $$
declare table_name text; owner_column text;
begin
 foreach table_name in array array['user_info','user_favorite_recipes','user_pantry_items','user_stores','user_scheduled_meals'] loop
  owner_column := case when table_name='user_info' then 'id' else 'user_id' end;
  execute format('alter table public.%I enable row level security',table_name);
  execute format('alter table public.%I force row level security',table_name);
  execute format('revoke all on public.%I from anon',table_name);
  execute format('grant select, insert, update, delete on public.%I to authenticated',table_name);
  execute format('drop policy if exists snapp_owner_boundary on public.%I',table_name);
  execute format('drop policy if exists snapp_owner_access on public.%I',table_name);
  execute format('create policy snapp_owner_boundary on public.%I as restrictive for all to authenticated using ((select auth.uid()) = %I) with check ((select auth.uid()) = %I)',table_name,owner_column,owner_column);
  execute format('create policy snapp_owner_access on public.%I for all to authenticated using ((select auth.uid()) = %I) with check ((select auth.uid()) = %I)',table_name,owner_column,owner_column);
 end loop;
end $$;
-- Feature catalogs are not accessed by browser code. Deny REST access by default.
alter table public.canonical_ingredients enable row level security;
alter table public.ingredient_aliases enable row level security;
alter table public.grocery_product_features enable row level security;
revoke all on public.canonical_ingredients,public.ingredient_aliases,public.grocery_product_features from anon,authenticated;
commit;
