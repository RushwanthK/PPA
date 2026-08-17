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
app
│
├── __init__.py
├── models.py
├── routes.py
├── dashboard_routes.py
├── dashboard_service.py
└── migrations/
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

# Future Docker Architecture

```
                   User
                     │
                     ▼
             React Container
                     │
                     ▼
             Flask Container
                     │
                     ▼
         PostgreSQL Container
```

---

# Future CI/CD Pipeline

```
Developer
      │
      ▼
Git Commit
      │
      ▼
GitHub Repository
      │
      ▼
GitHub Actions
      │
      ▼
Docker Build
      │
      ▼
Deploy to Cloud
```
