# Personal Portfolio Application (PPA)

## Overview

Personal Portfolio Application (PPA) is a full-stack web application developed to manage and monitor personal financial information from a single dashboard.

The application allows tracking of:

* Credit Cards
* Assets
* Investments
* Savings
* Bank Accounts
* Financial Dashboard & Analytics

Although initially developed as a personal finance application, the project is primarily intended to demonstrate Full Stack Engineering skills including backend development, frontend development, database design, REST API development, authentication, deployment, testing, and DevOps practices.

---

# Objectives

* Build a production-style full stack application
* Learn industry-standard software architecture
* Gain practical experience with backend and frontend integration
* Learn Docker, CI/CD and cloud deployment
* Learn automated testing and regression testing
* Prepare for Full Stack Software Engineer interviews

---

# Tech Stack

## Frontend

* React.js
* JavaScript
* CSS

## Backend

* Flask
* SQLAlchemy
* Flask-Migrate
* Flask-JWT-Extended
* Flask-CORS
* Flask-Limiter — rate limiting for login, registration and password change
* Redis (`redis-py`) — optional cache for dashboard aggregates and storage for rate-limit counters

## Database

* PostgreSQL `pg_trgm` extension — trigram indexes for bank transaction description/category substring search

## Authentication and API Security

* JWT access tokens (Flask-JWT-Extended) sent in the `Authorization` header
* Server-side logout, "log out of all devices" and logout on password change (token version + revocation list in PostgreSQL)
* Rate limiting on login, registration and password change
* Request size limit, generic 500 replies, CORS without credentials, API security headers

## Testing

* Backend: pytest against a dedicated PostgreSQL test database
* Frontend: Jest + React Testing Library (`react-scripts test`)

## Version Control

* Git
* GitHub

## CI

* GitHub Actions

## Deployment

* Frontend: Vercel
* Backend: Render
* Database: Supabase PostgreSQL
* Redis: Render Redis service alongside the backend, configured through `REDIS_URL`

---

# Current Status — Phase 3: Testing and Auth/API Security

Phase 3 covers backend regression (3A), targeted auth/API security (3B), frontend tests (3C), and CI plus documentation (3D). **Phase 3 is complete.** All four parts are committed and **deployed to production** (November 23, 2026). Production deploys from the `perf/add-request-diagnostics` branch. See `PROJECT_STATUS.md` for the full checklist and the deployment order.

### Local Verification (November 23, 2026)

| Check | Result |
|---|---|
| Backend `pytest` | `465 passed, 5 warnings` (known `datetime.utcnow()` deprecations) |
| Frontend `npm test -- --watchAll=false` | `201 passed`, 14 suites |
| `CI=true npm run build` | Compiled successfully |
| `pip-audit` | No known vulnerabilities |

These are local results. The migration is applied on Supabase and the new frontend and backend are live; production checks are listed in `PROJECT_STATUS.md`.

### Backend Testing

Test modules cover:

- Authentication, registration, login and user APIs
- Banks (cursor pagination, filters, query counts, IST date and amount boundaries)
- Savings, assets, credit cards and transaction exports/backup
- Dashboard and the dashboard Redis cache
- Rate limiting (`test_rate_limiting.py`)
- Token lifecycle: logout, logout-all, password change, revoked/expired/invalid tokens (`test_token_lifecycle.py`)
- API hardening: every non-public route requires a token, 413 size limit, no exception text in 500 replies, CORS and security headers (`test_api_hardening.py`)

The regression found one real defect. Credit-card billing did not return `transactions_billed` and `total_amount_billed`, which the billing-details panel displays. The backend now returns both.

### Frontend Testing

Jest and React Testing Library tests cover the Login, Dashboard, Banks, Savings, Assets and Credit Cards pages, shared components (Modal, DataTable, delete confirmation, transaction table, Profile dialog), and the API service layer. The tests found an accessibility bug: every open modal shared the same title id. Each modal now gets a unique id.

### GitHub Actions CI

The workflow in `.github/workflows/ci.yml`:

- Runs for pushes and pull requests on `main` and on the production branch `perf/add-request-diagnostics`, and manually via "Run workflow" (`workflow_dispatch`).
- Starts a PostgreSQL 17 service and uses a CI-only JWT key.
- Uses Python 3.12, installs dependencies, compiles the backend and runs `pytest -q`.
- Uses Node.js 22, runs `npm ci`, runs the frontend tests and then `npm run build`.

Vercel deploys on push at the same time as CI runs, so CI does not block the frontend deploy. It does tell you whether the backend is safe to deploy manually on Render: only deploy after a green run.

### Security Summary

- **Rate limits:** `/login` per IP (`10/min`, `50/hour`) and per account (5 failed attempts per 15 minutes), `/register` (3 per hour per IP), wrong current passwords (5 per 15 minutes). Counters are stored in Redis with a TTL; if Redis is unavailable, the limits fall back to per-process memory.
- **Logout:** logout revokes the current token on the server, "Log out of all devices" invalidates every token, and a password change requires the current password and ends other sessions. All of this state lives in PostgreSQL.
- **Uniform 401:** every token problem returns 401 with `{"error": ...}`, so the frontend always logs out cleanly.
- **Request hardening:** requests over 256 KB get a JSON 413, 500 replies never include exception text, CORS no longer advertises credentials, and API responses carry CSP, frame, referrer and HSTS headers.
- **Dependencies:** Python dependencies were upgraded until `pip-audit` reported no known vulnerabilities. The remaining `npm audit` advisories are only in Create React App build tooling.
- **Not done yet:** refresh tokens, moving the token out of `localStorage`, a frontend CSP on Vercel, and migrating off CRA.

### Production Configuration Done in Phase 3

- New 32+ byte `JWT_SECRET_KEY` on Render.
- Migration `0557b33bd281` applied on Supabase before the backend deploy.
- `TRUSTED_PROXY_COUNT=3`, measured from Render's real `X-Forwarded-For` chain (client, Cloudflare, Render load balancer).
- CI runs on the production branch; deploy the backend on Render only after a green run.

Next: the RAG and AI Integration phase. Deferred security items are listed under Phase 6.

# Current Features

## Dashboard

* Financial overview
* Summary cards
* Net worth calculations
* Spending analysis
* Asset allocation
* Optional Redis cache-aside for summary, spending-by-range and asset-allocation responses
* User-scoped cache keys with generation-token invalidation and configurable TTL
* Cache diagnostics through the `X-Dashboard-Cache` response header (`HIT`, `MISS` or `BYPASS`)

The production Render backend uses the Render Redis service through `REDIS_URL`. Redis remains optional in local/CI environments; when it is not configured or is unavailable, dashboard calculations fall back to PostgreSQL. The cache is an optimization layer, not the source of truth. If invalidation fails after a database commit, an older cached result may remain available until its TTL expires. Check `X-Dashboard-Cache` (`HIT`, `MISS` or `BYPASS`) on dashboard responses to confirm which path handled a request.

## Credit Cards

* Add/Edit/Delete credit cards
* Credit limits
* Available balance
* Used amount
* Transactions
* Billing behavior

## Assets

* Track different asset categories
* Deposit
* Withdraw
* Transaction history

## Investments

* Investment tracking
* Investment categories
* Current values

## Savings

* Savings categories
* Bank-wise savings
* Total savings calculations

## Banks

* Multiple bank accounts
* Bank balances
* Linked assets and savings
* Server-side transaction history with cursor/keyset pagination by default
* Legacy page-number pagination retained temporarily for compatibility
* Server-side description/category substring search
* Structured filters for transaction type, IST calendar dates and amount ranges
* Bounded page size (1–100; default 25)
* PostgreSQL trigram indexes for description/category substring search

### Bank Transaction Pagination and Filtering

The normal API path uses keyset pagination ordered by `date DESC, id DESC`. It fetches one extra row (`page_size + 1`) to determine `has_more`, avoiding an exact `COUNT(*)` query on each cursor-based page. The older page-number request remains supported as a compatibility path and continues to use `COUNT(*)` and offset pagination.

Search is deliberately limited to `description` and `category`. Transaction type, date and amount are handled by dedicated filters. Date selections represent IST calendar days; the backend converts local-midnight boundaries to naive UTC and applies a half-open interval (`date >= start`, `date < day-after-end`) so the selected end date is inclusive without relying on a fabricated end-of-day timestamp.

Amount ranges use non-overlapping lower-inclusive/upper-exclusive boundaries: `<500`, `500–<1,000`, `1,000–<5,000`, `5,000–<10,000` and `10,000+`.

### Bank Transaction Search Indexes

Migration `7bc2e41d5a90` enables `pg_trgm` and creates partial GIN trigram indexes on bank transaction descriptions and categories. These indexes are intended to support the endpoint's case-insensitive substring predicates. Their presence does not prove that PostgreSQL selects them; verify index usage with representative data and `EXPLAIN (ANALYZE, BUFFERS)`.

## Performance Diagnostics

The backend supports opt-in request and SQL execution timing through `PPA_PERF_DIAGNOSTICS`. It is disabled by default. When enabled, responses include an `X-Request-ID` and the backend logs request duration, time to first SQL execution, SQL execution count and accumulated DBAPI cursor-execution time. The instrumentation avoids logging SQL statements, parameters, request bodies, query strings, user identifiers and financial values.

The SQL timing metric does not include all result fetching, ORM processing, response serialization, browser rendering or network time. Use it with browser timing and database query plans rather than treating it as complete end-to-end latency.

---

# Project Structure

```text
PPA
│
├── app/                 # Flask backend
│   ├── banks/           # Bank APIs, including transaction filters and cursor pagination
│   ├── dashboard/       # Dashboard API and aggregation services
│   └── utils/           # Shared utilities: dashboard_cache, auth_tokens, rate_limit, errors
├── portfolio-app/       # React frontend
├── migrations/          # Alembic migrations (pg_trgm search indexes, token revocation)
├── tests/               # Backend automated tests
├── .github/workflows/   # GitHub Actions CI
├── requirements.txt
├── run.py
├── config.py
├── README.md
├── ARCHITECTURE.md
├── PROJECT_STATUS.md
├── LEARNING_NOTES.md
└── .env                 # local only, never committed
```

---

# Local Development

Backend

```bash
python run.py
```

Frontend

```bash
npm start
```

Backend tests (local PostgreSQL test database from `.env.test`)

```bash
pytest -q
```

Frontend tests (from `portfolio-app/`)

```bash
npm test -- --watchAll=false
```

Database migrations

```bash
flask db upgrade
```

Python dependencies are installed into the project's existing `venv`. `JWT_SECRET_KEY` should be at least 32 random bytes; the backend logs a warning at startup if it is shorter.

Optional performance diagnostics can be enabled in the backend environment with:

```text
PPA_PERF_DIAGNOSTICS=true
```

Dashboard caching uses the Render Redis service in production through `REDIS_URL`. The reviewed `docker-compose.yml` does not pass `REDIS_URL` to the backend container or define a Redis service, so the local Docker Compose stack bypasses Redis. Testing configuration explicitly disables the external Redis dependency.

---

# Roadmap

## Phases 0–2 — Application, Git and CI Foundations

- [x] Full-stack application foundation
- [x] Vercel frontend deployment — completed per project history
- [x] Render backend deployment — completed per project history
- [x] Supabase PostgreSQL integration — completed per project history
- [x] Backend and frontend Dockerization
- [x] PostgreSQL container, volumes, networking and Docker Compose
- [x] Git/GitHub workflow and repository safety practices
- [x] GitHub Actions CI foundation
- [x] Backend pytest execution configured in GitHub Actions
- [x] Frontend dependency installation and production build validation in CI

## Phase 3 — Automated Testing and Auth/API Security ✅ Complete

- [x] 3A: Full backend regression; credit-card billing summary defect fixed
- [x] 3B: Rate limiting on login, registration and password change
- [x] 3B: Server-side logout, logout of all devices, password change ends other sessions
- [x] 3B: Request size limit, generic 500 replies, route-coverage test, CORS without credentials, security headers
- [x] 3B: Dependency upgrades (`pip-audit` clean)
- [x] 3C: Frontend test setup fixed and meaningful tests for pages, components and services
- [x] 3D: Frontend tests added to GitHub Actions; documentation updated
- [x] Commit and push (`306bdb8`)
- [x] Apply the migration to Supabase, configure Render, deploy and verify in production
- [x] CI triggers include the production branch
- [x] Green CI run on the production branch (465 backend + 201 frontend tests, build)
- [x] `TRUSTED_PROXY_COUNT` set to 3 from the measured proxy chain

Phase 3 was completed on November 23, 2026. Refresh tokens and a frontend CSP are deliberately deferred to later security work.

## RAG and AI Integration (Planned, after Phase 3)

This phase will follow Phase 3 and precede Phase 4.

- [ ] Build a separate project-document learning chatbot
- [ ] Learn document ingestion, extraction, chunking and metadata
- [ ] Evaluate embeddings and PostgreSQL `pgvector`
- [ ] Implement semantic retrieval and PostgreSQL full-text search
- [ ] Build the initial PPA Knowledge Copilot using approved documentation and trusted financial-education material
- [ ] Generate grounded answers with source references and insufficient-evidence handling
- [ ] Integrate the initial copilot with React and Flask
- [ ] Add automated RAG tests and a repeatable evaluation dataset
- [ ] Add appropriate model credential, usage and cost controls
- [ ] Document the architecture and prepare for subsequent CI and deployment work

Personalized financial analysis using private user transactions must wait until the required security and authorization controls in Phase 6 are implemented.

## Phase 4 — Docker Integrated into CI

- [ ] Build the backend Docker image in GitHub Actions
- [ ] Build the frontend Docker image in GitHub Actions
- [ ] Verify both image builds succeed
- [ ] Keep AI dependencies and database extensions compatible with the Docker environment

## Phase 5 — Continuous Deployment

- [ ] Automate Render deployment after successful validation
- [ ] Manage deployment credentials securely
- [ ] Handle deployment failures
- [ ] Establish an appropriate rollback strategy

## Phase 6 — Production Configuration and Security

- [ ] Establish clear Local, Docker, CI and Production configuration boundaries
- [ ] Review secrets and environment-variable management
- [x] Initial API security hardening (done in Phase 3B)
- [ ] Refresh tokens and safer token storage
- [ ] Frontend CSP / security headers on Vercel
- [ ] Migrate off Create React App build tooling (its remaining `npm audit` advisories)
- [ ] Harden production configuration and access controls
- [ ] Protect AI endpoints with appropriate authentication, authorization and rate limits
- [ ] Enforce user-level data isolation for any future financial-analysis tools
- [ ] Evaluate prompt-injection and sensitive-data-disclosure risks

## Phase 7 — Production Reliability

- [ ] Implement a health endpoint
- [ ] Add deployment health checks
- [ ] Establish a migration-aware deployment process
- [ ] Understand and document rollback behavior
- [ ] Ensure ordinary financial features remain available if AI services fail

## Phase 8 — Logging and Monitoring

- [ ] Improve application and API error logging
- [ ] Improve database and deployment error visibility
- [ ] Introduce appropriate health monitoring and alerts
- [ ] Monitor AI latency, failures and usage if the copilot is deployed
- [ ] Prevent sensitive data from leaking into logs

## Phase 9 — System Design and Scalability

- [ ] Document architecture and important technology trade-offs
- [ ] Analyze performance bottlenecks using request diagnostics, browser timing and database query plans
- [x] Implement optional Redis cache-aside for dashboard aggregates with TTL and per-user generation-token invalidation
- [x] Add opt-in request/SQL execution diagnostics without logging sensitive request or SQL data
- [ ] Verify cache invalidation across all dashboard-affecting write paths, including Redis outage/invalidation-failure behavior
- [ ] Verify the new trigram indexes and transaction ordering indexes using representative data and `EXPLAIN (ANALYZE, BUFFERS)`
- [ ] Compare local/development and production measurements under comparable workloads
- [ ] Evaluate background jobs against actual workload requirements
- [ ] Document RAG retrieval, financial calculation and LLM-generation boundaries
- [ ] Evaluate scalability and concurrent workloads

## Phase 10 — Advanced / Optional Engineering

- [x] Rate limiting for authentication endpoints (Phase 3B)
- [ ] Evaluate API versioning
- [x] Redis — initial optional integration for dashboard caching; broader adoption remains conditional on need
- [ ] Background jobs
- [x] Caching — cache-aside implementation for dashboard summary, spending and asset-allocation responses
- [ ] Explore performance and load testing
- [ ] Consider Infrastructure as Code
- [ ] Explore additional technologies only when they address an identified engineering need

The primary objective is to build a reliable application and develop the ability to explain the engineering decisions behind it, rather than adding technologies simply for complexity.

# Learning Goal

This repository serves both as a working application and as a structured learning project for mastering modern Full Stack Development and DevOps practices.

The intended progression is:

```text
Develop
  ↓
Git / GitHub
  ↓
CI
  ↓
Automated testing
  ↓
Docker in CI
  ↓
CD / deployment
  ↓
Production security
  ↓
Reliability
  ↓
Monitoring
  ↓
System design / scaling
```

The project should remain focused. Additional technologies should only be introduced when they solve a real engineering problem.

---

# Configuration Model

```text
                    PPA
                     │
          ┌──────────┼──────────┐
          │          │          │
          ▼          ▼          ▼
       LOCAL       DOCKER    PRODUCTION
       DEV          DEV
          │          │          │
          ▼          ▼          ▼
       .env       .env.docker  Render/Vercel
          │          │          │
          ▼          ▼          ▼
    Local PG    Docker PG    Supabase PG
```
