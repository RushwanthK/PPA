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

# Sprint 13 - Phase 3: Regression, Auth/API Security and Frontend Tests

Phase 3 was widened so that the public app's auth and API security is hardened before testing is declared complete: 3A backend regression, 3B auth/API security, 3C frontend tests, 3D CI and docs. Everything below was verified locally on November 23, 2026. None of it has been deployed yet.

## 3A — Backend Regression

- Re-ran the full suite before adding anything, to get an honest baseline (`414 passed`).
- Found one real defect: the credit-card page showed "transactions billed" and "total amount billed" after processing billing, but the backend never returned those fields. The fix adds them to the response without touching the billing calculation.
- Lesson: a frontend reading a field the backend never sends fails silently (it shows `undefined`). Contract tests on both sides catch this.

## 3B — Rate Limiting

Concepts:

- **Two keys for login:** one per client IP counts every attempt (brute force and CPU protection). One per account counts only failed attempts (`deduct_when` the reply is 401), so a distributed attack on one account is capped even across many IPs, while a user who logs in successfully uses nothing.
- **Order matters:** Flask-Limiter checks limits in `before_request`, before the view and before PBKDF2 hashing (~0.4 s of CPU each). With one Gunicorn worker, an unlimited `/login` is also a denial-of-service vector.
- **Moving window vs fixed window:** a fixed window allows a burst of 2× the limit across a window boundary; moving window stores each hit's timestamp and has no boundary burst.
- **Real client IP behind a proxy:** without `ProxyFix`, every request appears to come from Render's proxy, so all users share one bucket. `ProxyFix(x_for=N)` trusts exactly N hops from the right of `X-Forwarded-For`. Values further left are client-controlled and ignored. N must match the real infrastructure (`TRUSTED_PROXY_COUNT`).
- **Hashing usernames in keys:** keeps Redis keys short and fixed-length, and avoids storing usernames in plain text.
- **Timing side channel:** for unknown usernames, the password is checked against a dummy hash so "no such user" takes as long as "wrong password".
- **Fail-open choices:** if Redis is down, limits fall back to per-process memory, and storage errors are swallowed so a normal 401 never becomes a 500.

Verification lesson: the first Redis key scan used the wrong pattern (the library adds its own `LIMITS:LIMITER/` prefix). It found zero keys, and the "every key has a TTL" check passed while checking nothing. **A check that inspects zero items proves nothing.** Always assert that the sample is non-empty.

## 3B — JWT Lifecycle

- **Problem:** a stateless JWT stays valid until it expires (one day). Logout only deleted it in the browser, and a stolen token kept working.
- **Two revocation mechanisms:**
  - `token_version` on the user is copied into each token as `ver`. Incrementing it invalidates every earlier token at once (logout-all, password change).
  - The `revoked_token` table holds individual `jti` values for single-device logout. Rows are pruned after the token's own expiry.
- **Cost:** one combined indexed query per authenticated request. This is acceptable at PPA's scale, and the bank query-count test was updated (2 → 3 SELECTs) with an explanation instead of being loosened.
- **Where security state lives:** the Redis instance is a disposable cache with `allkeys-lru`. An evicted revocation would silently re-enable a logged-out token, so revocation lives in PostgreSQL. Cache data can be lost; security state cannot.
- **Backward compatibility:** tokens issued before the change have no `ver` claim and are treated as 0. The migration gives existing users 0, so deploying logs nobody out.
- **Status codes are a contract:** Flask-JWT-Extended returns 422 for malformed or wrongly signed tokens, but the frontend only logs out on 401. Rotating the secret would have left users stuck with a dead token. All token problems now return 401.
- **Password change:** requires the current password, and wrong attempts are rate-limited. A wrong attempt returns 403, not 401, so the frontend does not log the user out for a typo. A successful change ends other sessions and returns a new token for this device.
- **Key length:** HS256 keys under 32 bytes can be brute-forced offline from any captured token, which would allow forging tokens for any user. PyJWT 2.15 warns about this, and the app now logs a warning at startup.

Migration lesson: adding a `NOT NULL` column with a constant default is metadata-only on PostgreSQL 11+ (no table rewrite). An additive migration can be applied before the new code ships, which makes the deploy order safe. The migration was tested with upgrade → downgrade → upgrade on a throwaway database.

## 3B — API Hardening

- **Request size limit:** `MAX_CONTENT_LENGTH` rejects large bodies with 413 before they are parsed.
- **Error replies:** returning `str(e)` can leak table names, constraint names or SQL. The client now gets a generic message, and the server log gets the full traceback, so the app stays debuggable.
- **Route-coverage test:** iterate over `app.url_map`, call every route without a token, and expect 401 unless the endpoint is on an explicit public allowlist. A future route that forgets `@jwt_required` fails CI. The sweep also showed that a suspected unauthenticated `/transfers` endpoint was inside a dead commented-out string, so it was never live. Lesson: verify by running the app, not by reading code that may not execute.
- **CORS credentials:** only needed for cookies. PPA sends the token in a header, so `supports_credentials` was turned off. Deploy order then matters, because the old frontend still requests credentials.
- **Security headers on an API:** `default-src 'none'` and `frame-ancestors 'none'` are safe for JSON responses. A CSP for the React site itself is a separate, riskier change.
- **Dependency audits:** `pip-audit` guided Python upgrades until it reported nothing. `npm audit` findings must be read by where the package runs: CRA build tooling never reaches the browser bundle, so those advisories are lower priority than runtime packages.

## 3C — Frontend Tests

- Fixed the setup first. `@testing-library/jest-dom` was imported but not declared, and jsdom lacks `TextEncoder`, `matchMedia` and `ResizeObserver`.
- Used `moduleNameMapper` so ESM-only builds of axios and react-router v7 load under CRA's Jest.
- Tested observable behavior: what the user sees and which API call is made, not component internals. API modules are mocked at the service boundary.
- The tests found a real accessibility bug: every modal used the same `id="modal-title"`, so stacked modals announced the wrong title. `useId()` gives each instance its own id.

## 3D — CI

- The workflow now runs the frontend tests (`CI=true`, no watch mode) before the build.
- The CI JWT key had to be lengthened after the PyJWT upgrade. Warnings jumped from 5 to 708, which is a reminder to read the warnings, not just the pass count.

## Engineering Habits Reinforced

- Inspect the real code before changing it, and correct claims publicly when evidence disproves them.
- State what was verified and what was not: local tests are not a GitHub Actions run, and a local Redis is not production Redis.
- Keep line endings consistent. Mixed CRLF/LF made git show whole-file rewrites and hid the real diff.
- Do not inflate test counts. Every new test protects a specific behavior.

## Current Learning Position

```text
Backend regression (3A)          ✅ 465 passed locally
Rate limiting (3B)               ✅ Verified with real local Redis
JWT logout / revocation (3B)     ✅
API hardening + deps (3B)        ✅
Frontend tests (3C)              ✅ 201 passed locally
CI workflow + docs (3D)          ✅ Updated
Commit, deploy, real CI run      ← NEXT
Refresh tokens / token storage   ⏳ Later security work
RAG and AI learning              ⏳ After Phase 3
```

# Next Learning Goals

## Shipping Phase 3 Safely

- Order a deploy across auto-deploying (Vercel) and manually deployed (Render) services so that no old/new combination breaks.
- Apply an additive migration ahead of the code that needs it.
- Configure production secrets and proxy settings, and verify behavior in production rather than assuming it.
- Read a real GitHub Actions run, and understand required status checks and branch protection.

## Later Security Work

- Short-lived access tokens with refresh tokens and rotation
- Trade-offs of `localStorage` versus httpOnly cookies (XSS versus CSRF)
- A Content-Security-Policy for the React site
- Migrating from Create React App to a maintained build tool

## RAG and AI Learning (after Phase 3)

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
Targeted auth/API security
        ↓
Phase 3 complete
        ↓
RAG and AI learning
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
