# ResumeLens AI

*See your resume the way a recruiter and an ATS see it.*

ResumeLens AI scores how well a resume fits a job description and ties every finding to a specific line in the resume or the JD. It separates honest rewrites from real skill gaps, and keeps every analysis and resume version per user.

## Free stack

Everything runs on free tiers. The original spec used Azure; this is what each piece maps to.

| Spec | What this repo uses | Cost |
|---|---|---|
| Azure OpenAI chat model | Groq (`openai/gpt-oss-120b`) or Gemini, picked with `LLM_PROVIDER`; `mock` needs no key | Free tier |
| text-embedding-3-small | Gemini embeddings at 768 dims, or `local` hashing vectors with no key | Free |
| Azure Database for PostgreSQL | Postgres 16 + pgvector in Docker locally; Render free PostgreSQL when hosted | Free (Render deletes free databases after 30 days) |
| App Service + Static Web Apps | One Render free web service (FastAPI serves the built React app) | Free |
| Azure Blob Storage | Uploaded files are stored in PostgreSQL, since Render's free disk is wiped on every redeploy | Free |

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
.\.venv\Scripts\python -m uvicorn app.main:app --port 8010 --reload --reload-dir app

# 3. Web app on http://localhost:5180  (in a second terminal)
cd frontend
npm install
npm run dev
```

If backend code changes don't show up, stop the API with `Ctrl+C` and start it again. On Windows the auto-reloader sometimes leaves the old server running.

Run the backend tests with `.\.venv\Scripts\python -m pytest` from `backend/` while the database is up.

## Deploy on Render (free)

The [Dockerfile](Dockerfile) builds the React app and serves it from FastAPI, so the whole app is one Render web service. [render.yaml](render.yaml) also creates a free Render PostgreSQL database and connects the app to it. Migrations run on every start. Uploaded files are stored in PostgreSQL, because Render's free disk is wiped on every redeploy and restart.

1. Push this repo to GitHub.
2. In Render: New → Blueprint → pick the repo → Apply. No values need to be typed in; Render creates the database, a random `JWT_SECRET` and HTTPS-only cookies.
3. Every push to `main` redeploys automatically.

Free-plan limits:
- The web service sleeps after 15 minutes without traffic, so the next request takes about a minute.
- **Render deletes a free database 30 days after it is created** (it emails you first). After that, create a new free database (data is not carried over), upgrade it, or use another free PostgreSQL such as [Neon](https://neon.tech), which doesn't expire: set `DATABASE_URL` to its connection string and remove the `databases` section from `render.yaml`.

## Project layout

```
backend/   FastAPI app, SQLAlchemy models, Alembic migrations, pytest
frontend/  React 18 + Vite + TypeScript, Tailwind CSS, shadcn/ui-style components
docker-compose.yml   Postgres 16 + pgvector for development
```

## What the app does

1. **New analysis**: upload a new resume (PDF/DOCX), or pick a saved one, and score it against a new JD (paste or upload) or a saved one.
2. **Match report**: a 0-100 score, a must-have / nice-to-have requirement checklist (met, partial or missing), the resume lines that prove each requirement, a score breakdown, and the ATS keywords that are present or missing.
3. **History**: every analysis with its score and the resume and JD it used. Reports keep a snapshot, so they still read correctly after the resume or JD is deleted.

**How scoring works:** the matcher finds the requirements in the JD and checks each one against the numbered resume lines. With `LLM_PROVIDER=mock` (no key) the built-in matcher uses a skills vocabulary with aliases, years of experience from date ranges, degree levels and wording overlap. Set `LLM_PROVIDER=groq` or `gemini` with a free key to use an AI model instead; it falls back to the built-in matcher if the model fails, and any evidence line it cites that doesn't exist is thrown out. The score itself is always computed in Python: 75% requirement fit (must-haves weigh 3, nice-to-haves 1; partial = half credit) plus 25% keyword coverage.

## Build phases

- [x] **1. Foundation**: monorepo, Docker Compose with Postgres + pgvector, FastAPI skeleton, Alembic migrations, React + Vite + Tailwind + shadcn/ui shell with dark mode
- [x] **2. Core app**: sign up / log in (Argon2, httpOnly cookies, route guard); resume upload (PDF/DOCX) and JD paste/upload with numbered lines; scoring and requirement matching with evidence; match report; history
- [ ] **3. Polish**: tests for the React app, GitHub Actions CI
