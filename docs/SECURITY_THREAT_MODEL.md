# SNAPP threat model (inspection before implementation)

The browser loads a static Vercel application, authenticates directly with Supabase,
and accesses owner data through Supabase REST. Render Flask provides public recipe,
nutrition, product, store and AI computation; privileged review routes use an admin token.
Typesense and model/provider credentials belong exclusively to Render/operators.

Assets: accounts and sessions; household size, ZIP/budget, dietary preferences,
pantry, schedules, favorites and derived shopping lists; API/provider/admin keys;
recipe/search infrastructure and availability. Boundaries: untrusted browser/input,
Vercel assets/CDNs, Render APIs, Supabase auth/RLS, Typesense, and outbound providers.
Frontend ownership filters are convenience, not authorization. Supabase RLS must check
both existing and resulting row ownership against auth.uid(). No Flask route currently
persists a user's pantry/profile/schedule; public computation is not an owner-data API.

Priority findings from repository inspection:
- High: pantry/stores/schedule tables used in the frontend lack checked-in RLS policies;
  deployed policies cannot be verified offline. Existing profile/favorites policies exist.
- High: legacy /chat uses process-global conversation history across requests.
- High: unrestricted expensive public endpoints permit resource/cost abuse.
- Medium: permissive preview/local CORS patterns in production; wildcard is configurable.
- Medium: exception details can reach clients; request IDs are unvalidated client input.
- Medium: coercion/nesting/array bounds are inconsistent; no universal streaming body cap.
- Medium: unvalidated dynamic link schemes; broad Supabase CDN version, no frontend CSP.
- Low/unknown: dependency advisories and credential leakage require scans, not assumptions.

Threats include account takeover, credential stuffing, IDOR/ownership spoofing, token
exfiltration through XSS/CDNs, Typesense/SQL injection, SSRF through provider URLs,
malformed input/CPU abuse, exposed admin diagnostics, and sensitive error/log leakage.
Passwords remain compatible with Supabase: no case/number/symbol composition or rotation.

Plan: centralized bounded request/security hooks, strict allowlisted CORS, safe responses,
rate limits with production shared storage, disable unused legacy chat in production,
owner-only RLS migration/tests, safe link protocols, CSP/pinned CDN integrity, deployment
checks and sanitized static/history/dependency audit. Do not change product algorithms.
Live RLS/auth/cloud verification and credential rotations remain operator actions.
