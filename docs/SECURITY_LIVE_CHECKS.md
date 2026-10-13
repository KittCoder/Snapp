# Supabase release checks

2026-10-09: **LIVE_RLS_BLOCKED_MISSING_ACCESS**. No admin key, database credentials,
or authenticated project CLI access were available. No cloud schema or records were
changed. This procedure and REST harness have not been executed against Supabase.

## Schema review and migration

1. Open project `wmagmsatawlwvcobtkxh` in Supabase Dashboard. First use an isolated
   staging project with the same schema. Confirm backups and the migration owner.
2. Paste `supabase/tests/security_inventory.sql` into SQL Editor and run it. Save
   the table/RLS/policy/grant results without selecting user records. Inspect **all**
   user-linked tables, including tables not present in repository migrations.
3. Review `supabase/migrations/20261008210000_owner_boundary_hardening.sql` against
   that inventory. It never disables RLS. Its restrictive authenticated ownership
   boundary uses `auth.uid()` in both USING and WITH CHECK. Existing authenticated
   permissive policies cannot widen that boundary. Confirm no PUBLIC/inherited
   grants and older anonymous/public policies permit private access. Resolve any
   such live findings before release. Confirm catalogs are server-only; do not run
   their revoke statements if an independently verified integration requires public
   reference access. Repository browser code does not use these catalogs.
4. Confirm the prior profile/favorite/catalog migrations exist. Paste the reviewed
   owner-boundary migration into SQL Editor and run its transaction. Re-run the
   inventory and record actual RLS flags and all four operation policies. Apply to
   the production project only after staging tests succeed and schema differences
   are reviewed. No migration was applied by this audit.
5. In isolated staging SQL Editor, run `supabase/tests/owner_boundary.sql`. This is
   a partial rollback-only SQL check, not a replacement for REST/token testing.

## Disposable REST tests

Use the tested Python 3.12 environment. Keys are entered through hidden prompts;
do not export them into shell history, paste them into commands, or redirect input.
The harness validates the exact project hostname before accepting credentials.

```sh
python scripts/verify_live_supabase.py \
  --project-url https://wmagmsatawlwvcobtkxh.supabase.co \
  --expected-project-ref wmagmsatawlwvcobtkxh
```

For staging, replace **both** arguments with that staging project's hostname/ref.
Use its publishable/anon key and server admin secret/service-role key. The harness
creates two dedicated confirmed `snapp-security-<random>-a/b@example.invalid` users
and disposable rows in each of the five owner tables. It checks:

- A cannot read B, update B, or delete B; B independently verifies its complete
  row is unchanged after both mutations.
- Every table rejects spoofed inserts and ownership changes with RLS error 42501.
  It temporarily deletes B's disposable profile to avoid duplicate-key failures
  masking those tests; no existing user's profile is touched.
- A's own insert/read/update/delete succeeds and deletion is independently read.
- Missing, invalid, and malformed auth headers fail with 401/403 on every table.
- The three server-only ingredient catalogs deny anon/authenticated REST reads.
- Password login, refresh, valid `/auth/v1/user`, logout and rejection of subsequent
  refresh work. Logout need not revoke an already issued access JWT immediately;
  it remains valid until expiry under the provider's documented session semantics.
- Finally, explicit owner-filtered cleanup removes only the created users' records
  and users, then confirms each user no longer exists. Any cleanup failure prints
  only its disposable UUID for Dashboard cleanup. User deletion failures block release.

It logs only check names/status codes, never provider response bodies or credentials.
It does not treat permission denial as proof of own-row usability: positive tests
must pass too. A failure exits nonzero. If live schema constraints/triggers differ,
inspect the schema without dumping provider auth bodies and adapt disposable fixture
fields; do not weaken assertions or policies to pass tests.

A genuinely expired **project-issued** token is a separate required test. Keep one
from a dedicated staging user in an operator-controlled private session until its
JWT expiry; do not forge a signature or merely alter `exp`. Run the same command
with `--check-expired-token` and enter it at the hidden prompt. Without this option,
the harness explicitly reports expired-token coverage as NOT_TESTED.

## Public behavior and actual browser auth

These remain manual tests beyond the REST harness:

```sh
curl --fail --silent --show-error https://snapp-a64d.onrender.com/health
curl --fail --silent --show-error https://snapp-a64d.onrender.com/ready
```

Readiness must pass with production Redis/Typesense and runtime assets configured.
In the deployed app, anonymously search a known recipe, open its detail, and request
its ingredients/nutrition. Repeat after login. Public recipes are served by Flask/
Typesense, not these owner tables; verify any additional live public reference tables
identified in the inventory remain accessible according to their intended design.

In staging, create two additional disposable email accounts through the actual app
using operator-controlled mailboxes (if email confirmation is required). Record only
their user IDs. Verify signup and confirmation, login, and generic failed login;
no mandatory case/number/symbol or forced rotation should appear. As A, create a
pantry item, store, schedule, favorite and profile update; reload to verify persistence.
As B in a separate browser profile, confirm none of A's items appears. Do not use
production users or log network Authorization headers.

In Auth settings on **staging only**, use a short supported JWT expiry; keep the
browser open beyond expiry and verify SDK refresh and an authenticated pantry read
succeed. Then log out, reload, and confirm private UI/session data is unavailable.
Test revoked/expired session handling by revoking only that disposable user's session
in Dashboard and waiting for its access token expiry; the next private operation must
fail safely and permit re-login without raw provider errors/stack traces. Restore the
staging expiry setting. Test logout synchronization in a second tab. Run the genuine
expired-token REST probe as above. Capture status/check outcomes, not raw tokens.

Delete these browser test accounts/records in Dashboard and independently confirm
cleanup. Record the test date, project, inventory, operation results, browser results,
and cleanup in `docs/SECURITY.md`. Inspect Auth redirect URLs, confirmation/rate limits,
optional CAPTCHA/MFA/leaked-password settings without adding password composition
rules. Neither local Flask tests nor mocked browser auth certify this live gate.
