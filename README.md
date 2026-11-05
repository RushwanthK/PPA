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
* Redis (`redis-py`) — optional cache for dashboard aggregates

## Database

* PostgreSQL `pg_trgm` extension — trigram indexes for bank transaction description/category substring search

## Authentication

* JWT Authentication

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

# Current Testing Status

## Phase 3 — Automated Testing

Backend automated testing is well established. The remaining work is to complete the transaction-specific coverage review, establish meaningful frontend tests, and verify that both test suites are enforced consistently through CI.

### Backend Testing

Test modules cover the following areas:

- Authentication, registration, login, and user APIs
- Banks
- Savings
- Assets
- Transaction exports and backup
- Credit Cards
- Dashboard
- Database isolation and transaction-related behavior

The bank test module has been expanded to cover the new transaction-history API behavior, including cursor pagination, filter scope, legacy page-number compatibility, query-count behavior, text search, amount boundaries, IST date boundaries, invalid filters and authorization. `tests/test_dashboard_cache.py` adds focused tests for cache hits, generation invalidation/user isolation, Redis failure fallback and invalidation after a bank transaction.

**Last recorded full backend regression result:** `411 passed, 5 warnings`.

This result comes from the existing project notes and has not been independently re-run against the reviewed branch. The presence of new test cases in the branch does not establish that those tests have passed. Re-run the focused suites and the complete test suite before recording a new result.

### GitHub Actions CI

The workflow in `.github/workflows/ci.yml` currently:

- Runs for pushes to `main` and pull requests targeting `main`.
- Starts a PostgreSQL 17 service for backend testing.
- Uses Python 3.12 and installs backend dependencies.
- Performs Python validation.
- Runs the backend test suite using `pytest -q`.
- Uses Node.js 22 and installs frontend dependencies using `npm ci`.
- Validates the React production build using `npm run build`.

Backend pytest execution is already configured in CI.

The workflow does not yet run frontend automated tests or build Docker images. A successful recent GitHub Actions run and repository branch-protection settings still need to be verified. The reviewed performance branch is not evidence of a green CI run merely because the workflow definition exists.

### Frontend Testing

The frontend has an `npm test` script and a React Testing Library dependency, but meaningful PPA frontend testing has not yet been established.

The existing `src/App.test.js` is still the Create React App starter test. In addition, `src/setupTests.js` imports `@testing-library/jest-dom`, but that package is not declared in the frontend `package.json` or its lockfile.

The test setup must be corrected before the frontend test suite can be relied upon.

Planned frontend coverage includes:

- Component rendering and routing
- Form validation
- API interactions and error feedback
- Transaction workflows
- Deletion confirmation
- Backup and export flows

### Immediate Next Steps

1. Resolve the frontend test setup and replace the starter test.
2. Add meaningful frontend regression tests.
3. Add frontend test execution to GitHub Actions while retaining the production build check.
4. Verify the complete pipeline and update the status after successful execution.

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
│   └── utils/           # Shared utilities, including dashboard_cache.py
├── portfolio-app/       # React frontend
├── migrations/          # Alembic migrations, including pg_trgm search indexes
├── tests/               # Backend automated tests
├── .github/workflows/   # GitHub Actions CI
├── requirements.txt
├── run.py
├── config.py
├── README.md
├── ARCHITECTURE.md
└── .env
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

Backend tests

```bash
pytest -v
```

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

## Phase 3 — Automated Testing (Current Phase)

- [x] Backend test modules established for the major application areas
- [x] Backend pytest step configured in CI
- [ ] Complete conservative backend cleanup where justified
- [ ] Resolve the frontend test setup and dependency issue
- [ ] Replace the default frontend starter test with meaningful PPA tests
- [ ] Add component, form, API interaction, transaction and error-feedback tests
- [ ] Add frontend test execution to GitHub Actions
- [ ] Verify consistent backend and frontend test execution
- [ ] Verify the latest successful CI run and the required-check settings for pull requests

The branch includes additional bank transaction and dashboard-cache test cases, but Phase 3 remains in progress until the branch's focused and full test suites have actually been run and the frontend test foundation is established.

Phase 3 is complete when backend and frontend test suites run consistently, meaningful coverage is established, and CI validates both suites alongside the React production build.

## Phase 3B — RAG and AI Integration (Planned)

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

- [ ] Evaluate rate limiting and API versioning
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
