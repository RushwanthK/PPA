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

## Database

* PostgreSQL

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

**Last recorded backend regression result:** `389 passed, 5 warnings`.

This result comes from the existing project notes and has not been independently re-run during the latest documentation review. Re-run the full test suite before treating it as the current verified result.

The remaining backend work is to review transaction-specific edge cases, close meaningful coverage gaps, and perform conservative cleanup where justified by the findings.

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

The workflow does not yet run frontend automated tests or build Docker images. A successful recent GitHub Actions run and repository branch-protection settings still need to be verified.

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

1. Complete the backend transaction-specific testing audit.
2. Resolve the frontend test setup and replace the starter test.
3. Add meaningful frontend regression tests.
4. Add frontend test execution to GitHub Actions while retaining the production build check.
5. Verify the complete pipeline and update the status after successful execution.

# Current Features

## Dashboard

* Financial overview
* Summary cards
* Net worth calculations
* Spending analysis
* Asset allocation

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

---

# Project Structure

```text
PPA
│
├── app/                 # Flask backend
├── portfolio-app/       # React frontend
├── migrations/          # Alembic migrations
├── tests/               # Backend automated tests
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
- [ ] Complete the transaction-specific backend coverage audit
- [ ] Investigate non-finite transaction amounts (`NaN` and infinity) for bank and credit-card transactions
- [ ] Address any confirmed validation or regression gaps
- [ ] Complete conservative backend cleanup where justified
- [ ] Resolve the frontend test setup and dependency issue
- [ ] Replace the default frontend starter test with meaningful PPA tests
- [ ] Add component, form, API interaction, transaction and error-feedback tests
- [ ] Add frontend test execution to GitHub Actions
- [ ] Verify consistent backend and frontend test execution
- [ ] Verify the latest successful CI run and the required-check settings for pull requests

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
- [ ] Analyze performance bottlenecks
- [ ] Evaluate caching, Redis and background jobs against real requirements
- [ ] Document RAG retrieval, financial calculation and LLM-generation boundaries
- [ ] Evaluate scalability and concurrent workloads

## Phase 10 — Advanced / Optional Engineering

- [ ] Evaluate rate limiting and API versioning
- [ ] Evaluate caching and background jobs
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
