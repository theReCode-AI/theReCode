# theReCode

Autonomous AI software-engineering platform for Python repositories on GitHub and GitLab.

theReCode analyzes repositories, runs diagnostics, plans and applies fixes, verifies changes, performs peer review, and opens pull/merge requests — behaving like an autonomous software engineer rather than a chatbot.

| Item | Value |
|------|-------|
| Product | theReCode |
| Backend version | `0.1.0` |
| License | Proprietary — theReCode |
| API base | `/api/v1` |

---

## Problem

Modern software teams face recurring engineering work that is slow, uneven, and hard to scale:

- **Quality and security debt** accumulate across Python codebases (lint, SAST, dependencies, secrets, tests, coverage).
- **Manual triage** of scanner noise is expensive; findings are siloed by tool and lack correlation.
- **Fix loops** (patch → test → rework) consume senior engineer time without durable institutional memory.
- **Chatbot-style AI** can suggest patches, but does not own end-to-end clone → diagnose → fix → verify → review → PR workflows with human gates and audit artifacts.

Teams need an autonomous system that can operate on real repositories with policy, approvals, and reproducible artifacts — not one-off chat completions.

---

## Solution

theReCode is a **monorepo platform** that runs a deterministic multi-stage pipeline over a cloned repository, with Gemini-backed specialist agents where planning, coding, and peer review benefit from LLM reasoning.

```
Create project → Link GitHub/GitLab repo → Save encrypted Git token
       → Create run → Clone into workspace → Execute autonomous pipeline
       → Human approvals (when required) → Branch + PR/MR → Report
```

**Monorepo layout**

```
backend/     FastAPI application, agents, scanners, Google ADK orchestration
frontend/    React + Vite operator dashboard
workspace/   Runtime clones and per-run artifacts
```

**Persistence model**

- **MongoDB** — users, projects, runs, findings, plans, approvals, memories, reports, etc.
- **Filesystem workspace** — clone, patches, diffs, baseline JSON, markdown/PDF reports under `THERECODE_WORKSPACE_ROOT`

**Primary orchestration entrypoint**

`POST /api/v1/runs/{id}/execute` → `GoogleAdkOrchestrator` (Google ADK 2.x Workflow graph + Gemini API)

---

## Features

### Operator dashboard (frontend)

| Route | Capability |
|-------|------------|
| `/login`, `/register` | JWT authentication |
| `/dashboard` | Project/run summary metrics, recent runs |
| `/projects` | Create/list projects; project cards with repo/run insight; sort by create date |
| `/projects/:projectId` | Link repos, start runs, list repositories and runs |
| `/runs/:runId` | Run overview — pipeline graph, timeline, clone/git actions |
| `/runs/:runId/findings` | Normalized findings |
| `/runs/:runId/diff` | Fix-attempt diffs |
| `/runs/:runId/approvals` | Human-in-the-loop cards (`approve` / `reject` / `request_changes`) |
| `/runs/:runId/reports` | Generated markdown/PDF reports |
| `/settings` | Account + encrypted Git credentials |

Live progress uses **Server-Sent Events** (`GET /api/v1/runs/{id}/stream`).

### Platform capabilities

- **Auth** — register/login, JWT bearer tokens
- **Projects & repositories** — GitHub/GitLab linked repos, validate/clone
- **Encrypted Git credentials** — provider tokens at rest
- **Workspace manager** — per-run directory layout (`baseline/`, `patches/`, `reports/`)
- **Project intelligence** — structural analysis of the cloned repo
- **Diagnostic agents** — seven agents wrapping industry scanners
- **Issue correlation** — group related findings into actionable issue groups
- **Fix planning & risk policy** — plans with autonomous vs approval-required decisions
- **Code fix + verification + self-correction** — iterative fix loops
- **Regression tests** — generated/executed after verification
- **Multi-agent peer review** — Security, Testing, Architecture + synthesizer
- **Human approvals** — risk gate and final review cards
- **Memory** — `project`, `decision`, `failure`, `success_strategy` for later planning
- **Git finalization** — branch `fix/<run_id>`, push, open PR/MR
- **Reports** — markdown + PDF run reports
- **Dark/light theme** — Flowbite theme mode

### Diagnostic agents and scanners

| Agent | Scanner |
|-------|---------|
| `code_quality_agent` | Ruff |
| `semgrep_agent` | Semgrep |
| `security_agent` | Bandit |
| `dependency_agent` | OSV Scanner |
| `secret_check_agent` | Gitleaks |
| `test_agent` | pytest |
| `coverage_agent` | coverage.py |

### Run lifecycle statuses

`CREATED` → `CLONING` → `ANALYZING` → `DIAGNOSING` → `PLANNING` → `AWAITING_APPROVAL` → `FIXING` → `VERIFYING` → `SELF_CORRECTING` → `PEER_REVIEW` → `FINAL_REVIEW` → `PUSHING` → `REPORTING` → `COMPLETED` | `FAILED` | `CANCELLED`

---

## Architecture

### High-level

```text
┌─────────────────┐     HTTPS / SSE      ┌──────────────────────────────┐
│  React Frontend │ ◄──────────────────► │  FastAPI (/api/v1)           │
│  Vite + Query   │                      │  Auth · Projects · Runs · Git│
└─────────────────┘                      └──────────────┬───────────────┘
                                                       │
                         ┌─────────────────────────────┼─────────────────────────────┐
                         ▼                             ▼                             ▼
                  ┌─────────────┐            ┌─────────────────┐            ┌──────────────┐
                  │  MongoDB    │            │ Google ADK      │            │  Workspace   │
                  │  Atlas/local│            │ Workflow+Gemini │            │  filesystem  │
                  └─────────────┘            └─────────────────┘            └──────────────┘
```

### Backend layers

```text
API routes (app/api/routes)
    → Application services (app/services)
        → Domain engines (app/adk/*, scanners, intelligence, git)
        → Repositories (app/db/repositories) → MongoDB
        → Workspace manager (app/workspace) → disk
```

Dependency injection lives under `backend/app/api/dependencies/`. Primary execute path wires **`GoogleAdkOrchestrator`** (legacy `RootOrchestrator` remains in tree but is not the default DI path).

### Frontend structure

```text
frontend/src/
  api/           HTTP + SSE clients (VITE_API_BASE_URL)
  pages/         Route-level screens
  components/    Layout, runs, projects, common UI
  stores/        Zustand (auth, app shell)
  routes/        React Router tree
  types/         Shared TypeScript models
```

### MongoDB collections

`users`, `projects`, `repositories`, `runs`, `agent_events`, `agent_states`, `findings`, `issue_groups`, `fix_plans`, `risk_decisions`, `fix_attempts`, `verification_results`, `self_correction_cycles`, `regression_test_results`, `reviews`, `approvals`, `memories`, `git_operations`, `git_credentials`, `reports`

### Execute data flow

1. Authenticate (JWT).
2. Create project, link repository, store Git credential.
3. Create run → workspace paths under `THERECODE_WORKSPACE_ROOT`.
4. `POST .../execute` → ADK Runner walks workflow nodes.
5. Deterministic stages write Mongo + disk artifacts; Gemini specialists call typed FunctionTools.
6. UI subscribes via SSE (`snapshot`, `run_update`, `state_update`, `agent_event`, `heartbeat`, `complete`).

---

## Agent Architecture

### Orchestration stages

Defined in `backend/app/adk/workflows/stages.py`:

`initialization` → `cloning` → `project_intelligence` → `diagnostics` → `issue_correlation` → `fix_planning` → `risk_assessment` → `code_fixing` → `verification` → `self_correction` → `regression_testing` → `peer_review` → `human_approval` → `memory` → `git_finalization` → `reporting` → `finalization`

### Google ADK workflows

Built in `backend/app/google_adk/workflow_builder.py`:

| Workflow | Purpose |
|----------|---------|
| `therecode_autonomous_run` | Full pipeline from initialize through finalize |
| `therecode_post_risk_approval_run` | Resume after risk-gate human approval (from code fix onward) |

### Stage types

| Kind | Stages | Implementation |
|------|--------|----------------|
| **Deterministic nodes** | Clone, intelligence, diagnostics, correlate, risk, verify, self-correct, regression, memory, git, report, … | `@node` functions in `pipeline_nodes.py` calling service container |
| **LLM specialists** | Fix planning, code fix, peer review | Gemini agents + FunctionTools in `google_adk/agents/specialists.py` |

### Gemini specialist agents

| Agent | Tool |
|-------|------|
| `fix_planner_agent` | `create_fix_plans` |
| `code_fix_agent` | `apply_autonomous_fixes` |
| `peer_review_agent` | `run_multi_agent_peer_review` |

Peer-review sub-roles: **Security**, **Testing**, **Architecture**, plus a **Synthesizer** (`backend/app/adk/peer_review/`).

### Domain agent packages

Python packages under `backend/app/adk/` implement diagnostic agents, correlation, fix planner, risk, code fix, verification, self-correction, regression, peer review, memory, git finalization, and reporting — invoked by services and ADK nodes.

### Sessions

- ADK app name: `THERECODE_GOOGLE_ADK_APP_NAME` (default `therecode`)
- Session service: **in-memory** (`InMemorySessionService`), `session_id = run_id`
- Not durable across process restarts

---

## Technology Stack

### Prerequisites

- Python **3.12+** (`>=3.12,<3.14`)
- [uv](https://docs.astral.sh/uv/)
- Node.js **22+**
- Docker / Docker Compose

### Backend (selected)

| Component | Notes |
|-----------|-------|
| FastAPI | HTTP API |
| Uvicorn | ASGI server |
| Pydantic / pydantic-settings | Config & schemas (`THERECODE_` prefix) |
| PyMongo | MongoDB driver |
| PyJWT + bcrypt | Auth |
| Cryptography | Git credential encryption |
| httpx | Provider HTTP |
| **google-adk ≥ 2.8** | Orchestration (locked 2.8.x) |
| google-genai | Gemini client (transitive) |
| Ruff, Semgrep, Bandit | Python scanner group |
| osv-scanner, gitleaks | Installed as binaries in Docker image |
| pytest + coverage | Test/coverage agents |

Docker Mongo image: **`mongo:7`**. Backend runtime image: Python **3.12** slim + scanner binaries (e.g. osv-scanner **2.5.1**, gitleaks **8.30.1**).

### Frontend (selected)

| Component | Notes |
|-----------|-------|
| React 18 | UI |
| Vite 5 | Dev server & build |
| TypeScript ~5.6 | Typing |
| React Router 6 | Routes |
| TanStack Query 5 | Server state |
| Zustand 5 | Client auth/shell state |
| Tailwind CSS 3 + Flowbite React | Design system |
| Vitest | Unit tests |
| nginx (Alpine) | Production static hosting |

---

## Gemini Integration

theReCode uses the **Gemini Developer API** (AI Studio), not Vertex AI by default.

| Setting | Role |
|---------|------|
| `THERECODE_GOOGLE_API_KEY` | API key ([AI Studio](https://aistudio.google.com/apikey)); also accepted as `GOOGLE_API_KEY` |
| `THERECODE_GOOGLE_GENAI_USE_VERTEXAI` | Must be `false` for API-key mode |
| `THERECODE_GEMINI_MODEL` | Model id (example/env: `gemini-2.5-flash`; code default may differ — set explicitly in env) |

Bootstrap:

- Settings load from `backend/app/.env` via `backend/app/core/config.py`
- `bootstrap_google_genai` exports the key into the process environment for ADK/GenAI clients (`backend/app/google_adk/bootstrap.py`)
- Lifespan startup and `execute` path call configuration guards (`ensure_google_adk_configured`)

LLM usage is concentrated in **fix planner**, **code fix**, and **peer review** specialists; remaining pipeline stages are deterministic service calls for reliability and cost control.

---

## Google ADK Integration

| Item | Detail |
|------|--------|
| Package | `google-adk>=2.8` |
| Orchestrator | `GoogleAdkOrchestrator` |
| Graph builder | `backend/app/google_adk/workflow_builder.py` |
| Nodes | `backend/app/google_adk/pipeline_nodes.py` |
| Specialists | `backend/app/google_adk/agents/specialists.py` |
| Execute API | `POST /api/v1/runs/{id}/execute` |
| Resume path | Post–risk-approval workflow after human `decide` |

Pattern:

1. Build ADK `Workflow` with ordered edges (START → … → finalize).
2. Attach deterministic nodes that call FastAPI service-layer use cases.
3. Attach LlmAgents with typed FunctionTools for specialist steps.
4. Run with session scoped to `run_id`; persist domain state in Mongo + workspace artifacts.

---

## Google Cloud Architecture

Typical deployment (see `deploy.txt`):

```text
┌──────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│ Artifact Registry│────►│ Cloud Run        │────►│ MongoDB Atlas      │
│ (Docker images)  │     │ Backend API      │     │ (mongodb+srv)      │
└──────────────────┘     │ PORT 8000/$PORT  │     └────────────────────┘
         │               │ /workspace (ephemeral)
         │               └──────────────────┘
         │                        ▲
         ▼                        │ HTTPS VITE_API_BASE_URL
┌──────────────────┐     ┌──────────────────┐
│ Cloud Build      │────►│ Cloud Run        │
│ backend/frontend │     │ Frontend nginx   │
└──────────────────┘     │ PORT 8080        │
                         └──────────────────┘
```

**Important Cloud Run constraints**

| Concern | Guidance |
|---------|----------|
| MongoDB | Use **Atlas** (`mongodb+srv://…`). Localhost Mongo in image env will not work from Cloud Run. |
| Atlas network | Allow `0.0.0.0/0` (or known egress) — Cloud Run IPs are dynamic. |
| Frontend | Image is **static-only**. Do **not** proxy to Docker hostname `backend` (compose-only). Bake `VITE_API_BASE_URL=https://<backend>/api/v1` at build time. |
| Frontend port | **8080** (`$PORT`). |
| Workspace | `/workspace` is **ephemeral**; approval decide can persist in Mongo without disk; full pipeline resume still needs durable storage for clone/artifacts. |
| Backend listen | Bind `${PORT:-8000}`; Mongo connect is soft/lazy so PORT can bind before Atlas is reachable. |

Compose vs Cloud Run:

- **Compose** — `nginx.compose.conf.template` proxies `/api` → `backend:8000`
- **Cloud Run frontend** — `nginx.conf.template` serves SPA only

---

## Setup

### 1. Clone and environment

```bash
cp .env.example .env
# Edit: THERECODE_GOOGLE_API_KEY, JWT/encryption secrets, Mongo URI if needed
```

Backend also reads `backend/app/.env` for runtime settings used in Docker/Cloud images.

### 2. Prerequisites check

- Python 3.12+, uv, Node 22+, Docker

### 3. Optional: Docker Compose env

```bash
cp .env.docker.example .env
```

---

## Local Development

### MongoDB only

```bash
docker compose up -d mongodb
```

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000  
- OpenAPI: http://localhost:8000/docs (disabled when `THERECODE_ENVIRONMENT=production`)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173  

Local Vite can proxy `/api` (see `frontend/vite.config.ts`). Prefer `VITE_API_BASE_URL` pointing at your API when not using the proxy.

### Full stack via Docker

```bash
cp .env.docker.example .env
docker compose --profile app up --build
./scripts/validate-docker.sh
```

| Service | Port |
|---------|------|
| Frontend | http://localhost:5173 → container 8080 |
| Backend | http://localhost:8000 |
| MongoDB | localhost:27017 |

### Typical operator flow

1. Register / sign in.
2. **Settings** — save GitHub or GitLab token.
3. **Projects** — create project, open it, link `owner/repo`.
4. Create a run → open run → **Clone repository** (or execute full pipeline).
5. Monitor pipeline / SSE; handle **Approvals**; view **Diff**, **Findings**, **Reports**.

---

## Cloud Deployment

Commands below match `deploy.txt` patterns (substitute your project, region, and image names).

### Artifact Registry

```bash
gcloud artifacts repositories create harpic-cursor-v1 \
  --repository-format=docker \
  --location=europe-north1 \
  --description="theReCode" \
  --immutable-tags \
  --async
```

### Backend image

```bash
gcloud builds submit ./backend \
  --config=./backend/cloudbuild.yaml \
  --substitutions=_IMAGE=REGION-docker.pkg.dev/PROJECT/REPO/backend:tag
```

Configure Cloud Run service env (example):

```bash
gcloud run services update SERVICE \
  --region REGION \
  --set-env-vars "THERECODE_MONGODB_URI=mongodb+srv://USER:PASS@CLUSTER/therecode?retryWrites=true&w=majority,THERECODE_WORKSPACE_ROOT=/workspace,THERECODE_ENVIRONMENT=production,THERECODE_GOOGLE_API_KEY=YOUR_KEY,THERECODE_GOOGLE_GENAI_USE_VERTEXAI=false,THERECODE_GEMINI_MODEL=gemini-2.5-flash"
```

Prefer Secret Manager for keys in production rather than baking `app/.env` long-term.

### Frontend image

Bake the **public** backend API URL:

```bash
gcloud builds submit ./frontend \
  --config=./frontend/cloudbuild.yaml \
  --substitutions=_IMAGE=REGION-docker.pkg.dev/PROJECT/REPO/frontend:tag,_VITE_API_BASE_URL=https://BACKEND_HOST/api/v1
```

```bash
gcloud run deploy FRONTEND_SERVICE \
  --image REGION-docker.pkg.dev/PROJECT/REPO/frontend:tag \
  --region REGION \
  --port 8080 \
  --allow-unauthenticated
```

Update backend `THERECODE_CORS_ORIGINS` to include the frontend Cloud Run origin.

---

## Environment Variables

Prefix: **`THERECODE_`** (pydantic-settings). Frontend uses **`VITE_`**.

### Application

| Variable | Description |
|----------|-------------|
| `THERECODE_APP_NAME` | Display name |
| `THERECODE_ENVIRONMENT` | `development` \| `staging` \| `production` \| `test` |
| `THERECODE_API_PREFIX` | Default `/api/v1` |
| `THERECODE_HOST` / `THERECODE_PORT` | Bind address |
| `THERECODE_CORS_ORIGINS` | Comma-separated allowed origins |
| `THERECODE_WORKSPACE_ROOT` | Clone/artifact root (`../workspace` local, `/workspace` containers) |
| `THERECODE_LOG_LEVEL` | e.g. `INFO` |
| `THERECODE_LOG_FORMAT` | `text` \| `json` |

### MongoDB

| Variable | Description |
|----------|-------------|
| `THERECODE_MONGODB_URI` | Connection string |
| `THERECODE_MONGODB_DATABASE_NAME` | Default `therecode` |
| `THERECODE_MONGODB_SERVER_SELECTION_TIMEOUT_MS` | Default `5000` |
| `THERECODE_MONGODB_CONNECT_TIMEOUT_MS` | Default `5000` |

### Auth & credentials

| Variable | Description |
|----------|-------------|
| `THERECODE_JWT_SECRET_KEY` | JWT signing secret |
| `THERECODE_JWT_ALGORITHM` | Default `HS256` |
| `THERECODE_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Default `60` |
| `THERECODE_CREDENTIALS_ENCRYPTION_KEY` | Git token encryption key |

### Git providers

| Variable | Description |
|----------|-------------|
| `THERECODE_GITHUB_API_BASE_URL` | Default `https://api.github.com` |
| `THERECODE_GITLAB_API_BASE_URL` | Default `https://gitlab.com/api/v4` |

### Gemini / ADK

| Variable | Description |
|----------|-------------|
| `THERECODE_GOOGLE_API_KEY` | Gemini API key |
| `THERECODE_GOOGLE_GENAI_USE_VERTEXAI` | `false` for AI Studio keys |
| `THERECODE_GEMINI_MODEL` | e.g. `gemini-2.5-flash` |
| `THERECODE_GOOGLE_ADK_APP_NAME` | Default `therecode` |

### Frontend

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | API base URL baked at build time; runtime fallback `"/api/v1"` |

### Other settings (code defaults)

| Setting | Typical default |
|---------|-----------------|
| Scanner timeout | `300` seconds |
| Max fix iterations | `3` |

---

## Demo

### Happy-path script (local)

```bash
# Terminal A — Mongo
docker compose up -d mongodb

# Terminal B — API
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# Terminal C — UI
cd frontend && npm install && npm run dev
```

1. Open http://localhost:5173 → **Create account**.
2. **Settings** → add GitHub or GitLab personal access token (repo + PR scopes as required by your provider).
3. **Projects** → create a project → open it → **Link repository** (`owner/repo`).
4. **Create run** → open the run.
5. On Overview, **Clone repository**, then trigger **Execute** (or use step APIs from `/docs`).
6. Watch the pipeline graph and agent timeline (SSE).
7. If status is `AWAITING_APPROVAL`, open **Approvals** and decide.
8. After completion, open **Reports** and the provider PR/MR from git finalization metadata.

### Key API demo calls

```bash
BASE=http://localhost:8000/api/v1

curl -s "$BASE/health"
curl -s -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"TestPass123!","full_name":"Demo"}'
# login → TOKEN
curl -s "$BASE/auth/me" -H "Authorization: Bearer $TOKEN"
```

Use `/docs` interactively for projects, credentials, runs, and `POST /runs/{id}/execute`.

---

## Testing

### Backend

```bash
cd backend
uv sync
uv run pytest
uv run ruff check .
```

- `asyncio_mode = auto`
- Marker `integration` for Mongo-backed tests

### Frontend

```bash
cd frontend
npm test
npm run build
```

### Docker validation

```bash
chmod +x scripts/validate-docker.sh
./scripts/validate-docker.sh
```

Checks compose config, image builds, and health endpoints.

---

## Limitations

1. **Ephemeral Cloud Run workspace** — `/workspace` does not survive instance recycle. Approval decisions can persist in Mongo without disk; durable clones/patches need external volume or re-clone strategies.
2. **In-memory ADK sessions** — orchestration sessions are not shared across replicas or restarts.
3. **Python-first scanners** — diagnostic toolchain targets Python repos; other languages are out of scope for current agents.
4. **Gemini cost/latency** — specialist stages depend on external LLM availability and quotas.
5. **Atlas networking** — misconfigured IP allow lists cause TLS/handshake failures from Cloud Run.
6. **Frontend Cloud Run** — absolute `VITE_API_BASE_URL` required; compose-style nginx upstream `backend` is invalid on Cloud Run.
7. **Production docs** — OpenAPI UI is disabled when `THERECODE_ENVIRONMENT=production`.
8. **Model id drift** — keep `THERECODE_GEMINI_MODEL` explicit; example env and code defaults may differ.
9. **Single-tenant UX** — dashboard is per authenticated user; no multi-org RBAC productization yet.

---

## Future Improvements

Suggested next steps aligned with the current codebase and phase roadmap:

| Area | Improvement |
|------|-------------|
| Storage | Durable workspace (GCS/Filestore) for Cloud Run multi-instance runs |
| ADK | Persistent session/state backend instead of `InMemorySessionService` |
| AuthZ | Organizations, roles, shared projects |
| Scanners | Expand language/ecosystem coverage beyond Python |
| Observability | Structured traces per stage, metrics dashboards |
| Secrets | Secret Manager / Workload Identity for Gemini and Mongo |
| UX | Deeper run compare, bulk project ops, notification webhooks |
| CI | Managed Cloud Build triggers + progressive delivery |
| Vertex | Optional `THERECODE_GOOGLE_GENAI_USE_VERTEXAI=true` path for enterprise |
| Resilience | Stronger resume semantics after approval when workspace is gone |

Historical implementation phases (1–25, 28, 29, 31) are tracked in `README.md`. **Phase 31 (Google ADK 2.0 + Gemini API)** is the current orchestration baseline; **Phase 29 (Cloud Run)** is supported via Dockerfiles and `deploy.txt`.

---

## API quick reference

| Area | Examples |
|------|----------|
| Health | `GET /api/v1/health`, `GET /api/v1/health/ready` |
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Projects | `CRUD /projects`, repositories under `/projects/{id}/repositories` |
| Git credentials | `POST/GET /git/credentials` |
| Runs | `POST /runs`, clone/analyze/diagnostics/agents/findings |
| Pipeline | `correlate`, `plan`, `assess-risk`, `fix`, `verify`, `self-correct`, `regression-tests`, `peer-review` |
| Approvals | `approvals/prepare`, `approvals/{id}/decide`, diffs |
| Orchestration | `POST /runs/{id}/execute`, `GET /runs/{id}/stream`, `GET /runs/{id}/state` |
| Memory / Git / Reports | `memory/capture`, `git/finalize`, `reports/generate` |

Full interactive schema: `/docs` in non-production environments.

---

## License

Proprietary — theReCode
