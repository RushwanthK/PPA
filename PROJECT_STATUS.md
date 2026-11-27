# Project Status

## Current Overall Status

Basis: branch `perf/add-request-diagnostics` at commit `306bdb8` (November 23, 2026). **This branch is the production branch** for both Vercel and Render (not `main`, which is 13+ commits behind). The Phase 3 work is committed, pushed and deployed: migration `0557b33bd281` is applied on Supabase, Vercel serves the new frontend and the new backend is deployed manually on Render.

PPA is an established full-stack personal finance application and a structured learning project for Full Stack Engineering and DevOps. It is used daily with real financial data, so every change goes through a manual review, commit and deployment step.

### Completed Foundations

- Full-stack application using React, Flask, SQLAlchemy and PostgreSQL
- JWT authentication and the existing financial modules
- Dockerized backend, frontend and PostgreSQL development environment
- Docker volumes, networking and Docker Compose
- Git/GitHub workflow and repository safety practices
- GitHub Actions CI foundation
- Opt-in backend request/SQL timing diagnostics
- Server-side bank transaction search/filtering and cursor pagination
- Optional Redis cache-aside for dashboard aggregates

### Current Phase — Phase 3: Automated Testing and Auth/API Security

Phase 3 was widened on November 22, 2026 so that the public app's security is hardened before testing is declared complete:

| Part | Scope | Status |
|---|---|---|
| 3A | Full backend regression and fixes | ✅ Done and deployed |
| 3B | Auth/API security: rate limiting, JWT lifecycle, request limits, CORS, error replies, dependencies | ✅ Done and deployed, `TRUSTED_PROXY_COUNT=3` (refresh tokens deliberately deferred) |
| 3C | Frontend automated tests | ✅ Done and deployed |
| 3D | CI runs both test suites; documentation updated | ✅ First green run on the production branch (November 23, 2026) |

**Local verification (November 23, 2026):**

- Backend: `pytest` → `465 passed, 5 warnings` (the five known `datetime.utcnow()` deprecation warnings).
- Frontend: `npm test -- --watchAll=false` → `201 passed` in 14 test suites.
- Frontend production build: `CI=true npm run build` → compiled successfully.
- `pip-audit` on `requirements.txt` → no known vulnerabilities.
- Rate limiting was also checked against a real local Redis 8 instance (per-IP, per-account and registration limits; every key had a TTL and contained only hashed usernames).
- Migration `0557b33bd281` was upgraded, downgraded and re-upgraded on a throwaway local database.

**Production deployment (November 23, 2026):**

- The owner applied migration `0557b33bd281` on Supabase (`alembic_version` = `0557b33bd281`), set a new 32+ byte `JWT_SECRET_KEY` on Render, deployed the backend manually, and confirmed the live app works.
- Read-only checks against production (no logins, no rate-limited endpoints):
  - The deployed frontend bundle calls `rs-ppa-backend-v2.onrender.com`, includes `logout-all` and no longer sets `withCredentials`.
  - Backend responses carry `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and HSTS.
  - `GET /me` and `POST /logout` without a token return `401 {"error": "Please log in to continue."}` (the new uniform reply; the old backend had no `/logout`).
  - A CORS preflight from `https://rs-ppa.vercel.app` is allowed for the `Authorization` header, with no `Access-Control-Allow-Credentials`.

**Notes and remaining minor items:**

- **CI on the production branch:** the workflow triggers now include `perf/add-request-diagnostics` (and a manual "Run workflow" button). First green run: GitHub Actions run 45152442674 on `558f7b3`: backend `465 passed, 5 warnings`, frontend `201 passed` (14 suites), build compiled. Vercel deploys in parallel with CI, so CI cannot block the frontend deploy; deploy the backend on Render only after a green run.
- **`TRUSTED_PROXY_COUNT=3` in production.** Measured on Render on November 23, 2026 with the `PROXY_DIAGNOSTICS` log: every request arrives with three `X-Forwarded-For` entries appended by infrastructure (client IP, then a Cloudflare edge address `104.23.x.x`, then Render's internal load balancer `10.x.x.x`), and a local proxy inside the container connects to gunicorn from `127.0.0.1`. The client IP also matches `True-Client-IP` / `CF-Connecting-IP`. A request with a fake `X-Forwarded-For: 6.6.6.6` showed the fake value as a fourth entry on the far left, so **`TRUSTED_PROXY_COUNT=3`** is set in production. With 3, a shorter-than-expected chain falls back to `127.0.0.1` (the shared bucket) instead of trusting a client value. Residual risk: a client able to reach Render's load balancer without Cloudflare could fake one entry; the per-account login limit still applies. If Render changes its routing, re-measure. `PROXY_DIAGNOSTICS` was switched off again afterwards.
- Rate-limit behavior (429) has not been exercised in production (it is covered by tests and was checked against a local Redis). Now that clients have separate buckets, a test with a made-up username is safe if wanted.
- Branch-protection/required-check settings.

### Planned After Phase 3 — RAG and AI Integration

A separate project-document learning chatbot and the PPA Knowledge Copilot are planned after Phase 3 and before Phase 4. Earlier documents called this "Phase 3B"; it is now listed as the RAG/AI phase to avoid confusion with the security work above.

**Status: in progress, local development only (not committed or deployed).**

- Design: a separate async **FastAPI AI service** in `ai_service/`, with its own venv and requirements. Flask is unchanged.
- RAG answers questions about PPA and general financial education.
- Agent tools fetch the user's own data by calling Flask with the user's token. pandas computes the numbers.
- Groq generates the answers, with Gemini for embeddings and as fallback.
- [x] Step 1 (Nov 23, 2026): skeleton, local Postgres 17 + pgvector 0.8.1 in Docker (`127.0.0.1:5434`), `ai` schema, `/health/live` and `/health/ready`. 16 tests pass. Baseline: ~59 MB RAM, ~47.5 MB of packages.
- [x] Step 2 (Nov 23, 2026): 16 knowledge documents (PPA user guide + finance notes with sources), heading-aware chunking (94 chunks, about 8.4k tokens), Gemini embedding client, incremental ingestion, `ai.documents` / `ai.chunks` with HNSW and full-text indexes, hybrid retrieval (vector + keyword, RRF), 36-question evaluation set, own migration runner. Ingested with real Gemini embeddings (Nov 24): hybrid retrieval hit@5 1.00, hit@1 0.94, MRR 0.97 on 36 questions. A free-tier 429 on the first run led to a client-side rate limiter and single-batch ingestion. 77 tests pass.
- [x] Step 3 (Nov 24, 2026): `POST /v1/ask` and `GET /v1/usage`.
  - Auth through Flask `/me` (no JWT secret in the AI service; fails closed).
  - Groq `openai/gpt-oss-120b` with Gemini `gemini-3.5-flash-lite` fallback.
  - Deterministic advice and injection refusals, and a relevance gate (0.61, calibrated).
  - Citation verification; ungrounded answers are blocked.
  - Per-user daily and per-minute limits with atomic quota reservation.
  - Audit log that stores no question text, and a kill switch.
  - Live smoke test: 11 questions behaved as designed, about 7.2k tokens. 197 tests pass. About 64 MB RAM.
- [x] Step 3 follow-ups (Nov 24, 2026):
  - Checked real provider limits: Groq 1,000 requests/day and 8,000 tokens/minute (from its response headers); Gemini Flash Lite 15/minute, 500/day; Gemini embeddings 100/minute, 1,000/day (AI Studio).
  - Quota day now resets with Gemini (midnight Pacific), shown to users in IST (1:30 PM IST in winter). `/v1/usage` returns `resets_at`. Added `tzdata`.
  - 503s say how long to wait (busy for N seconds, or until the daily reset), using the providers' own retry information.
  - A request that fails because every provider is down no longer uses up the user's daily request.
  - Answers cut off at 700 tokens carry a notice; `finish_reason` is audited (migration `0003`).
  - Accepted and documented: Gemini is a single point of failure for search.
  - 216 tests pass (Flask's 468 unchanged). Overall write-up: `AI_AND_RAG.md`.
- [ ] Step 4: agent tools that call Flask, plus pandas analysis
- [x] Step 5: chat panel in React (CRA), end-to-end tests. Done on Nov 25, 2026 (AssistantChat, CORS, a real-login end-to-end test; frontend 217, AI service 271, Flask 480)
- [x] Fine-tuning phase (Nov 26, 2026): precise questions about the owner's transactions.
  - Flask `GET /transactions/query` replaced `/transactions/summary`. The model fills in a validated structured query, never SQL.
  - The AI tool `query_transactions` replaced two tools.
  - Chat history: the last 3 turns, not stored.
  - Money movement (transfers, card bills, investments) is kept out of spending totals, configured by `MONEY_MOVEMENT_CATEGORIES`.
  - Help mode points to "My data" when it finds nothing.
  - Tests: Flask 491, AI service 288, frontend 221 (223 after round 2: named things searched by name, follow-ups keep the previous search, double welcome fixed).
  - Rounds 3–4: `must_match` (AND search), and "the model picks rows by meaning, the code adds them up" (`add_up_transactions`) for small sets such as one trip. Tests: AI service 297, frontend 224.
  - Before deploying: set `MONEY_MOVEMENT_CATEGORIES` on Render.
  - Before deploying: `ASSISTANT_LIMITS_ENABLED` must be `true` (or unset); it is `false` locally only for testing (Nov 26).
  - Nov 27: code writes My-data answers (1 trip for simple questions, 2 for picks); Gemini takes any trip Groq fails; tokens per trip logged.
  - Before deploying: apply AI migration `0005_audit_trips` on Supabase.
  - Before deploying: `MONEY_MOVEMENT_CATEGORIES` on Render must include `repayment` (owner's change, Nov 27).
  - To do: savings transactions in the transaction query (deposit/withdrawal mapping).
  - Done (Nov 27): savings transactions in the transaction query; open question: should savings deposits count as income?
  - Nov 27: savings deposits left out of totals (owner's decision); the chat is on every signed-in page; three help-mode notes added (money basics, payments in India, PPA terms). The owner runs `python -m app.rag.ingest`; before deploying, ingest into Supabase too.
  - Nov 27: help-mode "Click here" links to the right page, form and account (action names from code, fixed destinations in the browser, live user-specific account picker).
  - Full test run before step 6 (Nov 27): Flask 497, AI service 385, frontend 244, all passing; frontend production build succeeds.
- [ ] Step 6: measure, then choose hosting
  - Nov 27: measured in a 512 MB / 0.1 CPU Linux container: 45 MB idle, 47 MB peak at about 99 requests/s, about 10 s startup, 261 MB image. Recommended: Render free web service (root `ai_service`) plus the Supabase `ai` schema with a restricted role. Watch: 750 free instance hours a month are shared by Flask and the AI service.
  - Nov 27: AI service deploys like Flask: `ai_service/Dockerfile` + `start.sh` apply AI migrations and sync help notes to Supabase on every deploy. One-time Supabase setup in `ai_service/db/supabase_setup.sql` (restricted login `ppa_ai_app`, owns only the `ai` schema). Rehearsed locally; the migration runner fix found there is in `app/migrate.py`. Exact steps: `ai_service/README.md`, "Deploying: Render (free) + Supabase".
  - Follow-up: the CI workflow does not run the AI service tests yet.

Root `pytest.ini` now has `testpaths = tests`, so Flask's test run does not collect the AI service tests. Details are in `ai_service/README.md`.

### Remaining Roadmap

After the above work: Docker integrated into CI, automated deployment, production security/configuration, reliability, logging and monitoring, system design, and optional advanced engineering.

---

## Completed

### Application Foundation

* [x] Flask Backend
* [x] React Frontend
* [x] PostgreSQL Integration
* [x] JWT Authentication
* [x] SQLAlchemy ORM
* [x] Flask-Migrate
* [x] React Routing / Components
* [x] Financial modules
* [x] Dashboard

### Deployment

* [x] Vercel Frontend Deployment (auto-deploys on push)
* [x] Render Backend Deployment (manual deploys only)
* [x] Supabase PostgreSQL
* [x] Render Key Value (Redis) for the dashboard cache

All hosting must stay on free tiers.

### Docker

* [x] Docker Fundamentals
* [x] Backend Dockerization
* [x] Frontend Dockerization
* [x] PostgreSQL Container
* [x] Docker Volumes
* [x] Docker Networking
* [x] Docker Compose
* [x] Local Docker environment validation

### Git / GitHub

* [x] Separate working branches
* [x] Repository cleanup for generated files and local environments
* [x] Environment/secrets protection
* [x] Reviewed staged changes before commits
* [x] Pull Requests
* [x] PR review / secret review
* [x] Merged PR workflow
* [x] Safe local main synchronization
* [x] Clean working tree verification
* [x] `.gitattributes` for shell scripts

### GitHub Actions CI

* [x] Pull Request CI
* [x] Main branch CI
* [x] Ubuntu runner, PostgreSQL 17 service
* [x] Python 3.12 setup and backend dependency installation
* [x] Backend Python validation
* [x] Backend pytest execution (`pytest -q`)
* [x] Node 22 setup and `npm ci`
* [x] Frontend Jest tests (`npm test -- --watchAll=false`) — added in Phase 3
* [x] CI triggers include the production branch `perf/add-request-diagnostics`, plus `workflow_dispatch`
* [x] First green run on the production branch (GitHub Actions run 45152442674 on `558f7b3`: backend `465 passed, 5 warnings`, frontend `201 passed` (14 suites), build compiled)
* [x] React production build validation
* [x] CI-only JWT key of sufficient length (32+ bytes)
* [x] CI failure/recovery exercise

---

## Phase 3A — Backend Regression

### Modules Covered

* [x] Authentication / Registration / Login / `/me`
* [x] User API and deletion rules
* [x] Banks (including cursor pagination, filters and query-count checks)
* [x] Savings
* [x] Assets
* [x] Transaction exports / backup
* [x] Credit Cards
* [x] Dashboard and dashboard Redis cache
* [x] Rate limiting (`tests/test_rate_limiting.py`)
* [x] Token lifecycle (`tests/test_token_lifecycle.py`)
* [x] API-wide hardening (`tests/test_api_hardening.py`)

### Defect Found and Fixed — Credit-Card Billing Summary

`POST /credit_cards/<id>/process_billing` did not return `transactions_billed` or `total_amount_billed`, although the credit-card page displays both in its billing-details panel. The backend now returns them, computed before payments are re-applied. Existing billing calculations were not changed. `tests/test_credit_cards.py` asserts the new fields for the empty and the mixed-transactions cases.

### Bank Transaction History

`tests/test_banks.py` covers cursor pagination and filter-scope mismatch, malformed cursors, stable continuation when newer rows are inserted, combined filters across pages, legacy page-number compatibility, IST date boundaries, amount bands, search contract, invalid filters and authorization.

The query-count test now expects **three** SELECT statements on the cursor path, not two: the first one is the per-request token revocation check added in Phase 3B. The test still proves there is no `COUNT(*)` on the cursor path.

### Credit-Card Timestamp Note

Credit-card transaction datetime/timezone behavior is sensitive across local and Render environments. The testing work intentionally did not refactor the existing timestamp conversion/order logic. The five remaining test warnings (`datetime.utcnow()` deprecation) are left for the same reason.

### Backend Regression History

| Date | Result | Notes |
|---|---|---|
| Earlier notes | `389 passed`, then `411 passed`, 5 warnings | Historical |
| Nov 22, 2026 | `414 passed`, 5 warnings | Phase 3A baseline |
| Nov 23, 2026 | `465 passed`, 5 warnings | After rate limiting, token lifecycle and hardening tests |

Do not change financial calculations or timestamp behavior merely to make a test pass. First determine whether the test setup or expectation is incorrect, or whether the application has a genuine defect.

---

## Phase 3B — Auth and API Security

Audit findings (November 22, 2026) that started this work: no rate limiting, no forwarded-header handling, no request-size limit, no logout/revocation (tokens stayed valid for their full one-day lifetime), exception text returned in 500 replies, and CORS advertising credentials that the app does not use.

### Rate Limiting (Flask-Limiter)

* [x] `/login` per client IP: `10 per minute;50 per hour` (every attempt counts)
* [x] `/login` per account: `5 per 15 minutes`, counting only failed (401) attempts; key is a SHA-256 digest of the username
* [x] `/register` per client IP: `3 per hour`
* [x] Profile password change: `5 per 15 minutes` wrong current-password attempts per account
* [x] Limits are checked before the view runs, so blocked requests never reach password hashing (about 0.4 s of CPU each)
* [x] Moving-window strategy; counters in the existing Redis under `ppa:ratelimit`, every key with a TTL
* [x] Falls back to per-process memory with the same limits if Redis is unreachable; Redis errors never turn a normal reply into a 500
* [x] JSON 429 with a readable wait time and `retry_after`
* [x] `ProxyFix` trusts exactly `TRUSTED_PROXY_COUNT` proxies, so clients cannot choose their own bucket with a fake `X-Forwarded-For`
* [x] Unknown usernames are checked against a dummy hash, so response time does not reveal which usernames exist

All limits can be changed through environment variables (see `config.py`).

### JWT Lifecycle

* [x] `POST /logout` revokes the current token (its `jti` is stored in the new `revoked_token` table)
* [x] `POST /logout-all` increments `user.token_version`, which invalidates every token issued earlier (`ver` claim)
* [x] Changing the password requires `current_password`, ends all other sessions, and returns a fresh token for the current device
* [x] Tokens of deleted accounts are rejected
* [x] Every token problem (expired, revoked, invalid signature, malformed, missing) returns **401** with `{"error": ...}`. Flask-JWT-Extended's default 422 for invalid tokens left the frontend stuck with a dead token.
* [x] Tokens issued before this change have no `ver` claim and are treated as version 0, so deploying does not log anyone out
* [x] One combined query per authenticated request checks both the version and the revocation list
* [x] Revocation state lives in PostgreSQL, not Redis: the Redis instance is a disposable `allkeys-lru` cache, and an evicted revocation would silently re-enable a logged-out token
* [x] Startup warning when `JWT_SECRET_KEY` is shorter than 32 bytes
* [ ] Refresh tokens / shorter access-token lifetime — deferred (Step 2)
* [ ] Moving the token out of `localStorage` — deferred; depends on the refresh-token design

Migration: `migrations/versions/0557b33bd281_add_token_revocation.py` (additive: `user.token_version` with default 0, new `revoked_token` table and index). It must be applied **before** the new backend is deployed. The old backend keeps working against the upgraded schema.

Frontend: the Profile dialog has a "Current Password" field, a hint that changing the password logs out other devices, and a "Log out of all devices" button. Logout now also revokes the token on the server (without blocking the UI if that call fails).

### API Hardening

* [x] `MAX_CONTENT_LENGTH` (default 256 KB, `MAX_REQUEST_KB`) with a JSON 413
* [x] 15 handlers that returned `str(e)` in 500 replies now use `server_error()`: generic message to the client, full traceback in the server log
* [x] Unhandled exceptions return a generic JSON 500
* [x] Route-coverage test: every route except `/`, `/login`, `/register` and static files must return 401 without a token
* [x] Dead commented-out code removed from `app/routes.py` (old unauthenticated `/transfers` and other endpoints that were not live), plus the unused `createTransfer` frontend helper
* [x] CORS: `supports_credentials` disabled and `withCredentials` removed from the frontend (the token is sent in a header, not a cookie)
* [x] API security headers: `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Strict-Transport-Security`
* [ ] Frontend security headers / CSP on Vercel — deferred (no `vercel.json` yet; a wrong CSP can break the live site)

### Dependency Updates

* [x] Python: Flask 3.1.3, Werkzeug 3.1.9, Jinja2 3.1.6, Mako 1.3.12, python-dotenv 1.2.2, PyJWT 2.15.0, pypdf 6.21.4, Flask-Cors 6.0.0, Pillow 13.0.0; Flask-Limiter 4.1.1 added. `pip-audit`: no known vulnerabilities.
* [x] Frontend: axios 1.21.1, react-router-dom 7.18.6. No package that ships to the browser is flagged by `npm audit`.
* [ ] 64 remaining `npm audit` advisories are in Create React App build tooling only; fixing them means migrating off CRA (for example to Vite), which is a separate task.

---

## Phase 3C — Frontend Automated Tests

* [x] Missing `@testing-library/jest-dom` dependency added, plus `@testing-library/dom` and `@testing-library/user-event`
* [x] `setupTests.js` polyfills for jsdom (`TextEncoder`, `matchMedia`, `ResizeObserver`) and `localStorage` cleanup after each test
* [x] Jest `moduleNameMapper` entries so axios and react-router v7 load under CRA's Jest
* [x] Starter `App.test.js` replaced with routing/auth tests
* [x] Pages: Login, Dashboard, Banks, Savings, Assets, Credit Cards
* [x] Components: Modal, DataTable, delete confirmation, transaction table, Profile dialog
* [x] Services: `api.js` (token handling, 401 logout, session helpers) and backend status
* [x] Accessibility fix found by the tests: each `Modal` now gets a unique title id (`useId`) instead of a shared `modal-title`

Result: `201 passed` in 14 suites (local, November 23, 2026).

---

## Phase 3 Completion Criteria

- [x] Meaningful backend coverage gaps reviewed and addressed
- [x] Backend automated tests pass locally (`465 passed`)
- [x] Frontend automated testing established (`201 passed`)
- [x] Frontend test setup reproducible from committed dependency files (once committed)
- [x] Workflow defines backend tests, frontend tests and the React build
- [x] Targeted auth/API security hardening with regression tests
- [x] Documentation updated
- [x] Changes reviewed, committed and pushed (`306bdb8` on `perf/add-request-diagnostics`)
- [x] Production configuration and deployment completed (see checklist below)
- [x] CI triggers cover the production branch
- [x] A CI run on the production branch passes
- [x] `TRUSTED_PROXY_COUNT` measured and set (3)
- [ ] Required-check / branch-protection settings (optional for a single-developer repo)

---

## Deployment Checklist for This Change Set

**Completed on November 23, 2026** (`TRUSTED_PROXY_COUNT` was set to 3 later the same day, after measuring). Kept as the reference order for future backend/frontend changes. Order matters because the frontend auto-deploys on push and the backend is deployed manually.

1. **Generate a strong JWT key** (32+ random bytes), e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Set it as `JWT_SECRET_KEY` on Render and in the local `.env`. Changing it logs every user out once; they now get a clean 401 and the login page.
2. **Set `TRUSTED_PROXY_COUNT` on Render** to the real number of proxies that append to `X-Forwarded-For` (check the header first). `0` makes everyone share the proxy's IP bucket; too high lets clients spoof their IP.
3. **Check Render Key Value**: eviction policy and memory headroom (rate-limit counters share it with the dashboard cache).
4. **Apply migration `0557b33bd281` to Supabase** (`flask db upgrade`) before deploying the backend. It is additive and safe for the currently running backend.
5. **Push** (Vercel deploys the frontend). The new frontend no longer sends credentials and works with both the old and the new backend. Pushing first matters: the old frontend still requests credentials, which the new backend no longer allows.
6. **Deploy the backend manually on Render.**
7. **Verify in production:** login, a wrong password, logout, logout-all, password change, dashboard `X-Dashboard-Cache`, and that a 429 appears after repeated failed logins.
8. **Confirm the GitHub Actions run** for the pushed branch is green.

Optional cleanup: delete the leftover `~*` folders in `venv\Lib\site-packages` from the pip upgrade (Windows locked them; they are harmless).

---

## Future Phases

### RAG and AI Integration (after Phase 3)

**Status (November 24, 2026): in progress, local only. Steps 1–3 done; see "Planned After Phase 3 — RAG and AI Integration" above and `AI_AND_RAG.md`.** The original plan below is kept for reference.

**Update (later on November 24, 2026): step 4 done.**

- **"My data" mode:** five read-only tools over Flask's GET endpoints, called with the user's token.
  - Groq only; Python computes; a number check.
  - At most 3 tool calls; the figures are returned with every answer.
- **AI-service logging:** structured logs, request id, allowlist and redaction, a Groq quota warning, and an audit report.
- **Tests:** 269 (AI service), 468 (Flask).

**Update (November 25, 2026):** new Flask endpoint `GET /transactions/summary` (`app/transactions/transaction_summary.py`).

- PostgreSQL computes totals by type, category, India-time month and account, plus the largest 5, for the logged-in user's bank and card transactions.
- The AI tool uses it instead of paging through rows, so totals cover thousands of transactions; measured at 26 ms for 5,000 rows.
- 12 new Flask tests.
- No migration needed.

**Original status: Planned. Not implemented.**

The goal is to develop two related projects:

1. A separate project-document learning chatbot for understanding RAG concepts.
2. PPA Finance Copilot, initially grounded in approved documentation and trusted financial-education material.

Planned work:

- [ ] Learn document ingestion, extraction, chunking, metadata and embeddings.
- [ ] Evaluate PostgreSQL `pgvector` and PostgreSQL full-text search.
- [ ] Implement retrieval, context construction and grounded answer generation.
- [ ] Return source references and handle insufficient evidence.
- [ ] Integrate the Knowledge Copilot into the React frontend and Flask backend.
- [ ] Create a repeatable evaluation dataset and automated tests.
- [ ] Add model credentials, usage controls and appropriate error handling.
- [ ] Document the RAG architecture and its data flows.

Personalized financial analysis is a later extension. The backend must calculate exact financial values and enforce authorization. Private financial-data tools must not be enabled until the required Phase 6 security controls are in place.

---

### Phase 4 — Docker Integrated into CI

* [ ] Build backend Docker image in CI
* [ ] Build frontend Docker image in CI
* [ ] Verify Docker image builds successfully

### Phase 5 — Continuous Deployment

* [ ] Automated Render deployment
* [ ] Deployment triggers
* [ ] Deployment secrets
* [ ] Deployment failure handling
* [ ] Rollback strategy

### Phase 6 — Production Configuration & Security

* [ ] Separate Local / Docker / CI / Production configuration model
* [ ] Review secrets management
* [ ] Review production environment variables
* [x] Initial API security hardening (Phase 3B: rate limiting, token revocation, request limits, CORS, error replies, headers)
* [ ] Refresh tokens and token storage
* [ ] Frontend CSP / security headers on Vercel
* [ ] Migrate off Create React App build tooling

### Phase 7 — Production Reliability

* [ ] Health endpoint
* [ ] Deployment health checks
* [ ] Migration-aware deployment flow
* [ ] Rollback handling

### Phase 8 — Logging & Monitoring

* [ ] Application logs
* [x] Server-side logging of unexpected 500 errors (details no longer sent to clients)
* [x] AI service only (local, Nov 24, 2026): structured application logs with request ids, an allowlist of fields and redaction; a Groq quota warning; an audit-table report (`python -m app.report`)
* [ ] Database error visibility
* [ ] Health monitoring
* [ ] Alerts

### Phase 9 — System Design & Scalability

- [ ] Document architecture and trade-offs
- [ ] Scalability analysis
- [x] Add opt-in request and SQL cursor-execution diagnostics for performance investigation
- [x] Implement optional Redis cache-aside for dashboard summary, spending and asset-allocation responses
- [x] Add per-user generation-based cache invalidation hooks after successful domain writes
- [x] Deploy Redis alongside the production backend on Render and configure it through `REDIS_URL`
- [ ] Verify cache behavior and invalidation reliability against the production Redis instance
- [ ] Verify migration and trigram-index usage with realistic query plans
- [ ] Compare local/development and production timings under comparable conditions
- [ ] Evaluate background job execution where a concrete workload requires it

### Phase 10 — Advanced / Optional Engineering

- [x] Redis — dashboard cache and rate-limit counters
- [ ] Background jobs
- [x] Caching — dashboard cache-aside with TTL and per-user generation invalidation
- [x] Rate limiting — login, registration and password change (Phase 3B)
- [ ] API versioning
- [ ] Advanced authentication (refresh tokens, MFA)
- [ ] Performance testing
- [ ] Load testing
- [ ] Infrastructure as Code

Only add these when they solve a real engineering problem.

---

## Current Position

```text
Full-stack application                 ✅
Docker foundation                      ✅
Git / GitHub workflow                  ✅
GitHub Actions CI foundation           ✅

Phase 3 — Testing + Auth/API Security  ✅ COMPLETE (Nov 23, 2026)
    3A Backend regression              ✅ 465 passed (local)
    3B Rate limiting                   ✅ Verified with local Redis
    3B JWT logout / revocation         ✅ Migration checked locally
    3B API hardening + dependencies    ✅
    3C Frontend tests                  ✅ 201 passed (local)
    3D CI workflow + docs              ✅ Updated
    Commit / push                      ✅ 306bdb8
    Production config + deploy         ✅ Nov 23, 2026
    CI triggers for production branch  ✅ 558f7b3
    First green CI run                 ✅ 465 + 201 passed
    TRUSTED_PROXY_COUNT                ✅ 3 (measured on Render)

RAG & AI Integration                   🟡 IN PROGRESS (local only, nothing committed)
    Step 1 Foundation                  ✅ Nov 23
    Step 2 Knowledge base + retrieval  ✅ hit@5 1.00, MRR 0.97
    Step 3 Grounded answers API        ✅ Nov 24, 216 tests
    Step 4 Agent tools (own data)      ✅ Nov 24, "My data" mode + logging, 269 tests
    Step 5 Chat panel + E2E            ✅ Nov 25, real-login E2E passed
    Fine-tuning (precise questions)    ✅ Nov 26, structured queries + chat history
    Step 6 Hosting decision            ← NEXT
Phase 4 — Docker in CI                 ⏳
Phase 5 — Automated deployment         ⏳
Phase 6 — Security / configuration     🟡 Started (Phase 3B)
Phase 7 — Reliability                  ⏳
Phase 8 — Logging / monitoring         🟡 Started (AI service logging, local)
Phase 9 — System design / scalability  🟡 IN PROGRESS
Phase 10 — Advanced engineering        🟡 PARTIALLY COMPLETE
```

Phase 3 is complete. Deferred security items (refresh tokens, token storage, frontend CSP, leaving Create React App) are tracked under Phase 6. The RAG and AI Integration phase is in progress locally (see `AI_AND_RAG.md`).
