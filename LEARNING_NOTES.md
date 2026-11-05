# Docker Fundamentals

## Image
Blueprint used to create containers.

## Container
Running instance of an image.

## Dockerfile
Instruction file used to build an image.
Concept: A Dockerfile is Infrastructure as Code.

## FROM
Base image.

## WORKDIR
Working directory inside the container.

## COPY
Copies files from local machine to image.

## RUN
Executes commands during image build.

## CMD
Default command executed when the container starts.

## EXPOSE
Documents the port the application listens on. It does not publish the port.


# Sprint 2 - Running Containers

## Concepts Learned

* Difference between a Docker Image and a Docker Container.
* A single Docker Image can create multiple independent containers.
* `docker run` creates and starts a new container from an image.
* `--name` assigns a readable name to a container.
* `-p HOST_PORT:CONTAINER_PORT` maps a host port to a container port.
* `EXPOSE` only documents the application's listening port; it does not publish the port.
* Applications inside Docker should listen on `0.0.0.0`, not `127.0.0.1`, to allow external access through Docker networking.

## Problem Encountered

* Flask application crashed immediately after the container started.

## Root Cause

* Docker successfully created and started the container.
* The Flask application failed because the `DATABASE_URL` environment variable was not available inside the container.

## Important Takeaway

* Docker and the application are separate responsibilities.
* A container can fail because of the application, not because Docker is broken.
* Always diagnose the problem before modifying code or configuration.


# Sprint 3 - Container Lifecycle & Debugging

## Concepts Learned

* A Docker Image is different from a Docker Container.
* A container has a lifecycle: Created → Running → Exited → Removed.
* `docker run` creates a new container from an image.
* `docker start` starts an existing stopped container.
* `docker stop` stops a running container.
* `docker rm` permanently removes a container but does not delete the image.
* `docker ps` shows only running containers.
* `docker ps -a` shows all containers including exited ones.
* `docker logs` displays the application's stdout and stderr output from inside the container.
* `docker inspect` provides detailed metadata about the container.

## Problem Encountered

* Flask container exited immediately after startup.

## Root Cause

* Docker successfully created and started the container.
* The Flask application failed because the required `DATABASE_URL` environment variable was not available.

## Debugging Workflow

1. Check running containers using `docker ps`.
2. Check all containers using `docker ps -a`.
3. Read application logs using `docker logs`.
4. Inspect container configuration using `docker inspect`.
5. Identify whether the problem belongs to Docker or the application.

## Important Takeaway

* Docker's responsibility ends after starting the container.
* If the application crashes, investigate the application before changing Docker.
* Always debug methodically instead of making random changes.


# Sprint 4 - Application Configuration & Environment Variables

## Concepts Learned

- Application code should not decide which environment it is running in.
- Configuration should be supplied from outside the application.
- Docker images should never contain secrets such as database credentials or API keys.
- The same Docker image can be reused across Development, Testing and Production by supplying different environment variables.
- Docker reads environment variables at runtime, not during image creation.

## Refactoring Performed

Before:

- Application decided between LOCAL_DATABASE_URL and DATABASE_URL based on FLASK_ENV.

After:

- Application only reads DATABASE_URL.
- Each deployment environment is responsible for supplying the correct DATABASE_URL.

## Architecture Improvement

Application

↓

DATABASE_URL

↓

Environment supplies the correct value

- Local Python → localhost
- Docker → host.docker.internal
- Render → Supabase

## Important Takeaway

Build once.
Configure everywhere.

Deployment should decide configuration.
Application should remain environment agnostic.

# Sprint 5 - Running Flask in Docker

## Concepts Learned

- Environment variables are supplied when a container starts, not when an image is built.
- The same Docker image can run in different environments by providing different environment variables.
- `.env.docker` allows Docker-specific configuration while keeping the normal `.env` unchanged.
- `host.docker.internal` allows a Docker container on Windows/macOS to connect to services running on the host machine.
- Docker images are immutable snapshots. After changing application code, a new image must be built.

## Architecture Improvements

- The application now depends only on `DATABASE_URL`.
- Deployment environments are responsible for supplying the correct value.
- The application no longer contains database-selection logic.

## Improvements Made

- Added `portfolio-app/` to `.dockerignore`.
- Reduced backend Docker image from approximately 1.17 GB to 254 MB.

## Important Takeaways

- Build once, configure everywhere.
- Rebuild the image whenever application code changes.
- A Docker image is a snapshot of the application at build time.


# Sprint 6 - Docker Networking

## Concepts Learned

- Every Docker container belongs to a network.
- By default Docker places containers into the bridge network.
- Every container receives its own private IP address.
- Containers should communicate using container names instead of IP addresses.
- Docker provides built-in DNS for container name resolution.
- Environment variables are injected into containers during startup.
- Port mapping allows applications inside Docker to be accessed from the host machine.

## Networking Observations

- Flask container joined the default bridge network.
- Docker assigned a private IP address to the container.
- Docker exposed Flask through port 5000.
- Docker successfully injected DATABASE_URL and JWT_SECRET_KEY into the running container.

## Important Takeaways

- Containers should never rely on changing IP addresses.
- Docker networking becomes much simpler when using service/container names.
- Docker Compose automatically creates networks and DNS for services.

# Sprint 7 - Docker Architecture Preparation

## Concepts Learned

- Flask-Migrate is preferred over `db.create_all()` for managing database schema changes.
- `load_dotenv()` is useful for local Python execution but is effectively bypassed when Docker injects environment variables at runtime.
- Docker Compose orchestrates multiple containers; it does not replace Dockerfiles.
- A portable development environment should containerize both the application and its database.
- Docker Compose provides automatic DNS, allowing services to communicate using service names instead of IP addresses.

## Architectural Decisions

- Continue using Flask-Migrate.
- Keep `load_dotenv()` to support non-Docker local development.
- Plan to replace `host.docker.internal` with a PostgreSQL service name (`postgres`) once Docker Compose is introduced.

## Important Takeaway

Docker Compose is an orchestration tool that brings together containers, networking, environment variables, and volumes into a reproducible development environment.

# Sprint 8 - PostgreSQL Container

## Concepts Learned

- Docker images can contain complete services such as PostgreSQL.
- PostgreSQL can be configured during first startup using environment variables.
- Docker volumes persist PostgreSQL data outside the container.
- PostgreSQL initialization happens only once when the volume is empty.
- Containers can expose internal ports to the host machine using port mapping.

## PostgreSQL Container Configuration

Container:
ppa-postgres-container

Database:
portfoliodocker

Username:
postgresdocker

Password:
[DO NOT STORE REAL PASSWORDS IN PROJECT NOTES]

Host:
localhost

Port:
5433

Volume:
ppa-postgres-data

## Important Takeaways

- PostgreSQL server can run entirely inside Docker.
- Database files are stored inside the Docker volume, not inside the container.
- Deleting the container does not automatically delete the volume.
- Local PostgreSQL and Docker PostgreSQL can run simultaneously on different ports.

# Sprint 8.1 - Docker Volumes & PostgreSQL Persistence

## Concepts Learned

- Containers are ephemeral and expected to be disposable.
- Docker Volumes provide persistent storage independent of containers.
- PostgreSQL stores its database files inside a Docker Volume.
- Deleting a PostgreSQL container does not delete the volume.
- A recreated PostgreSQL container can reuse an existing volume and immediately regain access to existing data.

## Experiment Performed

Created:

- docker_test table

Inserted:

- Rushwanth Docker Test

Verified:

- Data existed

Deleted:

- PostgreSQL container

Recreated:

- PostgreSQL container

Verified:

- Data still existed

## Important Takeaway

Container != Data

Container can be deleted.

Volume persists.

Database survives.

# Sprint 9 - Docker Compose

## Concepts Learned

Docker Compose allows multiple containers to be managed using a single YAML configuration file.

Instead of running multiple docker run commands manually, the entire stack can be started using:

docker compose up

## Components Managed

- Flask Backend
- PostgreSQL Database
- Docker Network
- Docker Volume

## Important Concepts

### Service Discovery

Containers communicate using service names.

Example:

DATABASE_URL=postgresql://postgresdocker:password@postgres:5432/portfoliodocker

Here "postgres" is the Docker Compose service name.

### depends_on

depends_on only controls startup order.

It does not guarantee the database is ready to accept connections.

### External Volumes

Compose can reuse an existing volume using:

external: true

This allowed reuse of:

ppa-postgres-data

without creating a new database.

## Verification Performed

- Started backend and postgres using Compose
- Verified backend started successfully
- Verified PostgreSQL started successfully
- Verified existing docker_test table still existed
- Verified volume reuse


# Sprint 10 - React Dockerization

## Current React Setup

Development Environment:
REACT_APP_API_URL=http://localhost:5000

Production Environment:
REACT_APP_API_URL=https://rs-ppa-backend.onrender.com

Axios uses environment variables for API communication.

## Important Takeaway

Environment-specific configuration was already implemented before Dockerization, making React containerization easier and cleaner.



# Sprint 11 - Backend Automated Testing

## Current Goal

Phase 3 is focused on automated testing of the backend before frontend automated testing is introduced.

The testing approach is not simply to make endpoints return `200` or `201`. The goal is to verify meaningful application behavior.

## Testing Standard

For each backend module, test:

* Model / constraints where behavior is exposed
* Active routes
* Successful operations
* Validation and error responses
* Authentication
* Authorization / ownership
* Missing resources
* Business rules
* Database side effects
* API feedback
* Regression behavior

A passing test should provide evidence that the application does the right thing, not merely that a line of code was executed.

## Modules Tested So Far

* Authentication / Users
* Banks
* Savings
* Assets
* Transaction exports / backup
* Credit Cards
* Dashboard

## Credit Card Testing

The credit-card page is a financially sensitive backend module.

The test suite covers:

* Credit-card CRUD
* Authorization and ownership isolation
* Input validation
* Transaction creation and history
* Expense rules
* Payment rules
* Credit-limit rules
* Billing rules
* Balance calculations
* Deletion restrictions
* Database side effects
* API success and error feedback
* Regression behavior

Focused result:

`79 passed`

### Credit Card Testing Lesson

Do not change production datetime behavior simply to make a test pass.

The application's credit-card transaction timestamp behavior differs between local and deployed environments. Tests therefore need to be designed around the intended business behavior without rewriting the timestamp conversion/order logic unless a genuine application defect is identified.

A particularly important lesson was to distinguish between:

```text
Test setup problem
        vs
Production behavior problem
```

A failing test does not automatically mean the route is broken.

## Dashboard Testing

The Dashboard is primarily a read/aggregation module.

The test suite covers:

* Summary endpoint
* Spending endpoint
* Asset-allocation endpoint
* Authentication
* Empty states
* Financial aggregation
* Date-range filtering
* Invalid range feedback
* Expense-only spending calculations
* Bank + credit-card spending aggregation
* Category normalization
* Top-12 spending categories
* Asset grouping and sorting
* Cross-user isolation

Focused result:

`22 passed`

### Dashboard Testing Lesson

When an API sorts only by a value, equal values may legitimately have an unspecified relative order.

Tests should not accidentally require an ordering rule that the application never promised.

A better test dataset can also make the business rule unambiguous. For example:

```text
FD           15,000
Stocks       11,000
Mutual Funds 10,000
```

clearly exercises descending sorting without relying on tie ordering.

## Full Backend Regression

After adding Credit Card and Dashboard tests:

`389 passed, 5 warnings`

The warning count is currently left alone because the existing datetime deprecation warning is related to timestamp behavior that is considered sensitive. The objective of the current testing phase is behavioral coverage, not unrelated timestamp refactoring.

## Testing Workflow Learned

The preferred workflow is:

```text
Inspect implementation
        ↓
Understand current behavior
        ↓
Write focused tests
        ↓
Run module-specific tests
        ↓
Determine whether failures are test or production issues
        ↓
Fix tests when the expectation/setup is wrong
        ↓
Only change production code for genuine defects
        ↓
Run full regression suite
```

# Sprint 12 - Backend Performance and Transaction History Optimization

This sprint records the engineering concepts introduced in the current performance branch. The code is present in the reviewed branch, but runtime measurements, migration execution and the new tests still need to be verified in the target environments.

## Request-Level and SQL Performance Diagnostics

The Flask application factory supports opt-in diagnostics through:

```text
PPA_PERF_DIAGNOSTICS=true
```

The setting is disabled by default. When enabled, the application creates a request ID and records:

- HTTP method, Flask endpoint and response status
- Total Flask request elapsed time (`app_ms`)
- Time from request start until the first SQL cursor execution begins (`first_sql_start_ms`)
- SQL cursor execution count (`sql_count`)
- Accumulated DBAPI cursor execution time (`sql_execute_ms`)

The request ID is also exposed in the `X-Request-ID` response header so a browser request can be correlated with the server log.

### Important measurement boundaries

`sql_execute_ms` measures DBAPI cursor execution. It does not include all result fetching, SQLAlchemy object processing, JSON serialization, frontend rendering or browser-to-server network latency. It is therefore not equivalent to total database time or end-to-end request latency.

A useful performance investigation separates the request into layers:

```text
Browser / network time
        ↓
Flask request processing
        ↓
SQL execution
        ↓
Result fetching and ORM processing
        ↓
Serialization and response transfer
        ↓
Frontend rendering
```

Do not conclude that a request is database-bound from one timing value. Compare request elapsed time, SQL count, SQL execution time, query plans and browser timings. Keep local/development and production measurements separate unless the workloads and network conditions are comparable.

### Logging safety

The implementation intentionally avoids logging SQL text, SQL parameters, query strings, request bodies, user IDs and financial values. Diagnostics should remain opt-in and should not become a channel for exposing personal financial data.

SQLAlchemy event listeners are attached during app creation only when the setting is enabled. Changing the environment variable therefore requires an application restart/recreation.

## Bank Transaction API — Search and Structured Filters

The bank transaction endpoint now retrieves filtered data on the server. Its free-text search contract is limited to:

- Transaction description
- Transaction category

Other fields have dedicated behavior:

- `type`: `income` or `expense`
- `start_date`: inclusive start of the selected IST calendar date
- `end_date`: inclusive end of the selected IST calendar date
- `amount_range`: one of the five supported amount bands
- `page_size`: requested result count, clamped to 1–100 (default 25)

Text search intentionally does not include amount, date, balance-after or transaction type. This keeps the free-text contract explicit and allows the other dimensions to use typed filters.

### Amount range boundaries

The ranges use half-open intervals to avoid overlap:

- `under_500`: amount `>= 0` and `< 500`
- `500_1000`: amount `>= 500` and `< 1,000`
- `1000_5000`: amount `>= 1,000` and `< 5,000`
- `5000_10000`: amount `>= 5,000` and `< 10,000`
- `10000_plus`: amount `>= 10,000`

A transaction worth exactly ₹500 belongs to the ₹500–less-than-₹1,000 range; exactly ₹1,000 belongs to the next range. Half-open intervals remove ambiguity at boundaries.

### IST calendar filtering over naive UTC timestamps

The application's stored transaction timestamps follow a naive-UTC convention. The user selects calendar dates in IST. The backend converts IST midnight to naive UTC and filters using a half-open interval:

```text
start_utc = IST midnight on start_date converted to UTC
end_utc_exclusive = IST midnight on (end_date + 1 day) converted to UTC

WHERE transaction.date >= start_utc
  AND transaction.date < end_utc_exclusive
```

This makes the user's end date inclusive without constructing an artificial last instant such as `23:59:59.999999`. For IST, midnight corresponds to 18:30 on the previous UTC date. The filter leaves the database timestamp column unwrapped, preserving the opportunity to use a normal index on that column.

Keep the timezone convention consistent. Do not mix timezone-aware and naive timestamps casually, especially around credit-card transaction behavior, which the existing project notes identify as sensitive.

## PostgreSQL Trigram Search Indexes

Migration `7bc2e41d5a90` enables the `pg_trgm` extension if needed and adds two partial GIN indexes:

- `ix_transaction_bank_description_trgm` on `description` using `gin_trgm_ops`
- `ix_transaction_bank_category_trgm` on `category` using `gin_trgm_ops`

Both indexes apply only to rows where `type = 'bank_transaction'`. The transaction table is shared by multiple transaction subclasses; the partial predicate avoids including unrelated transaction rows in these indexes.

Trigram indexes can help with suitable `LIKE`/`ILIKE` substring patterns. They are not a guarantee of faster queries: index selection depends on data volume, selectivity, pattern length and the PostgreSQL planner's estimates. Run the migration against the intended database and inspect real plans with:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT ...;
```

Check both the normal ordered transaction page and description/category searches. Record the dataset size and plan; do not document an index as beneficial solely because it exists.

## Cursor / Keyset Pagination

### Why move away from offset pagination?

Offset pagination commonly requires the database to walk past earlier rows for later pages. The old API also calculated an exact `COUNT(*)` for page metadata. As the transaction history grows, the work can increase even when the client only needs the next small page.

The new-client path uses keyset pagination ordered by:

```sql
ORDER BY date DESC, id DESC
```

The ID is a deterministic tie-breaker when two transactions share the same timestamp. The next page uses the lexicographic predicate:

```sql
(date, id) < (:cursor_date, :cursor_id)
```

The endpoint fetches `page_size + 1` rows. The extra row determines whether another page exists, so the normal cursor path does not need an exact total count. The older page-number path remains available when a request supplies `page`; it continues to use offset pagination and `COUNT(*)` for compatibility during frontend/backend rollout.

### Cursor contents and scope

The URL-safe Base64 cursor stores the precise timestamp, transaction ID, a version and a SHA-256 digest of the active filter scope. The digest prevents a client from accidentally reusing a cursor with a different bank, user, page size or filter set.

The digest is not a keyed signature, and Base64 is not encryption. The cursor is not an authorization credential. The route independently verifies that the authenticated user owns the requested bank. If tamper resistance becomes a requirement, evaluate an HMAC-signed cursor as a separate API-security decision.

### Pagination consistency

Keyset pagination avoids the row-shifting behavior that can occur when newer rows are inserted ahead of an offset between requests. The branch tests include a case that inserts a newer transaction after page one and verifies that the subsequent cursor page continues from the prior boundary.

It does not create a database snapshot spanning multiple HTTP requests. Updates/deletes to rows and concurrent writes still need to be understood in the context of the endpoint's intended consistency model.

## Dashboard Cache-Aside with Redis

Redis is an optional cache for dashboard aggregates. PostgreSQL remains the source of truth. The cache is enabled through `REDIS_URL`; the configured defaults include a 60-second payload TTL and a maximum Redis connection pool size of 5.

Cached dashboard resources:

- Summary
- Spending for each supported range (`30d`, `3m`, `6m`, `1y`, `all`)
- Asset allocation

### Cache-aside read flow

```text
Authenticated dashboard request
        ↓
Read the user's generation token
        ↓
Build a user + generation + resource cache key
        ↓
Cache HIT? ── Yes ──> Return cached payload
        │
        No
        ↓
Calculate from PostgreSQL
        ↓
Store under the generation observed before calculation
        ↓
Return database result
```

The response includes `X-Dashboard-Cache` with `HIT`, `MISS` or `BYPASS`, which helps observe which path ran. It does not itself measure the speedup.

### Generation-token invalidation

Each user has a generation key. A successful database write rotates that user's generation value. New dashboard requests therefore build a new key namespace and do not find cached values from the prior generation. This avoids scanning or deleting every old resource key. Old values expire under their own short TTL.

The reviewed branch adds invalidation hooks after successful writes in bank, savings, asset, credit-card and user route modules. When extending or changing a financial write path, check whether it can affect summary, spending or asset allocation and whether the invalidation hook is present after commit.

### Failure behavior and consistency trade-off

Redis is fail-open: missing configuration or cache read/write failures fall back to the database. A Redis outage should not make ordinary financial writes fail. If invalidation fails after the PostgreSQL transaction has committed, an older cached dashboard response can remain accessible until the cache TTL expires. This is bounded staleness, not immediate consistency.

The production backend has a Redis service deployed on Render alongside it and uses `REDIS_URL` to connect. The current Docker Compose backend environment does not pass `REDIS_URL` and the Compose file does not define a Redis service, so local Compose bypasses Redis by default. Use the `X-Dashboard-Cache` response header (`HIT`, `MISS` or `BYPASS`) to observe the runtime path without recording the connection URL or credentials in project documentation.

The testing configuration explicitly sets `REDIS_URL = None`, so the regular backend test suite does not require an external Redis service. `tests/test_dashboard_cache.py` uses deterministic fake Redis clients to cover a cache hit, generation invalidation/user isolation, Redis failure fallback and invalidation following a bank transaction. These test cases are present in the branch; their execution must still be verified.

## Frontend Transaction Table and Navigation

The bank page now maintains search input and debounced search state separately. A 300 ms debounce avoids issuing a request for every keystroke. Cursor history is stored in a React ref so remembering the next cursor does not itself trigger another fetch. Page, page size and filter changes reset or use the appropriate cursor boundary.

An effect cleanup flag prevents stale results from updating the component after the relevant request effect has been cancelled. After a transaction is added, the cursor history resets and page one is refreshed; a partial page is not manually modified on the client.

The shared `TransactionTableDialog` supports both cursor pagination and the legacy page-number display, and exposes search, type, date, amount and clear-filter controls with loading/error feedback.

The desktop navigation sidebar uses CSS `position: sticky` below a calculated header offset. It has its own vertical scrolling container and is not viewport-fixed. The mobile navigation retains overlay behavior and closes after navigation.

## Tests Added for the Performance Changes

The reviewed `tests/test_banks.py` adds cases for cursor validation/scope, concurrent insertion between cursor pages, combined filters, legacy pagination, avoiding exact count queries on the cursor path, search contract, amount boundaries, IST boundaries, invalid filters and authorization.

`tests/test_dashboard_cache.py` adds four tests for cache hit, generation invalidation and user separation, Redis outage fallback, and bank-transaction invalidation.

The code review confirms that test cases are present; it does not prove that they pass. Run focused tests first, then the complete backend regression suite, and record the actual command, environment and output. The previous `389 passed, 5 warnings` result remains historical until rerun.

## Current Testing Position

The backend testing foundation is established, and testing now needs to progress from module-by-module coverage to a systematic audit of remaining transaction behaviors.

### Backend Testing Status

The existing backend suite covers:

- Authentication and users
- Banks
- Savings
- Assets
- Transaction exports and backup
- Credit cards
- Dashboard

The last recorded full backend regression result in the project notes is:

`389 passed, 5 warnings`

This result has not been independently re-run during the latest repository review.

### CI Testing Status

The current `.github/workflows/ci.yml` already contains:

- A PostgreSQL 17 test database service
- Python 3.12 dependency installation
- Backend Python validation
- Backend pytest execution
- Node.js 22 setup
- Frontend dependency installation
- React production build validation

The missing CI component is frontend automated test execution.

The workflow definition does not prove that the latest remote run is green, so actual GitHub Actions results must still be checked.

### Frontend Testing Readiness

The frontend has a test script and React Testing Library dependency, but the current `App.test.js` is a default starter test rather than a PPA test.

`setupTests.js` imports `@testing-library/jest-dom`, but that dependency is absent from the committed frontend package manifest and lockfile. The test setup must be corrected before useful frontend testing can begin.

### Immediate Learning Position

```text
Backend module testing           ✅ Established
Backend test execution in CI     ✅ Configured
Transaction coverage audit       ← NEXT
Frontend test setup               ⏳
Frontend component/form tests     ⏳
Frontend tests in CI              ⏳
Full Phase 3 verification         ⏳
RAG and AI learning               ⏳ Planned for Phase 3B
```

The purpose of the remaining work is to learn how to find meaningful behavioral gaps, construct reliable tests and use CI as regression protection—not merely to increase the test count.

# Next Learning Goals

## Phase 3 — Backend Transaction Audit

The immediate learning goal is to identify meaningful gaps in the existing transaction tests.

Focus on:

- Reviewing active transaction routes and their validation branches.
- Understanding how input validation affects balances and database records.
- Testing invalid inputs and confirming that rejected operations have no unwanted side effects.
- Checking ownership, missing-resource behavior, transaction history and error responses.
- Distinguishing a test setup problem from a genuine application defect.
- Re-running the complete regression suite after changes.

## Frontend Automated Testing

Once the backend audit is sufficiently complete:

- Resolve the frontend test dependency/setup mismatch.
- Replace the default Create React App starter test.
- Learn to render components and query the resulting UI.
- Test form input, validation and error messages.
- Mock API requests where appropriate.
- Test loading, successful and failed API interactions.
- Test important transaction, deletion and backup/export workflows.

The goal is to test observable behavior rather than internal implementation details wherever practical.

## CI Testing

The backend pytest command is already configured in GitHub Actions.

Remaining learning goals:

- Understand how PostgreSQL is provisioned as a CI service.
- Verify that backend tests run against the isolated test database.
- Add frontend automated test execution to CI.
- Retain React production build validation.
- Understand how failed test commands prevent a workflow from passing.
- Verify actual workflow results in GitHub Actions.
- Learn how GitHub branch protection and required status checks relate to the CI workflow.

## Phase 3B — RAG and AI Learning

After Phase 3, learn RAG through a separate document chatbot before extending PPA.

Concepts to study:

- LLM fundamentals and embeddings
- Document extraction, chunking and metadata
- Vector similarity and semantic retrieval
- PostgreSQL full-text search and hybrid retrieval
- Context construction and grounded responses
- Source citations and insufficient-evidence handling
- Retrieval evaluation and regression testing
- Model latency, token usage and cost control

The first copilot should use approved documentation and trusted financial-education material. Personalized financial analysis should follow only after the required security controls are implemented.

## DevOps Progression

The intended progression remains:

```text
Working full-stack application
        ↓
Git / GitHub workflow
        ↓
GitHub Actions CI
        ↓
Automated backend and frontend testing
        ↓
Phase 3 complete
        ↓
Phase 3B — RAG and AI learning
        ↓
Docker build in CI
        ↓
Continuous deployment
        ↓
Production configuration and security
        ↓
Reliability and rollback
        ↓
Logging and monitoring
        ↓
System design and scalability
        ↓
Optional advanced engineering
```

The goal is to understand why each engineering practice exists, how to implement it correctly, and what trade-offs it introduces. Additional technologies should be adopted only when they solve an identified problem.
