# SNAPP security operations

This repository hardening is not a certification or proof of the deployed configuration.
Before a government-facing demo, complete the deployment and database checks below.
See [the inspection threat model](SECURITY_THREAT_MODEL.md) and local audit artifacts
in `data/security_audit/` (ignored by Git). Never publish those artifacts without review.

## Architecture and authorization

Vercel serves static browser assets. Render Flask mediates Typesense, recipe/search,
matching, nutrition and third-party computation. Supabase owns authentication and
private data authorization. Browser state is untrusted, including user IDs, recipe
state, profile fields and provider output. All dynamic copy uses text DOM methods.

The complete Flask route/method inventory is exported to `data/security_audit/routes.csv`.
Recipe/search/detail/nutrition/dishes/store/sale endpoints are intentionally PUBLIC:
they compute from supplied input and do not read persisted owner resources. No Flask
endpoint currently implements private pantry/profile/schedule reads or writes.
`/internal/*` requires the server admin token even when a fake user_id/Bearer token is
supplied. `/dev/*` and obsolete `/chat` are disabled in production; the latter also
no longer retains process-global conversation history in development. The working
`/api/recipes/chat` conversation implementation is unchanged.

Private browser operations use Supabase's REST API with the SDK session token.
`user_info` ownership is its `id`; `user_pantry_items`, `user_stores`,
`user_scheduled_meals` and `user_favorite_recipes` ownership is `user_id`.
Shopping lists are derived from saved meals; preferences/household data live in the
profile. Frontend `.eq(user_id, currentUser.id)` constraints assist UX, but they are
not authorization. RLS must independently enforce authenticated ownership on SELECT,
DELETE, and both the old and resulting rows for UPDATE/INSERT. Catalog tables are not
used by the browser and are denied REST access by default.

Apply `supabase/migrations/20261008210000_owner_boundary_hardening.sql` after reviewing
existing schema, policies, integrations and grants. It creates missing owner tables,
enables/forces RLS, revokes anonymous grants, and adds restrictive ownership policies
so existing permissive policies cannot widen access. It adds permissive owner access
for the app's existing authenticated CRUD. Service-role operators still bypass RLS;
never use that key in browser code. Test on a staging database before production.
`supabase/tests/owner_boundary.sql` creates rollback-only A/B fixtures and exercises
cross-user reads/updates/deletes, ownership reassignment and spoofed inserts.
Neither migration nor database tests were executed against a live Supabase project.
No PostgreSQL/Supabase CLI connection was available in this workspace.

## Authentication, sessions, MFA and passwords

Supabase handles session expiry, refresh, cross-tab synchronization and logout.
The existing SDK storage model uses browser localStorage. This retains the SDK's
current UX; localStorage tokens remain exposed if an attacker obtains same-origin
script execution or controls a browser extension/device. CSP, SRI and safe DOM use
reduce that exposure; HttpOnly-cookie/BFF migration would be a separate architecture
change. Do not log tokens, put them into URLs, or implement a custom JWT/OTP system.
Public Flask computations do not need Supabase JWT verification. Any FUTURE private
Flask resource must verify the token with Supabase and derive owner identity from it,
never from a browser user_id. Do not reuse the public computation classification.

Supabase direct writes use Authorization Bearer tokens, not cookie authentication.
Flask has no cookie-authenticated write endpoints. Therefore ambient-cookie CSRF
middleware is not needed for current APIs. Revisit this if a cookie/BFF is added.
CORS does not authorize private data or prevent non-browser scraping.

Login and signup failures are generic and translated rather than exposing provider enumeration
messages. Configure Supabase Auth rate limits, CAPTCHA/Turnstile where appropriate,
email confirmation, redirect allowlists and supported leaked-password protection in
the dashboard. SDK signUp responses and account lifecycle must be tested with the
project's email-confirmation settings; this patch does not change signup semantics.
Enable MFA through Supabase's supported enrollment/challenge/AAL APIs, initially for
operators. Normal demo users are not forced to enroll. A complete MFA UX/AAL policy
rollout is future work; no custom OTP is present. See the official
[Supabase MFA guide](https://supabase.com/docs/guides/auth/auth-mfa).

**No new uppercase/lowercase/number/symbol or mixed-character password requirement,
forced composition, periodic expiry, or forced password rotation was introduced.**
Existing Supabase password-length behavior remains unchanged. Prefer passphrases,
password managers, optional MFA and supported compromised-password detection.

## API bounds, rate limiting and injection

As recommended by the [Flask security documentation](https://flask.palletsprojects.com/en/stable/web-security/), a global body limit defaults to 524,288 bytes, enforced before JSON parsing. Request
JSON must be an object; tree depth <=12, total values <=4,000, arrays <=200, object
fields <=100 and strings <=4,000. Text/numeric/boolean/filter/locale/ID fields receive
additional type and range checks. Recipe Chat messages have a server-side 300-character
limit. Existing route limits also apply. Malformed/oversized input returns 400/413.
Request IDs are generated server-side, ignoring client-controlled log identifiers.

Flask-Limiter/limits provides atomic shared storage in production. Configure
`SNAPP_RATE_LIMIT_STORAGE_URI` to a Redis service (use TLS for external connections).
Default limits: 120 requests/minute per route/IP; compute POST routes add 30/minute.
Override with `SNAPP_RATE_LIMIT_DEFAULT` and `SNAPP_RATE_LIMIT_COMPUTE` after load testing.
429 responses provide Retry-After. Health, readiness and OPTIONS are exempt.
Development limits are disabled unless `SNAPP_RATE_LIMIT_ENABLED=1`.
No arbitrary X-Forwarded-For header is trusted. Confirm Render's observed remote_addr
behavior: proxy/NAT clients may share limits. Identity-aware public-route limits are
not implemented because there is no verified user identity on these endpoints.
Use an edge/WAF limit as well; Redis outage fails closed, not silently unbounded.
Readiness caches a bounded Redis/Typesense availability probe for 30 seconds.

Typesense filters use server-owned field/operator construction and quoted literals;
backslash/backtick delimiters cannot escape those literals. Arbitrary filter_by input
is not accepted as query syntax. SQLite queries inspected use bound parameters;
HTTP IDs do not become shell commands/filesystem paths. Admin report paths are fixed.
Runtime requests use fixed provider origins or same-origin discovered recipe links,
not browser-supplied destination URLs. Generic browser URL-fetch endpoints do not
exist. Provider redirects/DNS compromise remain outbound/SSRF risks: restrict egress
in deployment and keep provider allowlists under operator control. This patch does
not claim DNS-rebinding/redirect isolation for existing urllib/provider integrations.
No input-controlled redirects were found in application routes. Supabase redirect
URL allowlists must still be verified in the dashboard.

## CORS, CSP, browser supply chain and headers

Set explicit `ALLOWED_ORIGINS` (legacy `CORS_ORIGINS` remains supported).
Production default deployment uses `https://snapp-1d5j.vercel.app`; configure each
approved preview origin explicitly. Wildcards/arbitrary preview origins are not
reflected. Development defaults include localhost/127.0.0.1 on ports 3000/5173.
CORS allows Content-Type/Authorization/admin/request-ID headers, not cookies.

Vercel config supplies CSP, nosniff, Referrer-Policy, Permissions-Policy, HSTS and
`frame-ancestors 'none'`. Scripts allow only self plus the two pinned CDN origins;
Supabase JS 2.117.3 and Leaflet 1.9.4 JS/CSS have SHA-384 SRI/crossorigin attributes.
There is no unsafe-inline or unsafe-eval script allowance. Google Fonts are explicitly
allowed. Inline styles remain necessary for Leaflet/generated positioning; CSS CSP
allows unsafe-inline styles. HTTPS images remain broadly allowed because real recipe
images come from multiple provider domains. Those two exceptions are intentional.
connect-src lists only self, the current Render API and Supabase HTTPS/WebSocket host.
Update CSP deliberately if these deployments move; never make connect-src wildcard.

Backend JSON adds nosniff, strict-origin referrer policy, disabled camera/mic/location,
a default-deny CSP/frame protection and production HSTS. Mutation/admin/Bearer responses
use no-store; public health/static resources need not be globally uncached.
Dynamic external links permit http/https only, reject embedded credentials, and use
existing noreferrer/noopener. Titles/instructions/product/profile/translated copy stay
text, not markup. Keep the centralized safe URL helper for new dynamic links.

## Secrets, configuration, readiness and incident handling

Only the Supabase publishable browser key is intentionally visible in index.html.
It identifies the project; it is not a service-role/admin key. The Supabase URL and
Render URL are public. Typesense/admin/provider secrets belong in Render's secret
manager; never copy them into Web assets or Vercel public variables.
.env/key/PEM/credential files, local Typesense state, logs and generated audits are
ignored. Sanitized .env.example remains tracked. Pattern scans found no real tracked,
untracked application-source or visible-history secrets; this is not an exhaustive
detection guarantee. No external credentials were rotated or revoked.

Render launch runs `python security_config.py` before gunicorn. Production refuses
missing/non-HTTPS origins, short/missing admin token, absent HTTPS Typesense config,
absent Supabase URL, missing shared Redis, disabled limits or disabled dependency
readiness. Debug is disabled. Run this preflight for EVERY alternate launch mechanism;
importing model directly bypasses the deployment launch preflight.
`/health` means process alive; `/ready` additionally requires runtime assets/warmup,
Supabase configuration and bounded Redis/Typesense probes. Supabase service availability
and RLS effectiveness are not certified by a configuration check. Readiness probe
failures return generic errors and no credential/config values.

Production errors omit exceptions/details; HTTP 404/405/413/429 retain their status.
Responses carry a request ID. Logs include error type, route/status/timing where existing
instrumentation provides them, not request bodies. Structured field sanitization removes
nested secret/token/password/auth keys and collapses newlines. Restrict access to Render
logs and metrics; they can still reveal internal operational state to operators.

Incident steps: restrict affected access; preserve sanitized timestamps/request IDs;
identify scope; rotate exposed API/admin/service credentials at their providers; revoke
compromised sessions; review RLS/privileged activity; deploy a tested fix; notify affected
parties under applicable obligations. History rewriting/removal alone is not rotation.
No routine forced user password rotation is introduced.
Vulnerability reporting contact: **[operator must supply monitored contact]**.

## Dependency review and release checks

On 2026-10-09 the fresh original environment audit found 53 advisories across 12
packages; the previous click advisory is absent from the fresh feed. The isolated
Python 3.12.15 candidate, fully pinned Linux dependency set and isolated auditor each
report zero known advisories, including zero critical/high. The original Python 3.9
`.venv` is preserved and still vulnerable; use the candidate runtime for deployment.
No dependency was removed to silence the scanner.
See [the full dependency reconciliation](SECURITY_DEPENDENCIES.md) for every advisory,
classification, version change, dependency chain, affected module and verification limit.
Exact direct requirements use transitive constraints in the same pip mechanism.
Render pins Python 3.12.15, bootstrap pip 26.2 and the official CPU Torch wheel on
Linux x86_64. Linux native execution remains a staging deployment smoke check.
One necessary compatibility fix defaults server embedding loads to CPU because
updated Torch Metal initialization aborted forked macOS Gunicorn workers. No matcher
scoring or optimizer rules changed. All 629 backend, 28 frontend and 2,091 corpus
cases pass. Do not deserialize untrusted weights/pickles; artifacts must remain
operator-controlled.

npm audit of the exact pinned browser packages/transitives reported zero advisories.
There is no npm application manifest; an isolated audit manifest/lock was used, with
install scripts disabled. Zero advisories is not supply-chain certification.
Use `scripts/security_check.py --history` for static configuration/header/source/history
checks; never describe its output as a security score. Review source and cloud policies,
not only automated scans. Run backend/frontend/i18n/auth/security tests and 2,091 matcher
regressions. Live cross-user Supabase REST/expired-token tests are deployment gates,
not implied by locally passing Flask tests or prepared SQL.

## OWASP review and remaining deployment gates

- Broken access control: owner RLS migration + admin guards; deployed RLS remains unverified.
- Cryptographic/auth failures: managed SDK/TLS, no tokens in URLs; localStorage/device and
  provider Auth settings remain risks. Complete MFA/email/anti-abuse configuration.
- Injection/XSS: bounded typed inputs, filter quoting, safe DOM/URL regression coverage;
  provider-generated data still requires ongoing review.
- Insecure design: legacy shared chat removed from production, public computation bounded;
  cost abuse across distributed IPs still needs an edge/WAF budget strategy.
- Misconfiguration: launch preflight, allowlisted CORS, CSP/headers and readiness;
  apply Vercel/Render config and staging-test before demo.
- Vulnerable components: candidate Python/browser audits clean; deploy the tested
  pinned runtime and verify native Linux startup/inference.
- Integrity: pinned CDN/SRI and trusted artifacts; verify model builds and update provenance.
- Logging/monitoring: request IDs/redaction, restricted diagnostics; configure alerting for
  429/5xx, provider spend, Redis errors and unexpected privileged activity.
- SSRF: no arbitrary browser URL endpoint; third-party redirects/DNS/egress remain risks.

Manual gates: review/apply SQL on staging then production; run A/B/anon REST and rollback
DB tests; inspect every public-schema table for RLS/grants beyond these five; configure
Render secrets/Redis/origins/preflight; apply Vercel headers and verify CSP in the deployed
browser; test login/refresh/logout across tabs; configure Supabase Auth/CAPTCHA/leaked
password/MFA options; deploy the audited pins and verify Linux inference; supply security contact.
Existing schedule duplicates/local cache persistence remain product semantics: the UI
already disables in-flight actions and stores/favorites use unique/upsert keys, but no
new global schedule idempotency constraint was introduced without a product-level key.

## Release gate reconciliation — 2026-10-09

| Gate | Result | Evidence / remaining requirement |
|---|---|---|
| PYTHON_DEPENDENCIES | PASS for candidate | Zero known advisories in installed candidate, pinned Linux set and auditor; original `.venv` unchanged. Staging Linux deploy smoke required. |
| LIVE_RLS | BLOCKED | LIVE_RLS_BLOCKED_MISSING_ACCESS; no live migration or A/B REST tests executed. |
| AUTH | BLOCKED for live | Local security tests and prior mocked browser smoke pass; actual project token and browser auth flows unverified. |
| FRONTEND_SECRET_EXPOSURE | PASS for repository | Only intended publishable Supabase key; no privileged browser/source/history finding. Verify deployed bundles/cloud variables. |
| PASSWORD_POLICY | PASS | No mandatory number/symbol/case composition or forced periodic rotation introduced. |

Overall: **SECURITY_RELEASE_GATES_BLOCKED**. Live verification date: **not performed**.
No admin key, database credentials or authenticated project CLI access were available.
No live migration, test user or record was created. No exposed real credential was
found requiring rotation. Existing cloud settings have not been changed.

Repository inventory covers every owner table accessed by the current browser:

| Table | Owner | Live RLS enabled | SELECT | INSERT | UPDATE | DELETE | Intended access |
|---|---|---|---|---|---|---|---|
| user_info | id | UNKNOWN | owner USING | owner WITH CHECK | owner USING + WITH CHECK | owner USING | private profile/preferences/household/settings |
| user_pantry_items | user_id | UNKNOWN | owner USING | owner WITH CHECK | owner USING + WITH CHECK | owner USING | private pantry |
| user_stores | user_id | UNKNOWN | owner USING | owner WITH CHECK | owner USING + WITH CHECK | owner USING | private selected stores |
| user_scheduled_meals | user_id | UNKNOWN | owner USING | owner WITH CHECK | owner USING + WITH CHECK | owner USING | private schedules; shopping derived from meal_data |
| user_favorite_recipes | user_id | UNKNOWN | owner USING | owner WITH CHECK | owner USING + WITH CHECK | owner USING | private saved recipes |

Policy columns describe **reviewed migration intent**, not observed live policies.
Owner means `(select auth.uid()) = ownership_column`; the migration supplies both
restrictive and permissive authenticated ALL policies. Prior profile/favorite
migrations enable RLS; proposed hardening enables/forces all five. Three ingredient
catalogs are server-only in repository usage. Obtain actual RLS/policies/grants for
all live tables with `supabase/tests/security_inventory.sql`; no live flags are
inferred from migration source.

| Live check | Result |
|---|---|
| A reads B | NOT RUN |
| A updates B; B independently verifies unchanged | NOT RUN |
| A deletes B; B independently verifies survival | NOT RUN |
| Insert ownership spoof, all five tables | NOT RUN |
| Ownership change, all five tables | NOT RUN |
| Own-row CRUD, all five tables | NOT RUN |
| Public data / server-only catalog access | NOT RUN |
| Valid/invalid/expired/malformed/missing tokens | NOT RUN |
| Actual browser signup/login/logout/refresh/expiry | NOT RUN |
| Cleanup | NOT APPLICABLE; none created |

[Exact operator instructions](SECURITY_LIVE_CHECKS.md) provide Dashboard SQL steps,
read-only inventory, migration review, runnable disposable A/B REST harness, genuine
expired-token checks, browser flows and cleanup. The harness is prepared and
syntax-checked, **not live-tested**. It never prints passwords, keys or token bodies.
Current Flask/browser code does not use a Supabase service role. The operator harness
uses a server admin credential only for disposable users and cleanup; keep it outside
browser assets/public variables.

Deploy requirements: review/apply RLS in staging and then production; run every live
check and inventory extra owner/public tables; configure Supabase redirects/email
confirmation/rate limits and optional CAPTCHA/MFA/leaked-password settings; build/start
Render using Python 3.12.15, the pins, operator-managed secrets and shared Redis
(TLS for external Redis); verify `/ready` and real Linux model inference; deploy
Vercel CSP/SRI and inspect actual bundles/auth flows. No external deployment was made.
Keep existing rate limits, explicit origins, preflight and secret manager settings.
No password composition rules or periodic rotation were added.
