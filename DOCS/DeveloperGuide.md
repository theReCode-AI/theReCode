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

## Development

### Backend tests

```bash
cd backend
uv run pytest
uv run ruff check .
```

### Frontend tests

```bash
cd frontend
npm test
npm run build
```

## Implementation Phases

| Phase | Scope |
|---|---|
| 1 | Monorepo foundation |
| 2 | FastAPI configuration + MongoDB |
| 3 | Authentication |
| 4 | Project and repository management |
| 5 | GitHub/GitLab provider abstraction |
| 6 | Workspace manager |
| 7 | Project Intelligence |
| 8 | Scanner services |
| 9 | Diagnostic agents |
| 10 | ADK root orchestration |
| 11 | Issue correlation |
| 12 | Fix planner |
| 13 | Risk engine |
| 14 | Code Fix Agent |
| 15 | Verification engine |
| 16 | Self-correction loop |
| 17 | Regression test agent |
| 18 | Multi-agent peer review |
| 19 | Human-in-the-loop |
| 20 | Memory system |
| 21 | Git finalization |
| 22 | Report generation |
| 23 | React dashboard |
| 24 | SSE live progress |
| 25 | Diff viewer + approvals |
| 28 | Dockerization |
| 31 | Google ADK 2.0 migration (current) |
| 29 | Cloud Run deployment |



## License

Proprietary — theReCode
