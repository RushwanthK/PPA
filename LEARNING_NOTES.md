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

## Current Testing Position

```text
Backend module testing
├── Authentication / Users   ✅
├── Banks                    ✅
├── Savings                  ✅
├── Assets                   ✅
├── Transaction exports      ✅
├── Credit Cards             ✅
├── Dashboard                ✅
└── Transaction audit        ← NEXT
```

Frontend testing is intentionally deferred until the remaining meaningful backend testing work is complete.

# Next Learning Goals

## Backend Testing

* Learn how to identify testing gaps from route and business-logic branches.
* Distinguish unit-style assertions from API integration/behavior tests.
* Strengthen database side-effect verification.
* Identify transaction-specific edge cases that are worth testing.

## CI Testing

After backend and frontend tests are established, integrate them into GitHub Actions so that tests become part of the repository's required validation flow.

## DevOps Progression

The intended progression remains:

```text
Develop
  ↓
Version control
  ↓
CI
  ↓
Automated tests
  ↓
Docker build in CI
  ↓
Continuous deployment
  ↓
Production configuration/security
  ↓
Reliability
  ↓
Monitoring
  ↓
System design / scaling
```
