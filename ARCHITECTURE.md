# PPA Architecture

## High-Level Architecture

```
                   User
                     │
                     ▼
              React Frontend
                     │
          HTTP / REST API Calls
                     │
                     ▼
               Flask Backend
                     │
        SQLAlchemy ORM + JWT Auth
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
   PostgreSQL Database    Optional Redis
   (source of truth,      (dashboard cache +
    token revocation)      rate-limit counters)
```

PostgreSQL remains the source of truth, including all security state (token versions and revoked tokens). Redis is used only when `REDIS_URL` is configured and reachable. It holds disposable data: dashboard cache entries and rate-limit counters, both with expiry times.

---

# Current Deployment Architecture

```
                User
                  │
                  ▼
         Vercel (React Frontend)
                  │
                  ▼
         Render (Flask Backend)
                  │
          ┌───────┴────────┐
          │                │
          ▼                ▼
  Supabase PostgreSQL   Render Redis
  (source of truth)     (dashboard cache,
                         rate-limit counters)
```

Vercel deploys the frontend automatically on every push. The Render backend is deployed manually. Supabase needs no deployment, but migrations are applied to it by hand.

The production deployment includes a Redis service on Render alongside the Flask backend. The backend connects through `REDIS_URL`; PostgreSQL remains the source of truth. Redis caches dashboard aggregates and, once the Phase 3 changes are deployed, also stores rate-limit counters under a separate `ppa:ratelimit` key prefix. Runtime connectivity should be confirmed from the dashboard response's `X-Dashboard-Cache` header (`HIT`, `MISS` or `BYPASS`). If Redis is missing or unavailable, dashboard calculations fall back to PostgreSQL.

---

# Backend Components

```
run.py
    │
    ▼
create_app()
    │
    ▼
Flask Application
    │
    ├── JWT Authentication (+ revocation check, uniform 401 replies)
    ├── SQLAlchemy
    ├── Flask-Migrate
    ├── CORS (no credentials)
    ├── ProxyFix (only when TRUSTED_PROXY_COUNT > 0)
    ├── Rate limiting (Flask-Limiter)
    ├── JSON error handlers (413, generic 500)
    ├── Security response headers
    ├── Optional Redis client
    ├── Optional request / SQL diagnostics
    └── Routes / Blueprints
```

The Redis client is initialized only when `REDIS_URL` is set. The performance event listeners are attached only when `PPA_PERF_DIAGNOSTICS` is enabled during application creation.

---

# Backend Folder Structure

```
app/
├── __init__.py
├── models.py
├── routes.py
├── login/
│   └── login_routes.py
├── users/
│   └── users_routes.py
├── banks/
│   ├── bank_routes.py
│   └── bank_util.py
├── savings/
│   ├── savings_routes.py
│   └── savings_util.py
├── assets/
│   ├── assets_routes.py
│   └── assets_util.py
├── credit_cards/
│   ├── credit_card_routes.py
│   └── credit_card_util.py
├── dashboard/
│   ├── dashboard_routes.py
│   └── dashboard_service.py
└── utils/
    ├── date_util.py
    ├── financial_util.py
    ├── transaction_export_util.py
    ├── dashboard_cache.py
    ├── auth_tokens.py     # token creation, revocation, JWT error callbacks
    ├── rate_limit.py      # Flask-Limiter setup, keys, ProxyFix, JSON 429
    └── errors.py          # JSON 413 / generic 500 handlers, server_error()

migrations/           # Flask-Migrate / Alembic migrations
tests/                # Backend pytest suite
portfolio-app/        # React frontend
.github/workflows/    # GitHub Actions workflows
```

---

# Frontend

```
React
│
├── Components
├── Pages
├── Services
├── Routing
└── API Integration
```

The bank transaction screen delegates search, filters and pagination to the backend. The shared `TransactionTableDialog` renders both cursor-pagination and legacy page-number modes. Search input is debounced, the bank page keeps cursor history in a React ref, and the first page is refreshed after a new transaction is created.

The desktop navigation sidebar uses `position: sticky` below the header and has its own vertical scroll container. It is not viewport-fixed. Mobile navigation retains overlay/close-on-navigation behavior.

`src/services/api.js` attaches the stored token as `Authorization: Bearer ...`, logs the user out on any 401, and does not send cookies (`withCredentials` was removed). It also provides `logoutSession(token)` and `logoutAllDevices()`. The Profile dialog uses them for Logout (server revocation that does not block the UI) and for "Log out of all devices". A password change requires the current password and stores the new token returned by the backend.

Frontend tests use Jest and React Testing Library through `react-scripts test`. They have 14 suites covering pages, shared components and the API service layer. `src/setupTests.js` provides the jsdom polyfills, and the `jest.moduleNameMapper` entries in `package.json` let axios and react-router v7 load under CRA's Jest.

---

# Database

```
PostgreSQL

Users
│
├── Credit Cards
├── Assets
├── Investments
├── Savings
└── Banks

Shared transaction table
│
├── Bank transactions
├── Credit-card transactions
└── Other transaction subclasses

Auth state
│
├── user.token_version   (integer, default 0)
└── revoked_token        (jti PK, expires_at indexed)
```

---

# Authentication and API Security

Added in Phase 3B. Code: `app/utils/auth_tokens.py`, `app/utils/rate_limit.py`, `app/utils/errors.py`, `app/__init__.py`.

## Request path

```text
Request
   │
   ▼
ProxyFix (TRUSTED_PROXY_COUNT hops) ── real client IP
   │
   ▼
Body larger than MAX_CONTENT_LENGTH? ──yes──> 413 JSON
   │
   ▼
Rate-limit check (before_request, before the view) ──over──> 429 JSON
   │
   ▼
@jwt_required: signature + expiry
   │
   ▼
Revocation check: one query
   SELECT user.token_version, EXISTS(revoked_token.jti = token jti)
   │
   ├── user missing / jti revoked / ver != token_version ──> 401
   ▼
View
   │
   ▼
after_request: security headers (CSP, X-Frame-Options, nosniff,
               Referrer-Policy, HSTS)
```

Every token problem (missing, expired, revoked, bad signature, malformed) returns **401** with `{"error": "..."}`. The frontend logs the user out on 401. Flask-JWT-Extended answers invalid tokens with 422 by default, and the frontend did not handle that.

## Token lifecycle

| Action | Mechanism | Effect |
|---|---|---|
| Login | Access token with claims `sub`, `jti`, `ver` | `ver` = current `user.token_version` |
| `POST /logout` | Insert the token's `jti` into `revoked_token` (expired rows pruned first) | Only this device is logged out |
| `POST /logout-all` | Atomic `token_version = token_version + 1` | Every earlier token fails the `ver` check |
| Password change (`PUT /users/<id>` with `password`) | Requires `current_password`; increments `token_version`; returns a new `token` | Other devices are logged out; this device continues with the new token |
| Account deleted | User row is missing | Token rejected |

Tokens issued before this design have no `ver` claim and are treated as version 0. Because the migration gives existing users `token_version = 0`, deploying it does not log anyone out.

**Why PostgreSQL and not Redis:** the Redis instance is a cache with `allkeys-lru` eviction. If a revocation entry were evicted, a logged-out token would silently become valid again. Security state therefore lives in PostgreSQL, at the cost of one small indexed query per authenticated request.

Not implemented yet: refresh tokens (access tokens still last one day) and moving the token out of `localStorage`.

## Rate limits

| Endpoint | Key | Default limit | What counts |
|---|---|---|---|
| `POST /login` | Client IP | `10 per minute;50 per hour` | Every attempt |
| `POST /login` | SHA-256 of submitted username | `5 per 15 minutes` | Only 401 replies |
| `POST /register` | Client IP | `3 per hour` | Every attempt |
| `PUT /users/<id>` | Account id in the URL | `5 per 15 minutes` | Only wrong current passwords |

- Limits are configured through environment variables (`LOGIN_RATE_LIMIT`, `LOGIN_FAILURE_RATE_LIMIT`, `REGISTER_RATE_LIMIT`, `PASSWORD_CHANGE_FAILURE_RATE_LIMIT`).
- The strategy is moving-window, and counters are stored in Redis under `ppa:ratelimit` with a TTL. If Redis is unreachable, Flask-Limiter falls back to per-process memory with the same limits. Storage errors are swallowed, so they never turn a normal reply into a 500.
- Limits run before the view, so a blocked request never reaches PBKDF2 password hashing (about 0.4 s of CPU on the single Gunicorn worker).
- Unknown usernames are checked against a dummy hash, so the login response time does not reveal whether an account exists.
- `TRUSTED_PROXY_COUNT` must match the real number of proxies on Render. If it is `0`, every user shares the proxy's IP bucket. If it is too high, clients can spoof their IP with `X-Forwarded-For`.
- To find the right value, set `PROXY_DIAGNOSTICS=true` temporarily. Every `GET /` then logs one `ppa_proxy_diagnostics` WARNING line containing the socket peer, the `X-Forwarded-For` list and its length, `True-Client-IP` / `CF-Connecting-IP` / `X-Real-IP` if present, and the address the rate limiter would use. Send a request with a fake `X-Forwarded-For` value: the real client IP's position counted from the right is the hop count. The log contains IP addresses, so switch the flag off afterwards.
- Measured on Render on November 23, 2026 with the `PROXY_DIAGNOSTICS` log: every request arrives with three `X-Forwarded-For` entries appended by infrastructure (client IP, then a Cloudflare edge address `104.23.x.x`, then Render's internal load balancer `10.x.x.x`), and a local proxy inside the container connects to gunicorn from `127.0.0.1`. The client IP also matches `True-Client-IP` / `CF-Connecting-IP`. A request with a fake `X-Forwarded-For: 6.6.6.6` showed the fake value as a fourth entry on the far left, so **`TRUSTED_PROXY_COUNT=3`** is set in production. With 3, a shorter-than-expected chain falls back to `127.0.0.1` (the shared bucket) instead of trusting a client value. Residual risk: a client able to reach Render's load balancer without Cloudflare could fake one entry; the per-account login limit still applies. If Render changes its routing, re-measure.

## Error replies, size limit, CORS

- `MAX_CONTENT_LENGTH` (default 256 KB, set with `MAX_REQUEST_KB`) rejects larger bodies with a JSON 413.
- Handled server errors call `server_error()`, which logs the full traceback and returns `{"error": "Something went wrong on our side. Please try again."}`. Unhandled exceptions get the same generic JSON 500. Exception text is never sent to the client.
- CORS allows only `CORS_ORIGINS`, without `Access-Control-Allow-Credentials`. The token is sent in the `Authorization` header, not a cookie, so cross-site credentials are not needed.
- `tests/test_api_hardening.py` calls every registered route without a token. Only `/`, `/login`, `/register` and static files may answer with something other than 401.

## Deployment ordering for these changes

1. Apply migration `0557b33bd281` to Supabase. It is additive, and the running old backend keeps working.
2. Push. Vercel deploys the new frontend, which no longer sends credentials and works with both backends.
3. Deploy the backend on Render.

Deploying the backend before the frontend would break every request from the old frontend, because the old frontend still asks for credentials and the new backend no longer allows them.

---

# Bank Transaction API — Filtering and Cursor Pagination

The bank transaction endpoint is scoped by both `bank_id` and the authenticated `user_id`. Ownership is checked on every request before transaction rows are returned.

## Query filters

| Parameter | Behavior |
|---|---|
| `search` | Case-insensitive substring search over description or category only |
| `type` | `income` or `expense` |
| `start_date` | Inclusive start of an IST calendar date (`YYYY-MM-DD`) |
| `end_date` | Inclusive end of an IST calendar date (`YYYY-MM-DD`) |
| `amount_range` | One of the five predefined amount bands |
| `page_size` | Clamped to 1–100; default 25 |
| `cursor` | Opaque continuation value for the next keyset page |

Free-text search deliberately excludes amount, date, transaction type and balance-after. These are not part of the text-search contract.

## Cursor pagination flow

The normal/new-client path uses keyset pagination:

```text
Authenticated request + bank ID
        │
        ▼
Verify bank belongs to authenticated user
        │
        ▼
Apply transaction type / text / date / amount filters
        │
        ▼
Order by date DESC, id DESC
        │
        ▼
Decode and validate cursor (if supplied)
        │
        ▼
Filter tuple (date, id) < cursor tuple
        │
        ▼
Fetch page_size + 1 rows
        │
        ├── Extra row exists → has_more = true
        │
        └── No extra row → has_more = false
        │
        ▼
Return transactions + next_cursor
```

The secondary `id DESC` order makes the order deterministic when transaction timestamps are equal. The next-page predicate compares `(date, id)` lexicographically. Fetching one extra record determines whether another page exists without calculating an exact `COUNT(*)` on the normal cursor path.

### Legacy compatibility path

If a request includes the `page` parameter, the endpoint retains the older page-number contract with `page`, `total`, `total_pages`, offset pagination and an exact count. This compatibility path is not the normal request shape used by the updated frontend.

### Cursor scope and security boundary

The URL-safe Base64 cursor contains a version, the stored timestamp, transaction ID and a SHA-256 digest of the active filter scope. The digest prevents accidental reuse with a different bank/user/page size/filter combination. It is not a keyed signature, and Base64 is not encryption. Authorization is still performed independently by the route. The cursor is not an authorization credential.

---

# Bank Transaction Date and Amount Filtering

## IST date boundary conversion

Transaction timestamps follow the application's naive-UTC storage convention. A selected IST calendar day is translated to UTC midnight boundaries, then the database timestamp column is filtered directly:

```text
start_utc = IST midnight on start_date converted to naive UTC
end_utc_exclusive = IST midnight on (end_date + 1 day) converted to naive UTC

WHERE transaction.date >= start_utc
  AND transaction.date < end_utc_exclusive
```

The exclusive end boundary makes the user's selected end date inclusive without manufacturing an end-of-day timestamp. IST midnight is 18:30 on the previous UTC date. Keeping the database column unwrapped also preserves the opportunity to use a normal index on that column.

## Amount bands

The filters use lower-inclusive, upper-exclusive intervals to avoid overlapping boundaries:

- `under_500`: `amount >= 0 AND amount < 500`
- `500_1000`: `amount >= 500 AND amount < 1000`
- `1000_5000`: `amount >= 1000 AND amount < 5000`
- `5000_10000`: `amount >= 5000 AND amount < 10000`
- `10000_plus`: `amount >= 10000`

---

# Bank Transaction Search Indexes

Migration:

`migrations/versions/7bc2e41d5a90_add_bank_transaction_search_indexes.py`

The migration enables PostgreSQL `pg_trgm` when required and creates two partial GIN trigram indexes on the shared `transaction` table:

- `ix_transaction_bank_description_trgm` — `description` using `gin_trgm_ops`
- `ix_transaction_bank_category_trgm` — `category` using `gin_trgm_ops`

Both indexes have the partial predicate `type = 'bank_transaction'` so they cover only bank-transaction rows, not the other subclasses stored in the shared table.

These indexes are intended to support the endpoint's `ILIKE '%term%'` predicates. Index creation does not prove planner selection or a performance improvement. Apply the migration to the intended PostgreSQL environment, use representative data, and verify unfiltered, date-filtered and text-search paths with `EXPLAIN (ANALYZE, BUFFERS)`.

The existing transaction ordering index should also be considered when inspecting the normal `date DESC, id DESC` page query.

---

# Dashboard Redis Cache Architecture

Redis is a cache-aside layer for three dashboard resources in the Render production deployment. The code keeps Redis optional so local/CI environments and deployments without Redis can use PostgreSQL fallback:

- Dashboard summary
- Spending for a supported range (`30d`, `3m`, `6m`, `1y`, `all`)
- Asset allocation

PostgreSQL remains authoritative. Cache configuration is supplied through environment variables:

| Variable | Default / behavior |
|---|---|
| `REDIS_URL` | Render Redis connection URL in production; enables Redis when supplied |
| `DASHBOARD_CACHE_TTL_SECONDS` | 60 seconds |
| `REDIS_MAX_CONNECTIONS` | 5 connections |

Redis client options in the application use short socket connect/read timeouts and a health-check interval. The testing configuration sets `REDIS_URL = None`, so unit/integration tests do not require an external Redis server.

## Cache-aside read path

```text
Dashboard GET request
        │
        ▼
Read user's generation token from Redis
        │
        ▼
Build namespaced cache key:
user + generation + resource (+ spending range)
        │
        ▼
Read cached payload
        │
        ├── HIT ──> Recheck generation ──> Return cached payload
        │
        └── MISS / BYPASS
                    │
                    ▼
             Calculate using PostgreSQL
                    │
                    ▼
             Store using observed generation
                    │
                    ▼
                 Return result
```

Dashboard responses expose `X-Dashboard-Cache` with `HIT`, `MISS` or `BYPASS`. This header shows which cache path was taken; it is not a latency measurement.

## Invalidation strategy

Each user has a generation key. After a successful database commit, write handlers rotate that user's generation token. New cache lookups therefore use a new namespace, so all previous cache entries for that user become unreachable without scanning Redis keys.

The reviewed branch adds invalidation hooks in bank, savings, assets, credit-card and user route modules. New write paths must be assessed for whether they affect dashboard summary, spending or asset allocation; if they do, invalidation must be included after the database commit.

## Failure and consistency behavior

- When `REDIS_URL` is absent, the application bypasses the cache and calculates from PostgreSQL.
- Redis read/write errors are logged and dashboard requests fall back to PostgreSQL.
- A Redis failure must not convert a successful financial database write into an API failure.
- If invalidation fails after the database commit, the old cached generation can remain visible until its short TTL expires. This is bounded staleness, not immediate consistency.

The current `docker-compose.yml` does not define a Redis service and does not pass `REDIS_URL` into the backend container. The present local Compose configuration therefore does not enable the Redis cache. Production Redis is configured separately on Render; a local Docker Redis setup would require explicit service and environment wiring.

---

# Performance Diagnostics

The Flask application supports opt-in request and SQL cursor-execution diagnostics through:

```text
PPA_PERF_DIAGNOSTICS=true
```

It is disabled by default. When enabled:

- A request ID is generated and returned in `X-Request-ID`.
- Structured `ppa_perf` logs include method, endpoint, response status and application elapsed time.
- The log records time until the first SQL execution starts, SQL execution count and accumulated DBAPI cursor-execution time.
- SQL statements, SQL parameters, request bodies, query strings, user IDs and financial values are intentionally not logged.

`sql_execute_ms` does not include all result fetching, ORM processing, JSON serialization, network transfer or frontend rendering. Use it as one diagnostic signal alongside browser timing, request elapsed time and query plans.

The SQLAlchemy event listeners are attached during app creation only when the diagnostics flag is enabled. Restart/recreate the application after changing the setting.

---

# Planned RAG / AI Extension (after Phase 3)

**Status (November 24, 2026): partly implemented locally; see "AI Service Architecture" below for what exists now.** The original plan is kept here for reference.

**Original status: Planned; not implemented in the reviewed repository.**

The initial PPA Knowledge Copilot will use approved project documentation and trusted financial-education material.

```text
Approved Documents
        |
        v
Text Extraction
        |
        v
Chunking + Metadata
        |
        v
Embeddings
        |
        v
PostgreSQL + pgvector
        |
        v
Semantic / Keyword Retrieval
        |
        v
Relevant Context + User Question
        |
        v
LLM Generation
        |
        v
Grounded Answer + Source References
```

The initial implementation should reuse Flask, React and PostgreSQL wherever practical.

Planned responsibilities:

- Document ingestion and update handling
- Chunking and source metadata
- Vector retrieval using `pgvector`
- PostgreSQL full-text search where useful
- Grounded answers with source references
- Insufficient-evidence handling
- Automated retrieval and answer-quality evaluation
- Error handling, latency and usage monitoring

The initial copilot will not require access to private financial transactions.

A later personalized-financial-analysis extension must use controlled, read-only backend tools. The backend must calculate exact financial results and enforce user-level authorization; the LLM must not be given arbitrary SQL execution or unrestricted access to financial data.

That extension is dependent on the required security controls in Phase 6.

This diagram is a planned target architecture, not a description of the current running application.

---

# AI Service Architecture (local, steps 1–3 done)

**Status: running locally only; not committed or deployed.** Full reasoning and history: `AI_AND_RAG.md`. Setup and API: `ai_service/README.md`.

How it differs from the plan above:

- It is a **separate async FastAPI service** (`ai_service/`), not part of Flask. LLM calls are slow network waits, so async fits; failures and heavy dependencies stay away from the finance app.
- Flask is unchanged. The AI service checks each user's token by calling Flask `GET /me`, so it never holds the JWT secret.
- It owns only the `ai` schema in its own Postgres + pgvector database (Docker, `127.0.0.1:5434`).

```text
React (CRA) ── step 5 ──►  FastAPI AI service :8001
                              │        │        │
          token check ────────┘        │        └──► Groq gpt-oss-120b (fallback: Gemini 3.5 Flash Lite)
          Flask GET /me                │
               │                       └──► Postgres 17 + pgvector (ai.documents, ai.chunks,
               ▼                                                    ai.usage_daily, ai.audit_log)
          Flask API :5000 (system of record)        Gemini gemini-embedding-001 (768-d) for search
```

Request pipeline (cheap checks first, so refused and off-topic questions cost no model tokens):

```text
per-minute + daily quota (atomic SQL)          -> 429
injection / investment-advice checks (regex)   -> refusal, 0 tokens
embed question + hybrid search (vector + keyword, RRF)
best similarity < 0.61                          -> "not covered", 0 LLM tokens
fit sources into ~1,800 tokens
Groq, fallback Gemini, max 700 output tokens    -> both down: 503 with wait time
verify citations; block ungrounded answers
-> answer + citations (+ disclaimer, + notice if cut short); usage + audit row
```

Personalized financial analysis (step 4) will follow the boundary stated above: read-only tools that call Flask's APIs with the user's own token, so Flask enforces authorization; code computes exact numbers; the model only explains them and never gets SQL access.

## Step 4: "My data" mode (local, November 24, 2026)

This is built exactly on that boundary. The user turns it on (`"mode": "my_data"`), and it uses **Groq only**, because Gemini's free-tier terms allow human review of submitted content.

```text
React ──► AI service /v1/ask {mode: "my_data"}
              │  quota + guardrails (same as help mode)
              ├──► Groq gpt-oss-120b: picks tools + arguments (sees the question and tool list only)
              │      arguments validated (Pydantic)
              ├──► Flask GET (user's own token; Flask checks ownership)
              │      /dashboard/summary, /dashboard/spending, /dashboard/asset-allocation,
              │      /banks, /banks/dropdown, /banks/<id>/transactions,
              │      /credit_cards, /credit_cards/<id>/transactions, /savings
              │      (Nov 25: transaction totals come from the new GET /transactions/summary instead
              │       of paging /banks/<id>/transactions and /credit_cards/<id>/transactions)
              │      Python computes totals, shares, by category / month, largest 5
              ├──► Groq writes the answer (at most 3 tool calls in 2 rounds)
              │      number check: every figure must be in the tool results
              ▼
          answer + the tables it came from; audit row (mode, tool names, request id)
```

## Chat Panel (React, local, November 25, 2026, step 5)

```text
Browser (React :3000, Dashboard → AssistantChat)
   │  Authorization: Bearer <same login token>     CORS: AI_CORS_ORIGINS, no cookies
   ├──► AI service :8001  POST /v1/ask {question, mode: help | my_data}, GET /v1/usage
   │        └──► Flask GET /me (token check), Flask GET data endpoints (my_data), Groq
   └──► Flask :5000 (everything else, unchanged)
```

- **The panel is hidden when `REACT_APP_AI_API_URL` is unset,** so a production build without a deployed AI service shows nothing broken.
- **Model text is rendered as React text, never as HTML.**
- **A 401 from the AI service** uses the same session-expired handling as Flask.

## My-data answer flow (AI service, local, November 27, 2026)

```
browser (AssistantChat.js) --POST /v1/ask + login token--> routes.py -> service.py (limits, guardrails)
  -> data_agent.py
       trip 1  Groq (or Gemini if Groq fails): choose tool + arguments   [system prompt ~450 tokens + tool menu ~1,350]
       tools.py -> flask_data.py --GET /transactions/query (as the user)--> Flask -> PostgreSQL
       trip 2  only to pick rows by meaning (pick rules arrive with the list), fix a bad call, or search again
  -> answer_writer.py: code writes the sentence from the query + result (no model)
  -> answer + figures/tables (model-only facts hidden) -> browser
```

- **Per-trip tokens:** stored in `ai.audit_log.trips` (migration 0005).
- **Where data goes:** questions, rows and figures may go to Groq and to Gemini (owner's decision, Nov 27). Keys and tokens never go to either.

## Transaction Query Endpoint (Flask, local, November 26, 2026)

*Update, November 27, 2026:* savings transactions are included (`account_kind` savings, and in all). A withdrawal is mapped to expense and a deposit to income. Savings rows in money-movement categories are always left out. The response has a `savings` section (rows matched, transfers left out).

`GET /transactions/query` (`app/transactions/transaction_query.py`, JWT required) answers precise, read-only questions over the user's bank and card transactions. It **replaced** `GET /transactions/summary` (described below, kept for history), whose code and tests were removed.

```
AI model ── fills in QueryArgs (validated, extra=forbid)
     │
AI service ── GET /transactions/query?terms=goa&terms=trip&type=expense&sort=date_desc&limit=10
     │          (user's own Bearer token)
Flask ─────── parse_query(): allowlists, lengths, ranges, dates → 400 on anything else
     │        _conditions(): user_id = me, bank+card only, ILIKE with escaped wildcards,
     │                       IST day bounds, amounts, money-movement categories
PostgreSQL ── totals per type · matches per word · excluded money movement · groups · rows
```

- **Two kinds of search words** (since round 3, Nov 26): `terms` (any may match) and `must_match` (up to 3, all must match), so "food in the Goa trip" is `must_match=goa` AND any of the food words.
- **Row ids and up to 30 rows** (round 4, Nov 26): rows carry `id`, so the AI service's `add_up_transactions` step can sum rows the model picked by meaning from a complete list, without another database call.
- **Alternatives** (round 5, Nov 26): a `must_match` entry may be `shree|shreya`, meaning either one, still ANDed with everything else (at most 4 alternatives).
- **Never SQL from the model:** every value becomes a bound parameter. Column and sort choices come from fixed maps.
- **Money movement:** categories in `MONEY_MOVEMENT_CATEGORIES` (env or app config, comma-separated, case-insensitive) can be included, excluded (with what was left out reported) or queried alone.
- **Limits:** 6 search words, 20 rows, 12 groups (plus an "other" amount).
- **Tests:** 23 (`tests/test_transaction_query.py`), covering:
  - another user's rows never counted;
  - savings rows excluded;
  - wildcard escaping;
  - India-time month boundaries;
  - money movement modes;
  - every grouping;
  - 13 kinds of invalid parameters.

## Transaction Summary Endpoint (Flask, local, November 25, 2026)

*Superseded on November 26, 2026 by `GET /transactions/query` (above); the text below is the original description.*

`GET /transactions/summary` (`app/transactions/transaction_summary.py`, JWT required) aggregates in PostgreSQL. It was added for the AI service, and any client can use it.

**Query parameters:**

| Parameter | Values |
|---|---|
| `account_kind` | `bank`, `credit_card` or `all` |
| `account_name` | text contained in an account name |
| `search` | text in the description or category |
| `type` | `expense`, `income` or `payment` |
| `start_date`, `end_date` | `YYYY-MM-DD`, as India-time calendar days |

**Response:**

- `transactions_found`, `first_date` and `last_date`;
- `by_type`: count, total and average for each type;
- `focus_type`: the type the groupings below describe;
- `by_category`: top 8, plus `other_categories_total`;
- `by_month`: India-time months, the last 12;
- `by_account`;
- `largest`: the 5 largest.

```text
WHERE user_id = <token user> AND type IN (bank_transaction, credit_card_transaction) [AND filters]
  -> SUM / COUNT by transaction_type
  -> focus type: GROUP BY category, IST month, account; ORDER BY amount LIMIT 5
```

- **Why SQL:** totals cover every row (thousands), take one request (26 ms for 5,000 rows) and return a ~2 KB body.
- **Amounts:** shown as positive numbers (card expenses are stored negative).
- **No new index or migration:** existing indexes cover account and date filters. An index on `(user_id, date)` is the next step if measurements on production data show it is needed.

## AI service logging (local, November 24, 2026)

```text
request ──► RequestContextMiddleware: request id (X-Request-ID), one "request finished" line
              └─► service: one "assistant request" line (labels and counts only)
                    └─► audit row with the same request_id (the only place that links to a user)
formatter: allowlist of fields + redaction (tokens, keys, emails, IPs, DB URLs)
output:    text locally (terminal); JSON lines in production (Render → Logs)
```

---

# Local Docker Compose Architecture

```
                    Browser
                       |
                       v
             React Frontend Container
                    :3000
                       |
                       | API requests
                       v
              Flask Backend Container
                    :5000
                       |
                       | SQLAlchemy / DATABASE_URL
                       v
              PostgreSQL Container
                 internal :5432

Host ports:
  React frontend   -> localhost:3000
  Flask backend    -> localhost:5000
  PostgreSQL       -> localhost:5433

Docker Compose services:
  frontend
  backend
  postgres
```

The backend service receives `PPA_PERF_DIAGNOSTICS` from Compose, but the reviewed Compose file does not map `REDIS_URL`, `DASHBOARD_CACHE_TTL_SECONDS` or `REDIS_MAX_CONNECTIONS`. Redis is therefore bypassed in the current Compose setup unless the Compose environment mapping is extended and a Redis endpoint is supplied.

---

# Current CI Pipeline

```
Developer
    |
    v
Git Commit / Push / Pull Request
    |
    v
GitHub Actions — Ubuntu Runner
    |
    +----------------------------------+
    | PostgreSQL 17 CI service         |
    | Database: ppa_test               |
    +----------------------------------+
    |
    +--> Python 3.12
    |       |
    |       +--> Install backend dependencies
    |       +--> Python compile validation
    |       +--> pytest -q
    |
    +--> Node.js 22
            |
            +--> npm ci
            +--> npm test -- --watchAll=false   (CI=true)
            +--> npm run build
```

The workflow runs the backend tests, the frontend Jest tests and the React production build. It uses a CI-only `JWT_SECRET_KEY` of at least 32 bytes, because PyJWT 2.15 warns about shorter HMAC keys. The workflow runs on pushes and pull requests for `main` and for the production branch `perf/add-request-diagnostics`, and can be started manually (`workflow_dispatch`). Vercel deploys in parallel with CI, so CI cannot block the frontend deploy; it gates the manual Render deploy by convention (deploy the backend only after a green run).

The following work is still outstanding:

- Verifying a green GitHub Actions run and the required-check settings
- Docker image builds within CI
- Automated cloud deployment

The diagram represents the workflow defined in `.github/workflows/ci.yml`. It does not prove that the latest remote run succeeded.

## Future CI/CD Pipeline

```
Developer
    |
    v
GitHub
    |
    v
GitHub Actions
    |
    +--> Backend validation
    |
    +--> Backend pytest suite
    |
    +--> Frontend automated tests
    |
    +--> React production build
    |
    +--> Backend Docker image build
    |
    +--> Frontend Docker image build
    |
    v
All Required Checks Pass
    |
    v
Automated Deployment
    |
    +--> Vercel
    |
    +--> Render
```

Implementation order:

1. Complete Phase 3 by establishing reliable backend and frontend automated testing.
2. Add Docker builds to the existing CI workflow in Phase 4.
3. Introduce automated deployment in Phase 5.
4. Strengthen production security, configuration, reliability and monitoring in the subsequent phases.

The future pipeline should reuse the existing workflow where practical. Docker builds and deployment should be added incrementally rather than introducing an entirely separate pipeline without a clear need.

Automated deployment must occur only after the required validation steps have succeeded.
