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
   PostgreSQL Database    Optional Redis Cache
                          (dashboard aggregates)
```

PostgreSQL remains the source of truth. Redis is an optional cache layer used only when `REDIS_URL` is configured and reachable.

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
  Supabase PostgreSQL   Optional Redis
  (source of truth)     (dashboard cache)
```

The reviewed source supports an optional Redis connection through `REDIS_URL`; it does not establish which Redis provider is used or prove that a production Redis instance is connected. A missing or unavailable Redis service is handled by falling back to PostgreSQL for dashboard calculations.

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
    ├── JWT Authentication
    ├── SQLAlchemy
    ├── Flask-Migrate
    ├── CORS
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
    └── dashboard_cache.py

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
```

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

Redis is an optional cache-aside layer for three dashboard resources:

- Dashboard summary
- Spending for a supported range (`30d`, `3m`, `6m`, `1y`, `all`)
- Asset allocation

PostgreSQL remains authoritative. Cache configuration is supplied through environment variables:

| Variable | Default / behavior |
|---|---|
| `REDIS_URL` | Not set by default; enables Redis when supplied |
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

The current `docker-compose.yml` does not define a Redis service and does not pass `REDIS_URL` into the backend container. The present Compose configuration therefore does not enable the Redis cache. A local Docker Redis setup would require an explicit service and environment wiring; do not assume it is already part of the stack.

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

# Planned RAG / AI Extension — Phase 3B

**Status: Planned; not implemented in the reviewed repository.**

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
            +--> npm run build
```

The current workflow executes backend tests and validates the React production build.

The following work is still outstanding:

- Frontend automated test execution
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
