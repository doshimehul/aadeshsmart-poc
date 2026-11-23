# AadeshSmart POC

## Frontend setup

The Next.js application lives in `frontend/` and uses the App Router, TypeScript, and a responsive volunteer workspace shell.

1. Install Node.js 18.18 or newer.
2. From `frontend/`, install dependencies and create local settings:

   ```bash
   npm install
   cp .env.example .env.local
   npm run dev
   ```

The frontend runs at `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` to the backend API origin (default `http://localhost:8000`). The app includes a web manifest and service worker for installation and app-shell caching. Serve production builds over HTTPS for installation outside localhost.

## Backend setup

Requires Python 3.11+ and Docker Compose.

1. Create local settings and start PostgreSQL:

   ```bash
   cp .env.example .env
   docker compose up -d db
   docker compose ps
   ```

   PostgreSQL data is stored in the `postgres_data` Docker volume and survives container restarts.
2. From the repository root, create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Start the API from the repository root:

   ```bash
   uvicorn app.main:app --app-dir backend --reload
   ```

API: `http://localhost:8000`; interactive docs: `/docs`. `GET /api/health` checks the API and PostgreSQL connection and returns HTTP 503 if PostgreSQL is unavailable.

Stop PostgreSQL with `docker compose down`. To remove its stored data too, run `docker compose down -v`.

## Tests

Run from the repository root:

```bash
PYTHONPATH=backend pytest backend/tests
```

The health endpoint test replaces the database dependency, so it does not require a running PostgreSQL instance.

## Migrations

Alembic reads `DATABASE_URL` from `.env`. The initial application-owned `ledgers` and `recordings` schema is defined in `backend/app/models` and created by the first migration. Apply it to the configured project database with:

```bash
alembic upgrade head
```

Confirm `DATABASE_URL` points to the intended AadeshSmart project database before applying migrations. The migration does not modify any external donor database.

## Recording processing

Uploads are processed by one FastAPI background task. Development defaults to mock Sarvam and Gemini providers; set `SARVAM_MODE=live` and/or `GEMINI_MODE=live` with `SARVAM_API_KEY` and `GOOGLE_API_KEY` to use the real providers. Provider timeouts and the Gemini model are configurable in `.env`.

Processing checkpoints are returned by the recording endpoints under `/api/v1/recordings`. Retry a failed recording with `POST /api/v1/recordings/{recording_id}/retry`. The repository method `RecordingRepository.list_stale_in_progress(older_than)` identifies jobs whose `modified` timestamp is older than the operator's chosen recovery threshold; inspect those records before taking manual recovery action.
