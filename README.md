# ResumeLens AI

*See your resume the way a recruiter and an ATS see it.*

ResumeLens AI scores how well a resume fits a job description and ties every finding to a specific line in the resume or the JD. It separates honest rewrites from real skill gaps, and keeps every analysis and resume version per user.

## Free stack

Everything runs on free tiers. The original spec used Azure; this is what each piece maps to.

| Spec | What this repo uses | Cost |
|---|---|---|
| Azure OpenAI chat model | Groq (`openai/gpt-oss-120b`) or Gemini, picked with `LLM_PROVIDER`; `mock` needs no key | Free tier |
| text-embedding-3-small | Gemini embeddings at 768 dims, or `local` hashing vectors with no key | Free |
| Azure Database for PostgreSQL | Postgres 16 + pgvector in Docker locally; Neon free tier when hosted | Free |
| App Service + Static Web Apps | One Render free web service (FastAPI serves the built React app) | Free |
| Azure Blob Storage | Decided in phase 3 (Render's free disk is wiped on redeploy) | Free |

## Run it locally

You need Docker Desktop, Python 3.11+ and Node 20+.

```powershell
# 1. Database (Postgres + pgvector on port 5433)
docker compose up -d db

# 2. API on http://localhost:8010  (docs at /api/docs)
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --port 8010 --reload

# 3. Web app on http://localhost:5180  (in a second terminal)
cd frontend
npm install
npm run dev
```

Run the backend tests with `.\.venv\Scripts\python -m pytest` from `backend/` while the database is up.

## Project layout

```
backend/   FastAPI app, SQLAlchemy models, Alembic migrations, pytest
frontend/  React 18 + Vite + TypeScript, Tailwind CSS, shadcn/ui-style components
docker-compose.yml   Postgres 16 + pgvector for development
```

## Build phases

- [x] **1. Foundation**: monorepo, Docker Compose with Postgres + pgvector, FastAPI skeleton, Alembic migration for all six tables, React + Vite + Tailwind + shadcn/ui shell with dark mode
- [ ] **2. Auth**: signup / login / logout / refresh / me, Argon2, httpOnly cookies, route guard, avatar menu
- [ ] **3. Upload and parse**: PDF/DOCX resume upload, JD upload or paste, text with line ids, library pages
- [ ] **4. Scoring pipeline v1**: LangGraph Parse → Extract → Match → Judge, score formula in Python, status polling, first Report page
- [ ] **5. History**: history table, dashboard cards, score trend chart, compare two analyses
- [ ] **6. Standout features**: Suggest + Verify (truth guard), evidence highlighting, apply and rescore, ATS parse preview
- [ ] **7. Polish and deploy**: PDF export, job fit board, interview prep, Vitest + Playwright, GitHub Actions CI, deploy to Render + Neon
