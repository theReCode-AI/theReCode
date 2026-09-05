# theReCode

Autonomous AI software-engineering platform for Python repositories on GitHub and GitLab.

theReCode analyzes repositories, runs diagnostics, plans and applies fixes, verifies changes, performs peer review, and creates pull requests — behaving like an autonomous software engineer rather than a chatbot.

## Monorepo Layout

```
backend/     FastAPI application, agents, and services
frontend/    React + Vite dashboard
workspace/   Runtime workspace for cloned repositories and run artifacts
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 22+
- Docker and Docker Compose

## Quick Start

### 1. Environment

```bash
cp .env.example .env
```

### 2. Start MongoDB

```bash
docker compose up -d mongodb
```

### 3. Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### 5. Full Stack via Docker

```bash
cp .env.docker.example .env
docker compose --profile app up --build
```

Open http://localhost:5173 (frontend proxies `/api` to the backend).

Validate the stack:

```bash
chmod +x scripts/validate-docker.sh
./scripts/validate-docker.sh
```

## Health Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/v1/health` | Liveness check |
| `GET /api/v1/health/ready` | Readiness check (includes MongoDB ping) |
| `GET /api/v1/auth/me` | Current authenticated user |
| `GET /api/v1/projects` | List current user's projects |
| `POST /api/v1/projects` | Create project |
| `POST /api/v1/git/credentials` | Save encrypted Git provider token |
| `POST /api/v1/projects/{id}/repositories/{repo_id}/validate` | Validate linked repository |
| `POST /api/v1/runs` | Create run and workspace layout |
| `GET /api/v1/runs/{id}/workspace` | Get run workspace paths |
| `POST /api/v1/runs/{id}/clone` | Clone linked repo into run workspace |
| `POST /api/v1/runs/{id}/analyze` | Analyze cloned repo (project intelligence) |
| `GET /api/v1/runs/{id}/intelligence` | Get stored project intelligence |
| `POST /api/v1/runs/{id}/diagnostics` | Run baseline scanner diagnostics |
| `GET /api/v1/runs/{id}/diagnostics` | Get stored baseline diagnostics |
| `POST /api/v1/runs/{id}/agents` | Run diagnostic agents (normalized findings) |
| `GET /api/v1/runs/{id}/findings` | List normalized findings for a run |
| `GET /docs` | OpenAPI documentation |




## License

Proprietary — theReCode
