# Universal Autonomous Growth Agent

A self-hosted foundation for a modular growth platform. This initial project provides a FastAPI backend, a React dashboard, and local PostgreSQL and Redis infrastructure. It does not yet include project management, campaign execution, AI providers, or background jobs.

## Requirements

- Windows 10/11 with PowerShell
- Python 3.11 or newer
- Node.js 22.12 or newer (npm is included)
- Docker Desktop with Docker Compose

## Windows setup

Run these commands from the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and replace `POSTGRES_PASSWORD` and the matching password in `UGA_DATABASE_URL` with a local password. Use a URL-safe password, or percent-encode reserved URL characters in `UGA_DATABASE_URL`. Keep `.env` private; it is ignored by Git.

Use IPv4 loopback for Redis on Windows. This avoids a slow initial IPv6 `localhost` connection attempt when Docker publishes Redis only on IPv4:

```env
UGA_REDIS_URL=redis://127.0.0.1:16379/0
```

Use the Redis port configured by `REDIS_PORT`; the value above matches the default local project configuration when Redis is published on port `16379`.

Start PostgreSQL and Redis:

```powershell
docker compose up -d postgres redis
docker compose ps
```

Set up the backend virtual environment and install its dependencies (including test tools):

```powershell
cd apps/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000
```

If PowerShell blocks activation, use the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The virtual environment is created in `apps/backend`.

In a second PowerShell window, start the dashboard:

```powershell
cd apps/dashboard
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). The dashboard calls the backend health endpoint and shows the returned database and Redis states. If the backend is stopped, it reports the API as unavailable.

## Verify the foundation

From `apps/backend` with its virtual environment active:

```powershell
python -m pytest
```

The database connectivity test runs when `UGA_TEST_DATABASE_URL` is set; otherwise it is skipped. The API health endpoint still checks the configured runtime connection URLs from the root `.env`.

### Dedicated PostgreSQL test database

`UGA_TEST_DATABASE_URL` must always target a database that is separate from `universal_growth`. The current integration test only runs `SELECT 1`, but keeping a dedicated database prevents future tests from ever affecting development data.

After reviewing the operation, create the dedicated database once using the local PostgreSQL administrator account:

```powershell
docker exec uga-postgres psql -U uga -d postgres -c "CREATE DATABASE universal_growth_test OWNER uga;"
```

Before running the integration test, set the URL only in the current PowerShell session. Replace `<url-encoded-password>` with the local password from `.env`; do not commit it or add it to `.env.example`.

```powershell
$env:UGA_TEST_DATABASE_URL = "postgresql+psycopg://uga:<url-encoded-password>@127.0.0.1:15432/universal_growth_test"
cd apps/backend
.\.venv\Scripts\python.exe -m pytest -q tests/test_database.py
Remove-Item Env:UGA_TEST_DATABASE_URL
```

Confirm the URL database name is `universal_growth_test` before running the test. Never use `universal_growth` for `UGA_TEST_DATABASE_URL`.

### Health verification

With Docker and the backend running, verify the live dependency state:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/info
```

The healthy response reports both PostgreSQL and Redis as `connected`. The system information response reports only the application name, version, and environment.

From `apps/dashboard`:

```powershell
npm run typecheck
npm run lint
npm run build
```

Useful local URLs:

- Dashboard: `http://localhost:5173`
- API health: `http://localhost:8000/api/v1/health`
- System metadata: `http://localhost:8000/api/v1/system/info`
- Interactive API docs: `http://localhost:8000/docs`

Stop local infrastructure with `docker compose down`. Named volumes keep the database and Redis data between runs.

## Configuration

Backend settings are read from `UGA_`-prefixed environment variables. See `.env.example`. CORS origins are a JSON array. `UGA_DATABASE_URL` and `UGA_REDIS_URL` are optional; an unconfigured or unreachable service is reported honestly as `not_configured` or `unavailable`, and the aggregate health state becomes `degraded`.

See [docs/MASTER_ARCHITECTURE.md](docs/MASTER_ARCHITECTURE.md), [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md), and [docs/TECH_STACK.md](docs/TECH_STACK.md) for architecture and upgrade guidance.
