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

Although initially developed as a personal finance application, the project is primarily intended to demonstrate Full Stack Engineering skills including backend development, frontend development, database design, REST API development, authentication, deployment, and DevOps practices.

---

# Objectives

* Build a production-style full stack application
* Learn industry-standard software architecture
* Gain practical experience with backend and frontend integration
* Learn Docker, CI/CD and cloud deployment
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

## Deployment

* Frontend: Vercel
* Backend: Render
* Database: Supabase PostgreSQL

---

# Current Features

## Dashboard

* Financial overview
* Summary cards
* Net worth calculations

## Credit Cards

* Add/Edit/Delete credit cards
* Credit limits
* Available balance
* Used amount

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

```
PPA
│
├── app/                 # Flask backend
├── portfolio-app/       # React frontend
├── migrations/          # Alembic migrations
├── requirements.txt
├── run.py
├── config.py
├── README.md
├── ARCHITECTURE.md
├── PROJECT_STATUS.md
└── .env
```

---

# Local Development

Backend

```
python run.py
```

Frontend

```
npm start
```

---

# Future Roadmap

* Docker
* Docker Compose
* GitHub Actions
* Automated Testing
* Redis Caching
* Cloud Infrastructure
* Monitoring & Logging
* System Design Improvements

---

# Learning Goal

This repository serves both as a working application and as a structured learning project for mastering modern Full Stack Development and DevOps practices.

The configuration model I want us to reach

Think of the PPA like this:

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