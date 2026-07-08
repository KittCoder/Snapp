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
   - Start command: `gunicorn model:app`
   - Health check path: `/health`
4. Set these environment variables in Render:
   - `OPENAI_API_KEY`: your OpenAI API key
   - `FDC_API_KEY`: your USDA FoodData Central API key
   - `APIFY_API_TOKEN`: your Apify API token for running the Trader Joe's scraper
   - `CORS_ORIGINS`: `https://snapp-1d5j.vercel.app`

Optional:
   - `APIFY_TRADER_JOES_ACTOR_ID`: defaults to `merry_arctic~trader-joes-scraper`
   - `APIFY_TRADER_JOES_STORE_NUMBER`: local/manual scraper fallback only; app users store their selected number in Supabase
   - `APIFY_TRADER_JOES_CRAWL_URL`: optional Trader Joe's category URL for a narrower manual scrape
   - `APIFY_TRADER_JOES_MAX_PRODUCTS`: defaults to `500`
 
Render injects `PORT` automatically. Gunicorn handles the hosted service process.

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

## Trader Joe's Price Data

The backend loads [Model/data.json](/Users/2027kstarkie/Desktop/SNAPP/Model/data.json:1) first for grocery products and prices. If that file has no products, it falls back to the demo grocery database.

Refresh Trader Joe's pricing once or twice a week:

```sh
cd Model
python scraper.py
```

The scraper runs the Apify Trader Joe's actor, normalizes the returned dataset into SNAPP's grocery product format, and writes product names, prices, sale prices when present, `on_sale`, package sizes, stock flags, tags, SKUs, and source URLs to `data.json`. If Apify returns no usable products, the scraper exits without replacing the existing pricing file with an empty dataset.
 
