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

The backend is actively being tested as part of Phase 3.

Current full backend regression result:

```text
389 passed
5 warnings
0 failed
```

Completed backend testing areas include:

* Authentication / Users
* Banks
* Savings
* Assets
* Transaction exports / backup
* Credit Cards
* Dashboard

The remaining backend work is a transaction-specific coverage audit. Frontend automated testing will be handled separately afterward.

---

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

* [x] Docker Fundamentals
* [x] Dockerized Backend
* [x] Dockerized Frontend
* [x] PostgreSQL Docker Container
* [x] Docker Compose
* [x] Git / GitHub Workflow
* [x] GitHub Actions CI Foundation
* [ ] Complete remaining backend testing audit
* [ ] Frontend automated testing
* [ ] Backend + frontend tests enforced in CI
* [ ] Docker build in CI
* [ ] Automated Render deployment
* [ ] Production security/configuration
* [ ] Health checks / reliability
* [ ] Logging / monitoring
* [ ] System design / scalability
* [ ] Advanced engineering topics

---

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
