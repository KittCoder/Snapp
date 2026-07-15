create table if not exists public.canonical_ingredients (
  id uuid primary key default gen_random_uuid(),
  canonical_name text not null unique,
  category text,
  subcategory text,
  default_form text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.ingredient_aliases (
  id uuid primary key default gen_random_uuid(),
  alias_normalized text not null unique,
  canonical_ingredient_id uuid not null references public.canonical_ingredients(id) on delete cascade,
  source text not null default 'manual',
  confidence numeric(4, 3) not null default 1.0 check (confidence >= 0 and confidence <= 1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.grocery_product_features (
  product_id text primary key,
  normalized_name text not null,
  canonical_ingredient_id uuid references public.canonical_ingredients(id) on delete set null,
  brand text,
  category text,
  subcategory text,
  form text,
  fat_level text,
  salted_status text,
  sweetened_status text,
  freshness text,
  cut text,
  bone_status text,
  skin_status text,
  dietary_attributes text[] not null default '{}',
  package_quantity numeric,
  package_unit text,
  package_quantity_base numeric,
  base_unit text,
  feature_extraction_version text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists canonical_ingredients_name_idx
  on public.canonical_ingredients (canonical_name);

create index if not exists ingredient_aliases_canonical_ingredient_id_idx
  on public.ingredient_aliases (canonical_ingredient_id);

create index if not exists grocery_product_features_canonical_ingredient_id_idx
  on public.grocery_product_features (canonical_ingredient_id);

create index if not exists grocery_product_features_normalized_name_idx
  on public.grocery_product_features (normalized_name);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists canonical_ingredients_set_updated_at on public.canonical_ingredients;
create trigger canonical_ingredients_set_updated_at
before update on public.canonical_ingredients
for each row execute function public.set_updated_at();

drop trigger if exists ingredient_aliases_set_updated_at on public.ingredient_aliases;
create trigger ingredient_aliases_set_updated_at
before update on public.ingredient_aliases
for each row execute function public.set_updated_at();

drop trigger if exists grocery_product_features_set_updated_at on public.grocery_product_features;
create trigger grocery_product_features_set_updated_at
before update on public.grocery_product_features
for each row execute function public.set_updated_at();

insert into public.canonical_ingredients (canonical_name, category, subcategory, default_form)
values
  ('all-purpose flour', 'pantry', 'baking', null),
  ('powdered sugar', 'pantry', 'baking', 'powdered'),
  ('green onions', 'produce', 'alliums', 'fresh'),
  ('milk', 'dairy', 'milk', null),
  ('butter', 'dairy', 'butter', null),
  ('parsley', 'produce', 'herbs', 'fresh'),
  ('ground beef', 'meat', 'beef', 'ground'),
  ('heavy cream', 'dairy', 'cream', null),
  ('tomato paste', 'pantry', 'tomato products', 'paste'),
  ('baking powder', 'pantry', 'baking', null)
on conflict (canonical_name) do nothing;

insert into public.ingredient_aliases (alias_normalized, canonical_ingredient_id, source, confidence)
select alias.alias_normalized, ci.id, 'seed', alias.confidence
from (
  values
    ('ap flour', 'all-purpose flour', 1.0),
    ('a p flour', 'all-purpose flour', 1.0),
    ('plain flour', 'all-purpose flour', 0.95),
    ('all purpose flour', 'all-purpose flour', 1.0),
    ('confectioners sugar', 'powdered sugar', 1.0),
    ('confectioner sugar', 'powdered sugar', 1.0),
    ('icing sugar', 'powdered sugar', 0.95),
    ('scallions', 'green onions', 1.0),
    ('scallion', 'green onions', 1.0),
    ('spring onions', 'green onions', 0.95)
) as alias(alias_normalized, canonical_name, confidence)
join public.canonical_ingredients ci
  on ci.canonical_name = alias.canonical_name
on conflict (alias_normalized) do nothing;
