# Supabase store catalog handoff

The live store API last checked on November 10, 2026 exposes 12 C-Town catalogs and Morton Williams. The Food Bazaar extension is prepared locally; its production import still requires privileged Supabase access. Do not treat the local manifest or an import dry run as evidence that a location is live.

## Food Bazaar activation

The November 5 source snapshot contains 258,282 product/location records for 22 verified NYC locations. Twelve other directory locations have no exposed catalog and are excluded. Each promoted file is hash-pinned; records must carry the matching retailer location and item ID. Coordinates come from that location's captured retailer metadata. Existing C-Town and Morton Williams manifest entries are unchanged.

After deploying the expanded backend manifest, run the following from the repository root with server-only Supabase credentials configured:

```sh
.venv/bin/python scripts/import_store_catalog.py --dry-run --retailer food_bazaar
.venv/bin/python scripts/import_store_catalog.py --retailer food_bazaar
.venv/bin/python scripts/import_store_catalog.py --verify --retailer food_bazaar
```

The importer validates and atomically activates each location after its complete count matches. The database registry exposes only active versions that match the manifest, so deploying code before importing inventory preserves the existing stores. After activation, check `/api/stores` for all 35 catalogs and compare recipe prices at different Food Bazaar locations. Home rankings remain fixed to Morton Williams; Food Bazaar is available through Stores, Shopping, Budget, recipe pricing and store comparison after activation.

## Files and behavior

- `supabase/migrations/20261016000100_store_catalog.sql`: stores, inventory versions, products, indexes, recursive null-preserving updates, count-checked atomic activation, RLS and backend-only grants.
- `supabase/tests/store_catalog_security.sql`: deployed privilege/RLS assertions for an administrator to run.
- `scripts/import_store_catalog.py`: imports verified catalogs from the existing whitelist and the active Morton Williams artifact; `--retailer food_bazaar` imports only Food Bazaar. Batches 100 products, reports inserted/updated/skipped, and validates full counts before activation. Repeating an identical import skips unchanged products. No deletion or scraping.
- `Model/store_catalog_manifest.json`: small, source-version-pinned public metadata manifest for 35 approved inventories (12 C-Town, Morton Williams, and 22 Food Bazaar). Production uses imported database inventory and does not need the large local JSON files. A future inventory promotion must update this manifest from the validated source registry and re-import matching feature versions.
- `Model/supabase_store_catalog.py`: credential-safe server gateway, bounded database candidates, Redis caching, and request-local matching adapters. Inventory version IDs include exact source hash plus matcher/ontology/feature adapter fingerprint.
- `Model/store_comparison.py`: one additive request-catalog hook before the existing basket calculation.
- `Model/store_comparison_api.py`: backend selection and generic database-unavailable 503 responses.
- `Model/tests/test_supabase_store_catalog.py`: retrieval, isolation, versioning, cache, importer idempotency, null preservation, credential failure, production fallback and MW index-sharing checks.
- `scripts/verify_store_catalog.py`: current file baseline, bounded SQL parity and performance. SQLite is an explicitly labeled test adapter, never a production backend.
- `.env.example`, `Model/.env.example`: server inventory settings. Existing values are otherwise preserved.

Queries always restrict store and inventory version. They retrieve complete relevant ontology families, falling back to subfamily, semantic head and normalized-name retrieval when empty. The unchanged matcher performs every compatibility check and the unchanged optimizer determines purchases. Unknown heads do not cause broad catalog scans. Pools are bounded to 4,500 per ingredient and 6,000 distinct products per store/basket; exceeding either fails rather than silently dropping a potentially better product. The largest indexed family in the current rehearsal is 4,221 rows. Patty Melts uses 618–1,434 distinct candidate rows per store.

The existing local file implementation remains intact. Explicit `file` selects it; development `auto` falls back when Supabase is unavailable. The default is `file`, including in production, until an operator explicitly activates the database after live validation. Explicit production `auto` and explicit `supabase` require the database and fail closed rather than allocating every local catalog. Request-local builders are discarded; no complete inventory is retained by database catalog objects.

Redis TTL is 300 seconds. Keys include store ID, source inventory version, normalized ontology identity, matcher/ontology/feature fingerprint and overrides hash. Redis failure falls back to bounded database retrieval. Every comparison, including a completed-basket cache hit, rechecks each selected active version; expect one metadata query per selected store in addition to cold candidate queries. Candidate responses are paged at 900 rows to avoid Supabase's normal 1,000-row response ceiling.

Active Morton Williams source features remain byte-for-byte unchanged. Its existing semantic index/backend are shared when semantic mode is requested; candidate IDs remain restricted by the unchanged matcher. Recipe Chat, DealOptimizer and matcher gates were not edited. Local representative parity used lexical mode, consistent with the existing local review; live semantic-mode parity remains to be verified.

## Apply and import

Run from the repository root. Supply actual server values through your secret manager/environment; do not put them in commands, files, browser settings or Git:

```sh
export SUPABASE_URL='https://your-project.supabase.co'
# SUPABASE_SERVICE_ROLE_KEY: inject as a hidden server secret.
# SUPABASE_DB_URL: inject as a hidden admin Postgres connection string, for psql only.
psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20261016000100_store_catalog.sql
psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/tests/store_catalog_security.sql
.venv/bin/python scripts/import_store_catalog.py --report data/store_scrapes/audit/supabase_catalog/live_import.json
.venv/bin/python scripts/import_store_catalog.py --verify --report data/store_scrapes/audit/supabase_catalog/live_counts.json
```

Alternatively, apply the SQL and its security assertions in the Supabase SQL editor as an administrator. The importer itself needs only `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, with no browser credentials or direct Postgres driver. The migration creates no vectors, anonymous policies or browser CRUD grants. Inventory activation is a privileged transaction and requires an exact staged product count. Old versions and all local source files remain present.

Expected current counts: **81,998 C-Town + 10,010 Morton Williams = 92,008 products** across 13 inventories. Actual remote rows imported in this session: **0**. Dry-run `skipped` counts mean upload was skipped, not that matching remote rows were found.

## Real parity and latency verification

With local source artifacts available and the server credentials above injected:

```sh
.venv/bin/python scripts/verify_store_catalog.py --file-baseline --report data/store_scrapes/audit/supabase_catalog/current_file_baseline.json
.venv/bin/python scripts/verify_store_catalog.py --supabase --baseline data/store_scrapes/audit/supabase_catalog/current_file_baseline.json --samples 20 --report data/store_scrapes/audit/supabase_catalog/live_parity_performance.json
```

The parity check compares every output field, including basket IDs and product/deal details, excluding only elapsed time, basket latency and cache-hit status. It checks Patty Melts, Lamb in Pitas and Tuscan Salad across all 13 stores, plus the established rice/butter example across its four stores (43 comparisons). For reproducible cold-cache measurements, use a fresh Redis database dedicated to the rehearsal. Benchmark IDs bypass completed-basket caching; the second request measures that cache separately.

SQLite rehearsal commands, when Postgres is unavailable:

```sh
.venv/bin/python scripts/verify_store_catalog.py --sqlite /tmp/snapp-catalog-rehearsal.sqlite --prepare-sqlite --report /tmp/unused.json
REDIS_URL=redis://127.0.0.1:6379/1 .venv/bin/python scripts/verify_store_catalog.py --sqlite /tmp/snapp-catalog-rehearsal.sqlite --baseline data/store_scrapes/audit/supabase_catalog/current_file_baseline.json --samples 10 --report data/store_scrapes/audit/supabase_catalog/sqlite_rehearsal.json
```

The prepare command refuses to overwrite a database. This adapter tests retrieval and the real matching/optimization pipeline against indexed SQL; it does not execute the Postgres migration or emulate RLS, grants, HTTP or network latency.

## Render settings after live verification

Set on the backend service only:

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<server secret>
STORE_CATALOG_BACKEND=supabase
REDIS_URL=<existing trusted Redis connection URL>
SNAPP_ENV=production
```

Preserve existing rate-limit, CORS, recipe-search and application settings. `SUPABASE_DB_URL` is an operator migration credential, not required by Flask. No frontend environment or payload changes are required. Ship the new modules, manifest and matching feature dependency files with the same revision used for import. Do not switch Render until live counts, privileges, semantic behavior where enabled, parity and latency have been reviewed. This task did not redeploy.

## Local checks

```sh
PYTHONPATH=Model:Model/tests .venv/bin/python -m unittest discover -s Model/tests
SNAPP_TEST_PYTHON=.venv/bin/python node --test Web/tests/*.test.cjs
python3 scripts/check_snapp_i18n.py
git diff --check
```

Measured local results and per-store versions/counts are in `data/store_scrapes/audit/supabase_catalog/`. That directory is ignored by Git; this handoff document and the small manifest are the reviewable source files. Local memory measurements use separate catalog-comparison Python processes, not a deployed Flask/Render worker with embedding models loaded. Production memory and latency remain unmeasured.
