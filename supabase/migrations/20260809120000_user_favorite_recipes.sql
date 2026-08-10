create table if not exists public.user_favorite_recipes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  recipe_key text not null,
  recipe_name text not null,
  recipe_data jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_favorite_recipes_user_recipe_key unique (user_id, recipe_key)
);

create index if not exists user_favorite_recipes_user_id_created_at_idx
  on public.user_favorite_recipes (user_id, created_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists user_favorite_recipes_set_updated_at on public.user_favorite_recipes;
create trigger user_favorite_recipes_set_updated_at
before update on public.user_favorite_recipes
for each row execute function public.set_updated_at();

alter table public.user_favorite_recipes enable row level security;

drop policy if exists "Users can read their favorite recipes"
  on public.user_favorite_recipes;
create policy "Users can read their favorite recipes"
  on public.user_favorite_recipes
  for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert their favorite recipes"
  on public.user_favorite_recipes;
create policy "Users can insert their favorite recipes"
  on public.user_favorite_recipes
  for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can update their favorite recipes"
  on public.user_favorite_recipes;
create policy "Users can update their favorite recipes"
  on public.user_favorite_recipes
  for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users can delete their favorite recipes"
  on public.user_favorite_recipes;
create policy "Users can delete their favorite recipes"
  on public.user_favorite_recipes
  for delete
  using (auth.uid() = user_id);
