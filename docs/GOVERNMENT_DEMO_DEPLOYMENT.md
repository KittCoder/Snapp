# SNAPP government demo deployment

This release freezes current application behavior. It does not certify a live
cloud deployment or Supabase owner boundaries. The active grocery source remains
`Model/database.scrape-20260721-143928.json` (10,010 rows), with 10,010 features,
9,994 real BGE vectors and the corresponding runtime manifest.

## Numbered deployment steps

1. **GitHub.** Use `https://github.com/KittCoder/Snapp.git`, release branch
   `demo/government-demo`. Review the release commit and local release reports
   before selecting that branch in hosting dashboards. Do not deploy `main`
   accidentally. Never upload `.env`, `.venv`, local databases or `data/` audits.

2. **Render Flask.** Inspect existing service IDs first; map the existing backend
   to `render.yaml`, rather than creating another backend by mistake. Select the
   release branch. Root directory `Model`; Python **3.12.15**. Build:
   `python -m pip install --upgrade pip==26.2 && python -m pip install -r requirements.txt`.
   Startup: `python security_config.py && gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 model:app`.
   Use at least the proposed 2 GB plan for the PyTorch/BGE runtime; do not assume
   the old 512 MB free plan can load it. Health check `/ready`; `/health` only
   checks process liveness. First readiness also requires reachable dependencies.
   The committed constraints are the remediated set, not the old local `.venv`.
   Model weights download from Hugging Face on the first load; allow outbound
   HTTPS and sufficient startup time. A download failure must leave readiness
   unavailable, not silently switch matcher behavior.

3. **Render Typesense.** Inspect existing services before applying the optional
   `deploy/render-services.yaml`. Use the official `typesense/typesense:30.2`
   image, independent of the Mac. Set `TYPESENSE_API_PORT=10000`,
   `TYPESENSE_DATA_DIR=/var/lib/typesense`, and a random backend-only
   `TYPESENSE_API_KEY` in the secret manager. Public Render ingress supplies HTTPS.
   In Flask set `TYPESENSE_HOST` to the service's actual hostname (no scheme),
   `TYPESENSE_PORT=443`, `TYPESENSE_PROTOCOL=https`, and
   `TYPESENSE_COLLECTION=snapp_recipes`. Never put this key in Vercel or JavaScript.

4. **Persistent disk.** Attach the specified 10 GB paid persistent disk at
   `/var/lib/typesense`. Confirm this directory is the Typesense data directory.
   The embedding model and collection must survive service restarts. Snapshot
   the disk/collection before reindexing; do not treat Render's ephemeral root
   filesystem as recipe storage. Paid resources are intentional and require
   dashboard approval/configuration; no resources were created by this pass.

5. **Index the exact approved corpus.** The compressed artifact is an exact
   copy of the approved export, not regenerated recipes. From a release checkout,
   with the **remote** Typesense variables loaded securely, run:

   ```sh
   python scripts/prepare_recipe_index.py
   python scripts/index_recipes_typesense.py --skip-export \
     --documents data/snapp_typesense_documents.jsonl \
     --report data/typesense_remote_index_report.json
   python scripts/verify_recipe_index.py
   ```

   The existing index command recreates the named collection: take a snapshot
   and confirm the target host/collection before invoking it on populated data.
   Expected count **28,522**; embedding schema 384 dimensions, instructions and
   structured ingredients present. The verification script is read-only.
   Collection counts/schema and sampled documents are checked; it does not
   pretend to exhaustively review all recipe text.

6. **Redis.** Create/map the shared Render Key Value service in
   `deploy/render-services.yaml`. Use its private Redis URL for Flask. Set
   `SNAPP_RATE_LIMIT_STORAGE_URI` (canonical) or `REDIS_URL` (alias), and keep
   `SNAPP_RATE_LIMIT_ENABLED=1`, `SNAPP_DEPENDENCY_READINESS=1`.
   The canonical variable wins if both are set. Production configuration rejects
   local-memory-only rate limiting, including a single worker that may later
   scale. Redis errors fail requests/readiness; there is no memory fallback in
   production. Local development remains supported without Redis.

7. **Supabase.** Confirm the intended project is
   `wmagmsatawlwvcobtkxh` before editing its dashboard. Browser credentials must
   be publishable/anon only; never service-role. Authentication URL settings:
   Site URL `https://snapp-1d5j.vercel.app`; redirect allowlist that exact origin,
   plus explicitly needed development URLs such as `http://localhost:3000` and
   `http://localhost:5173`. Add preview origins individually if actually used.
   Review `docs/SECURITY_LIVE_CHECKS.md`, inspect policies, apply reviewed
   `supabase/migrations/20261008210000_owner_boundary_hardening.sql`, and run the
   disposable two-user verification described there. **Live RLS verification
   remains pending until real token/database tests succeed.** The repository
   migration and local security tests are not proof of deployed policies.

8. **Vercel.** Map the existing project; select the release branch. Project root
   repository root, framework Other, build `node scripts/build_frontend.cjs`,
   output `dist`. Set `SNAPP_API_BASE_URL` to the actual Render HTTPS backend,
   `SUPABASE_URL` to the intended project URL, and `SUPABASE_ANON_KEY` to its
   publishable/anon credential. The build rejects privileged credentials and
   localhost production APIs. Keep `vercel.json` security headers. If changing
   API/Supabase hostnames, explicitly update reviewed CSP `connect-src` origins;
   the build fails when configured origins are absent. Static assets and i18n
   copy into `dist`; extensionless direct navigation falls back to `index.html`.

9. **Environment variables.** `.env.example` lists public build variables and
   private runtime variables; `Model/.env.example` covers local backend options.
   Render: exact HTTPS `ALLOWED_ORIGINS=https://snapp-1d5j.vercel.app`,
   `SNAPP_ENV=production`, `FLASK_DEBUG=0`, strong random `SNAPP_ADMIN_TOKEN`,
   Typesense settings, Redis URL, `SUPABASE_URL`, and optional provider secrets.
   Do not use wildcard CORS, disable dependency readiness, or remove rate limits
   to bypass a deployment failure. Local `SNAPP_ENV=development` preserves local
   HTTP origins. For a separate local static build use `SNAPP_BUILD_MODE=development`
   and a local API URL; no production artifact should use that build mode.

10. **Smoke test without the Mac.** Confirm remote `/health` and `/ready` return
    200, then turn **Mac Flask and Mac Typesense OFF**. In incognito/separate
    device verify Vercel hard refresh/direct navigation, signup/login, English
    and Spanish chat, “I want a beef dinner under 30 minutes”, “no cheese”,
    “show me the second one”, instructions/detail, schedule, pantry, shopping,
    Best Deal presentation, current full Morton Williams prices, refresh and
    logout/login. Replay Patty Melts, Lamb in Pitas and Tuscan Salad. Garlic must
    remain garlic for “3 cloves garlic”; absent minced lamb/skirt steak abstain.
    Do not call the demo ready while RLS or remote index checks are pending.

11. **Rollback.** Git: create a reviewed rollback commit; never force-push shared history.
    Keep remediated dependency pins and security/ownership guards. The original
    main branch predates that hardening and is not an approved cloud rollback. Render Flask: deploy the previous known-good
    commit and restart every worker. Vercel: promote the prior known-good
    deployment and verify CSP/API alignment. Typesense: restore the saved disk
    snapshot or reimport the exact approved artifact with the existing indexing
    command; verify 28,522 documents afterward. Inventory: preserve
    `Model/artifact_rollbacks/morton_williams_promotion_20261013T171603Z` locally;
    restore inventory, features, whole vector-index directory, sale candidates
    and manifest together, validate hashes, restart workers and require READY.
    Do not deploy a source from one snapshot with vectors from another.

## Validation and release gates

With the remediated Python 3.12 interpreter active, reproduce local gates:

```sh
python -m unittest discover -s Model/tests
SNAPP_TEST_PYTHON="$(command -v python)" node --test Web/tests/*.test.cjs
python scripts/check_converged_regressions.py
python scripts/check_snapp_i18n.py
python scripts/security_check.py --history
```

Frontend fixture generation uses `SNAPP_TEST_PYTHON` or `python3`; it never
requires the developer's preserved `.venv`. Local Python 3.12 tests and dependency audit are recorded under ignored
`data/government_demo_release/`. Clean checkout tests must use committed fixtures,
not temporary audit folders. Runtime translations now live under
`Model/recipe_chat_translations/`; the original local files are retained.
No actual cloud service creation, remote indexing, live RLS or device/incognito
smoke is claimed without evidence. Missing live checks remain release blockers.

Authoritative service references:
[Render Blueprint specification](https://render.com/docs/blueprint-spec),
[Typesense installation](https://typesense.org/docs/guide/install-typesense.html),
[Vercel environment variables](https://vercel.com/docs/environment-variables).
