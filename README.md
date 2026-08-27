# SNAPP 
  
A web application that generates healthy recipes for SNAP benefits users, using AI on the backend. Checks local grocery store availability.
           
## Backend Deployment on Render 
 
The backend is configured for Render with [render.yaml](/Users/2027kstarkie/Desktop/SNAPP/render.yaml:1).
 
1. Create a new Render Blueprint from this GitHub repository, or create a Web Service manually.
2. If using the blueprint, Render reads `render.yaml` automatically.
3. If creating the service manually, use these settings:
   - Root directory: `Model`
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 model:app`
   - Health check path: `/health`
4. Set these environment variables in Render:
   - `OPENAI_API_KEY`: your OpenAI API key
   - `FDC_API_KEY`: your USDA FoodData Central API key
   - `APIFY_API_TOKEN`: your Apify API token for running the Trader Joe's scraper
   - `CORS_ORIGINS`: `https://snapp-1d5j.vercel.app`
   - `SNAPP_ADMIN_TOKEN`: random secret used for protected internal diagnostics/review endpoints
   - `SNAPP_ENV`: `production`
   - `SNAPP_LOG_FORMAT`: `json`

Optional:
   - `APIFY_TRADER_JOES_ACTOR_ID`: defaults to `merry_arctic~trader-joes-scraper`
   - `APIFY_TRADER_JOES_STORE_NUMBER`: local/manual scraper fallback only; app users store their selected number in Supabase
   - `APIFY_TRADER_JOES_CRAWL_URL`: optional Trader Joe's category URL for a narrower manual scrape
   - `APIFY_TRADER_JOES_MAX_PRODUCTS`: defaults to `500`
 
Render injects `PORT` automatically. Gunicorn handles the hosted service process.

Use one worker by default. The local embedding model and vector index are loaded per worker, so multiple workers multiply memory usage. The recommended deployment shape is one worker with two threads until measured Render memory shows more workers are safe.

The backend also accepts Vercel deployment URLs that match this project, such as:

```text
https://snapp-1d5j-b7g466kuj-snapp-app.vercel.app
```

## Frontend on Vercel

After Render deploys the backend, copy the Render service URL and set it in [Web/index.html](/Users/2027kstarkie/Desktop/SNAPP/Web/index.html:7):

```html
<meta name="snapp-api-base-url" content="https://your-render-service.onrender.com" />
```

Then redeploy the static frontend to Vercel. The current allowed production frontend origin is:

```text
https://snapp-1d5j.vercel.app
```

## Supabase Auth

The frontend currently uses a temporary username/password flow backed by Supabase Auth. Usernames are converted into internal `@snapp.local` email addresses before calling Supabase. Personalized settings are stored in `public.user_info` with the row `id` matching the logged-in Auth user id. The app saves `zip_code`, `household_size`, `budget`, `dietary_preference`, `dietary_restrictions`, and `notifications_enabled`; `created_at` and `updated_at` are managed by the database.

Pantry items are stored in `public.user_pantry_items` and sent to the dish generator so meal ideas can account for food the user already has.

Selected stores are stored per user in `public.user_stores`.

Selected dishes are stored per user in `public.user_scheduled_meals`. The frontend stores the chosen recipe, recipe ingredients, and matched grocery ingredients in `meal_data` so the weekly calendar can reopen the full recipe without regenerating it.

```sql
create table if not exists public.user_scheduled_meals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  meal_name text not null,
  scheduled_day text not null,
  meal_data jsonb not null,
  created_at timestamptz not null default now()
);

alter table public.user_scheduled_meals enable row level security;

create policy "Users can read their scheduled meals"
  on public.user_scheduled_meals
  for select
  using (auth.uid() = user_id);

create policy "Users can insert their scheduled meals"
  on public.user_scheduled_meals
  for insert
  with check (auth.uid() = user_id);

create policy "Users can delete their scheduled meals"
  on public.user_scheduled_meals
  for delete
  using (auth.uid() = user_id);
```

The nearest Trader Joe's store number is resolved from the ZIP code a user enters in My stores and stored on `public.user_info.store_number`. Add these columns to `public.user_info` before using the Trader Joe's scraper flow:

```sql
alter table public.user_info
  add column if not exists store_number text,
  add column if not exists store_name text,
  add column if not exists store_address text,
  add column if not exists store_website text,
  add column if not exists store_distance_miles numeric;
```

In the Supabase dashboard, enable Email auth and disable email confirmation while this username prototype is active. Password reset emails will not work until the app moves to real email addresses.

## Local Backend

```sh
cd Model
pip install -r requirements.txt
OPENAI_API_KEY=your_key_here FDC_API_KEY=your_fdc_key_here python model.py
```

The API runs on `http://localhost:5000` locally.

Recipe search uses the user's query against a small allowlist of real web recipe sites, respects `robots.txt`, parses `schema.org/Recipe` JSON-LD metadata, and links to the source for full instructions. Spoonacular is disabled by default.

## Public Domain Recipe Data

[Model/recipes.json](/Users/2027kstarkie/Desktop/SNAPP/Model/recipes.json:1) contains recipes scraped from Public Domain Recipes with names, parsed ingredient quantities, equipment, categories, and instructions.

Refresh the recipe file with:

```sh
cd Model
python recipe_scraper.py --max-pages 5 --max-recipes 100
```

The Dishes backend searches [Model/all_recipes_search.sqlite](/Users/2027kstarkie/Desktop/SNAPP/Model/all_recipes_search.sqlite:1), a generated SQLite FTS database built from `all_recipes.json`. Regenerate it after changing recipe data:

```sh
cd Model
python build_recipe_search_db.py
```

## Trader Joe's Price Data

The backend loads [Model/data.json](/Users/2027kstarkie/Desktop/SNAPP/Model/data.json:1) first for grocery products and prices. If that file has no products, it falls back to the demo grocery database.

Refresh Trader Joe's pricing once or twice a week:

```sh
cd Model
python scraper.py
```

The scraper runs the Apify Trader Joe's actor, normalizes the returned dataset into SNAPP's grocery product format, and writes product names, prices, sale prices when present, `on_sale`, package sizes, stock flags, tags, SKUs, and source URLs to `data.json`. If Apify returns no usable products, the scraper exits without replacing the existing pricing file with an empty dataset.

## Ingredient Matching Foundation

The ingredient parser and Morton Williams feature extractor live in `Model/ingredient_normalization.py`.

Apply the Supabase schema migration from:

```sh
supabase/migrations/20260715180000_ingredient_matching_foundation.sql
```

Extract deterministic Morton Williams product features from `Model/database.merged.json`:

```sh
python3 Model/normalize_morton_williams_products.py \
  --input Model/database.merged.json \
  --output Model/morton_williams_product_features.json \
  --uncertain-log Model/morton_williams_uncertain_products.csv \
  --invalid-log Model/morton_williams_invalid_or_noise.csv
```

The command is safe to rerun. It does not mutate `database.merged.json`; uncertain canonical ingredient assignments are logged instead of guessed.

Run the ingredient foundation tests:

```sh
python3 -m unittest discover -s Model/tests -v
```

Build the local Morton Williams product embedding index:

```sh
python3 Model/build_product_embedding_index.py \
  --features Model/morton_williams_product_features.json \
  --index-dir Model/morton_williams_vector_index \
  --model BAAI/bge-small-en-v1.5 \
  --batch-size 64
```

The first run downloads and loads the local `sentence-transformers` model. Later runs reuse unchanged vectors by comparing each product's embedding source-text hash.

The build also writes `Model/runtime_artifact_manifest.json`, which records the feature hash, vector index hash, row counts, embedding model, matcher version, optimizer version, override version, and build command. Startup and `/ready` validate this manifest against the active artifacts.

For an offline smoke test that does not download the model:

```sh
python3 Model/build_product_embedding_index.py \
  --features Model/morton_williams_product_features.json \
  --index-dir Model/morton_williams_vector_index_test \
  --deterministic-test-embeddings
```

Local candidate retrieval is available through the reusable Python service:

```python
from product_retrieval import retrieve_product_candidates

result = retrieve_product_candidates("unsalted butter", limit=30)
```

For local development only, Flask exposes:

```sh
curl "http://localhost:5000/dev/product-candidates?ingredient=unsalted%20butter&limit=10"
```

The development endpoint is disabled when `SNAPP_ENV=production` or `FLASK_ENV=production`.

Run final compatibility matching:

```python
from product_compatibility import match_recipe_ingredient

result = match_recipe_ingredient("unsalted butter", limit=5)
```

Development-only matcher endpoint:

```sh
curl "http://localhost:5000/dev/product-match?ingredient=unsalted%20butter&limit=5"
```

Manual overrides live in `Model/product_match_overrides.json`. The file supports:

- `forbidden_products`
- `forced_matches`
- `approved_matches`
- `canonical_overrides`
- `aliases`
- `substitutions`
- `incompatible_families`

Each override entry should include a `query` and the relevant `product_id`, `canonical`, `alias`, or `family` field. Overrides are loaded lazily, do not mutate source product data, and use deterministic precedence: forbidden, forced, approved, aliases/canonical overrides, then automated ranking.

## Production Artifact Map

Render root directory: `Model`

Runtime files required by the Morton Williams matcher:

- `morton_williams_product_features.json`: normalized product feature artifact, committed to Git.
- `morton_williams_vector_index/metadata.json` and `morton_williams_vector_index/embeddings.npy`: local semantic index, committed to Git as the default production artifact strategy.
- `runtime_artifact_manifest.json`: manifest for the active product/features/index/override set.
- `product_match_overrides.json`: deterministic review overrides, committed to Git for durable production behavior.
- `all_recipes.json`, `all_recipes_search.sqlite`, `recipes.json`, `USDA recipes.json`: recipe data and search artifacts, committed to Git.

`database.merged.json` is ignored and is not required at runtime. It is the source input for refresh jobs. Render does not automatically obtain a new Morton Williams source file; weekly refresh output must be run locally or in a controlled job, validated, and then promoted by committing the generated runtime artifacts. The current default is Git-committed runtime artifacts because the update cadence is low, the active vector index is modest in size, deployment is simple, and rollback is a normal Git redeploy.

Hugging Face model files are downloaded by `sentence-transformers` when the model first loads. Render build/runtime cache may reuse them, but readiness does not assume the cache exists.

## Health, Readiness, And Diagnostics

- `/health` only confirms the Flask process is alive.
- `/ready` requires warmup, manifest validation, feature/index alignment, model/index compatibility, and a smoke matcher query. It returns `503` for warming, failed, or unavailable semantic readiness. Lexical-only mode is only treated as ready when `SNAPP_ALLOW_LEXICAL_ONLY=1`.
- `/internal/diagnostics` and `/internal/metrics` require `X-SNAPP-Admin-Token: <SNAPP_ADMIN_TOKEN>`.

Protected review endpoints:

```sh
curl -H "X-SNAPP-Admin-Token: $SNAPP_ADMIN_TOKEN" \
  "$BASE_URL/internal/review/queues?limit=50"

curl -H "X-SNAPP-Admin-Token: $SNAPP_ADMIN_TOKEN" \
  "$BASE_URL/internal/review/inspect?ingredient=unsalted%20butter"
```

Override mutation endpoint:

```sh
curl -X POST "$BASE_URL/internal/review/overrides" \
  -H "Content-Type: application/json" \
  -H "X-SNAPP-Admin-Token: $SNAPP_ADMIN_TOKEN" \
  -d '{"action":"define_alias","query":"caster sugar","canonical":"sugar","actor":"reviewer","reason":"common recipe alias"}'
```

Supported actions are `approve_match`, `forbid_product`, `define_alias`, `assign_canonical`, `acceptable_substitution`, `mark_incompatible_family`, and `remove`. Mutations write a backup and append `Model/product_match_override_audit.jsonl`, then reload overrides and clear caches. On Render's ephemeral filesystem, local override mutations are not durable unless the changed files are committed or a persistent artifact store is configured.

Cache control:

```sh
curl -X POST "$BASE_URL/internal/cache/clear" \
  -H "Content-Type: application/json" \
  -H "X-SNAPP-Admin-Token: $SNAPP_ADMIN_TOKEN" \
  -d '{}'
```

## Morton Williams Refresh Workflow

Use the safe refresh command after obtaining a new `database.merged.json`:

```sh
python3 Model/refresh_morton_williams_artifacts.py \
  --source Model/database.merged.json \
  --dry-run

python3 Model/refresh_morton_williams_artifacts.py \
  --source Model/database.merged.json
```

The command validates the source schema, backs up active artifacts under `Model/artifact_rollbacks/`, normalizes features, regenerates uncertainty/noise reports, rebuilds the vector index, writes a manifest, validates the staged set, runs the unit suite and matcher evaluation, then atomically promotes the staged files. Failed refreshes leave the active artifact set unchanged.

Use `--force-rebuild` to ignore existing vectors and `--deterministic-test-embeddings` only for offline smoke tests.

After refresh, run:

```sh
python3 Model/artifact_manifest.py
python3 -m unittest discover -s Model/tests -v
python3 Model/evaluate_product_matching.py --fixture Model/evaluation/product_match_cases.jsonl
python3 -m compileall -q Model
```

## Deployment Verification

Verify a local or deployed instance:

```sh
python3 Model/verify_deployment.py --base-url http://localhost:5000

python3 Model/verify_deployment.py \
  --base-url https://your-render-service.onrender.com \
  --admin-token "$SNAPP_ADMIN_TOKEN"
```

The command checks `/health`, `/ready`, a repeated `/dishes` smoke request, response shape, hard-conflict absence, and protected diagnostics when a token is supplied.

## Rollback

Code rollback: redeploy a prior Git commit in Render or revert the commit and redeploy.

Product artifact rollback: restore the previous files from `Model/artifact_rollbacks/<timestamp>/` or redeploy a prior Git commit containing the previous manifest/features/index bundle.

Override rollback: restore `Model/product_match_overrides.json` from its `.bak` file, an audit-log revision, or a prior Git commit. Then clear caches through `/internal/cache/clear` or restart the service.

Failed refresh: the refresh script uses a staging directory and does not promote partial artifacts. The previous active artifact set remains in place.

Run the checked-in matcher evaluation:

```sh
python3 Model/evaluate_product_matching.py \
  --fixture Model/evaluation/product_match_cases.jsonl
```
 
