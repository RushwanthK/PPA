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
                     ▼
             PostgreSQL Database
```

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
                  ▼
      Supabase PostgreSQL Database
```

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
    └── Routes
```

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
    └── transaction_export_util.py

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
```

---

# Planned RAG / AI Extension — Phase 3B

**Status: Planned; not implemented in the reviewed repository snapshot.**

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