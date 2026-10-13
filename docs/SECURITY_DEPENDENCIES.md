# Python dependency reconciliation — 2026-10-09

The fresh original Python 3.9 environment audit found **53 advisories / 12 packages**,
including 3 critical and 29 high based on the maximum available OSV CVSS vector.
These are calculated severities, not invented publisher labels; one has unknown
severity. The previous 54/13 result included a click advisory absent from the fresh
feed. No advisory was suppressed. Exact aliases, fix versions, vectors, dependency
chains, import/use evidence and reachability are in local
`data/security_audit/dependency_classification.csv` and `.json`.

Production contained 48 of those advisories across 10 packages. The other five were
pip installer / msgpack audit-tool issues. **No packages were removed to silence the
scanner.** The original `.venv` is preserved and still vulnerable; the isolated tested
runtime is `/tmp/snapp-security-py312` (Python 3.12.15). Production uses the repository's
existing pip requirements mechanism, with exact direct versions and transitive
constraints; Render upgrades its installer to pip 26.2. No second package manager is
required for deployment. An isolated auditor uses pip-audit 2.9.0/msgpack 1.2.1/pip 26.2.

## Version changes

| Package | Original | Selected | Advisories removed from applicable target | Compatibility risk / affected use |
|---|---|---|---|---|
| anyio | 4.12.1 | 4.14.2 | 2 | Low: same major; HTTPX/OpenAI transport |
| filelock | 3.19.1 | 3.20.3 | 2 | Low: same major; model cache locks |
| fsspec | 2025.10.0 | 2026.6.0 | 1 | Moderate: calendar release; model file I/O |
| pillow | 11.3.0 | 12.3.0 | 18 | Moderate: major change; text encoder does not decode images |
| requests | 2.32.5 | 2.33.0 | 1 | Low: same major; model acquisition |
| sentence-transformers | 5.1.2 | 5.6.0 | 1 | Moderate: same major; embedding load/encode |
| setuptools | 58.0.4 | 83.0.0 | 4 | Moderate: build API changes; Torch requires >=77.0.3 |
| torch | 2.8.0 | 2.13.0 / 2.13.0+cpu Linux | 8 | Moderate: native runtime; embeddings/offline translation |
| transformers | 4.57.6 | 5.10.1 | 6 | High: required major security bump; model loaders/translation tooling |
| urllib3 | 2.6.3 | 2.8.0 | 5 | Low: same major; requests transport |
| pip | 26.0.1 | 26.2 build bootstrap | 4 | Low: installer only |
| msgpack | 1.1.2 | 1.2.1 isolated auditor | 1 | Low: scanner cache only |

Only necessary model-library changes were accepted. Transformers 5.10.0 was rejected
because PyPI marks it yanked; 5.10.1 is the first non-yanked release after the final
reported fix. Torch 2.13.0 is required by the latest listed fix. Pillow 12.3.0 removes
all 18 reported issues. Sentence-transformers 5.6.0 removes its model trust bypass.
The parent upgrades require huggingface-hub 0.36.2 -> 1.5.0, setuptools >=77.0.3
(selected 83.0.0 for its own fixes), and introduce annotated-doc 0.0.5, shellingham
1.5.4 and typer 0.27.3. Other production versions remain unchanged.

All affected application use flows through `Model/product_retrieval.py` and its
matcher warmup/retrieval consumers; HTTPX/AnyIO also support OpenAI calls in Model,
while offline translation scripts use Transformers. Python 3.9 cannot support all
selected fixes. Python 3.12.15 is pinned in Render; local supported targets are macOS
arm64 and Render Linux x86_64. Render's official CPU Torch wheel URL includes its
SHA256, avoiding irrelevant CUDA downloads. Other platforms/interpreters require a
new reviewed resolution. This is exact version pinning, not hashes for every artifact.

One compatibility fix was required: `SentenceTransformer` now defaults server loads
to CPU (`SNAPP_EMBEDDING_DEVICE` can explicitly override). Updated Torch auto-selected
Metal and aborted macOS forked Gunicorn workers. No matcher scoring, optimizer,
ranking, multilingual parsing or UI logic changed. Five cached-model probe vectors
retained dimension 384 and cosine 1.0 with maximum absolute drift 1.63e-7. This small
probe supplements regression coverage; it does not prove all numerical outputs are
bit-identical. CPU inference can change local performance versus Metal.

## Every fresh advisory

Classification prioritizes known severity; no low-reachability finding was dismissed.
Descriptions and path-specific qualifications are preserved in the CSV. Installer and
scanner findings are fixed in their applicable environments, rather than falsely
called production dependencies.

| Package | Advisory | Severity | Classification |
|---|---|---|---|
| anyio | PYSEC-2026-4025 | CRITICAL | CRITICAL_FIX_NOW |
| anyio | PYSEC-2026-4024 | MODERATE | SAFE_TO_UPGRADE |
| filelock | PYSEC-2026-1375 | MODERATE | SAFE_TO_UPGRADE |
| filelock | PYSEC-2026-1374 | MODERATE | SAFE_TO_UPGRADE |
| fsspec | GHSA-27vj-qcqg-25rc | HIGH | HIGH_FIX_NOW |
| msgpack | PYSEC-2026-3625 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-165 | MODERATE | SAFE_TO_UPGRADE |
| pillow | PYSEC-2026-2250 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-2253 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-2251 | MODERATE | SAFE_TO_UPGRADE |
| pillow | PYSEC-2026-2255 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-2257 | MODERATE | SAFE_TO_UPGRADE |
| pillow | PYSEC-2026-2256 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-2254 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-2252 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-2249 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-2874 | MODERATE | SAFE_TO_UPGRADE |
| pillow | PYSEC-2026-3453 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-3451 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-3454 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-3495 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-3496 | HIGH | HIGH_FIX_NOW |
| pillow | PYSEC-2026-3494 | MODERATE | SAFE_TO_UPGRADE |
| pillow | PYSEC-2026-3493 | HIGH | HIGH_FIX_NOW |
| pip | PYSEC-2026-196 | MODERATE | SAFE_TO_UPGRADE |
| pip | PYSEC-2026-2875 | MODERATE | SAFE_TO_UPGRADE |
| pip | PYSEC-2026-2876 | MODERATE | SAFE_TO_UPGRADE |
| pip | PYSEC-2026-3721 | MODERATE | SAFE_TO_UPGRADE |
| requests | PYSEC-2026-2275 | MODERATE | SAFE_TO_UPGRADE |
| sentence-transformers | PYSEC-2026-4164 | CRITICAL | CRITICAL_FIX_NOW |
| setuptools | PYSEC-2022-43012 | UNKNOWN | SAFE_TO_UPGRADE |
| setuptools | PYSEC-2025-49 | HIGH | HIGH_FIX_NOW |
| setuptools | PYSEC-2026-1918 | HIGH | HIGH_FIX_NOW |
| setuptools | PYSEC-2026-3447 | MODERATE | SAFE_TO_UPGRADE |
| torch | PYSEC-2025-206 | MODERATE | SAFE_TO_UPGRADE |
| torch | PYSEC-2025-204 | HIGH | HIGH_FIX_NOW |
| torch | PYSEC-2026-139 | HIGH | HIGH_FIX_NOW |
| torch | PYSEC-2025-203 | HIGH | HIGH_FIX_NOW |
| torch | PYSEC-2026-2286 | HIGH | HIGH_FIX_NOW |
| torch | GHSA-vgrw-7cvw-pwgx | MODERATE | SAFE_TO_UPGRADE |
| torch | GHSA-rrmf-rvhw-rf47 | MODERATE | SAFE_TO_UPGRADE |
| torch | GHSA-qfhq-4f3w-5fph | MODERATE | SAFE_TO_UPGRADE |
| transformers | PYSEC-2025-217 | HIGH | HIGH_FIX_NOW |
| transformers | PYSEC-2026-2290 | CRITICAL | CRITICAL_FIX_NOW |
| transformers | PYSEC-2026-2288 | HIGH | HIGH_FIX_NOW |
| transformers | PYSEC-2026-2289 | HIGH | HIGH_FIX_NOW |
| transformers | PYSEC-2026-3929 | HIGH | HIGH_FIX_NOW |
| transformers | PYSEC-2026-4174 | HIGH | HIGH_FIX_NOW |
| urllib3 | PYSEC-2026-142 | HIGH | HIGH_FIX_NOW |
| urllib3 | PYSEC-2026-141 | MODERATE | SAFE_TO_UPGRADE |
| urllib3 | PYSEC-2026-4177 | HIGH | HIGH_FIX_NOW |
| urllib3 | PYSEC-2026-4176 | MODERATE | SAFE_TO_UPGRADE |
| urllib3 | PYSEC-2026-4175 | HIGH | HIGH_FIX_NOW |

## Audit and validation boundaries

- Tested installed application environment: **0 known advisories; 0 critical/high**.
- Fully pinned Linux dependency set plus installer: **0 known advisories** (feed
  audit with dependency resolution disabled only because the complete resolved set
  was supplied; official CPU wheel resolved separately). Linux native execution is
  not available on this macOS host and remains a deployment smoke check.
- Isolated auditor environment: **0 known advisories**.
- Remaining advisories in the remediated targets: **none**. The retained original
  Python 3.9 `.venv` is not the candidate runtime and was not altered by remediation.
- Backend: 629 passed, including security/Auth route tests, Recipe Chat,
  multilingual, matcher, DealOptimizer, shopping path and Gunicorn readiness.
- Frontend: 28 passed; matcher regression corpus: 2,091 passed.
- Live Supabase RLS/auth and actual deployed configuration remain unverified.

Artifacts: `data/security_audit/dependency_audit_before.json`,
`dependency_audit_after.json`, `linux_dependency_audit.json`,
`audit_tool_environment.json`, `dependency_matcher_regressions.json`,
`dependency_backend_tests.log`, `dependency_frontend_tests.log`.
Model files/cache must remain operator-controlled; no dependency audit certifies
model provenance. Existing production headers/rate limits/security behavior remain
subject to the deployment checks in SECURITY.md.
