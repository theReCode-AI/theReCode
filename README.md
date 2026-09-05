![theReCode](./DOCS/resources/theReCode-logo-without-name.png)

<h1 style="text-align:center; font-size:55px;">theReCode</h1>

**Autonomous AI software-engineering platform for Python repositories on GitHub and GitLab.**


theReCode analyzes real repositories, runs industry-standard diagnostics, plans and applies fixes with Gemini, verifies changes, performs multi-agent peer review, captures institutional memory, and opens pull requests behaving like an autonomous software engineer, not a chatbot.

| Item | Value |
|------|-------|
| Product | theReCode |
| Backend version | `0.1.0` |
| API base | `/api/v1` |
| Orchestration | Google ADK 2.x + Gemini API |

---

## Problem

Software teams spend disproportionate time on work that is **repeatable but high-stakes**:

- **Security and quality debt** — lint violations, SAST findings, dependency CVEs, leaked secrets, failing tests, and coverage gaps pile up faster than teams can triage them.
- **Tool fragmentation** — Ruff, Semgrep, Bandit, OSV, Gitleaks, and pytest each produce separate reports. Engineers manually correlate noise into actionable issues.
- **Slow fix loops** — patch → test → rework cycles burn senior engineer hours. Knowledge from past fixes is rarely captured for the next run.
- **Chatbot limits** — generic LLM assistants can suggest snippets, but they do not **clone a repo, run scanners, apply scoped patches, verify, get human approval, push a branch, and open a PR** with a full audit trail.

**Hackathon insight:** Teams do not need another chat window. They need an **autonomous agent platform** that owns the end-to-end workflow on real Git repositories with policy gates, human oversight, and reproducible artifacts.

---

## Solution

theReCode is a **full-stack monorepo platform** that runs a deterministic multi-stage pipeline over a cloned repository, using **Google ADK 2.0 Workflows** for orchestration and **Gemini** for specialist reasoning where it adds the most value (planning, coding, peer review).

```
Register → Link GitHub/GitLab repo → Save encrypted Git token
    → Create project & run → Clone into workspace
    → Execute autonomous pipeline (ADK Workflow)
    → Human approvals when required
    → Push branch fix/<run_id> + open PR/MR
    → Generate markdown/PDF report
```

**What makes it different from a chatbot**

| Chatbot | theReCode |
|---------|-----------|
| Suggests code in isolation | Operates on a cloned repository in a managed workspace |
| No verification | Runs pytest, scanners, regression tests after every fix |
| No governance | Risk engine + human approval gates before risky changes |
| No delivery | Creates real Git branches and pull requests |
| No memory | Captures project memories for future planning |



**Persistence**

- **MongoDB** — users, projects, runs, findings, plans, approvals, memories, git operations, chat history
- **Filesystem workspace** — clone trees, patch diffs, baseline JSON, markdown/PDF reports under

---

## Architecture
![](./DOCS/resources/theReCode-Architecture-v1.png)
### High-level system diagram
![](./DOCS/resources/agent-architecture.png)
<!-- ![project-architecture](./DOCS/resources/theReCode-project-architecture.png) -->


---

### Diagnostic agents

| Agent | Scanner / tool |
|-------|----------------|
| `code_quality_agent` | Ruff |
| `semgrep_agent` | Semgrep |
| `security_agent` | Bandit |
| `dependency_agent` | OSV Scanner |
| `secret_check_agent` | Gitleaks |
| `test_agent` | pytest |
| `coverage_agent` | coverage.py |

### Run lifecycle statuses

`CREATED` → `CLONING` → `ANALYZING` → `DIAGNOSING` → `PLANNING` → `AWAITING_APPROVAL` → `FIXING` → `VERIFYING` → `SELF_CORRECTING` → `PEER_REVIEW` → `FINAL_REVIEW` → `PUSHING` → `REPORTING` → `COMPLETED` | `FAILED` | `CANCELLED`


# --------------- DEVELOPER GUIDE --------------------

# DEVELOPER GUIDE


## Prerequisites

- Python 3.12+, uv, Node.js 22+, Docker

## Setup

### 1. Clone

```bash
git clone https://github.com/theReCode-AI/theReCode.git -b main
cd theReCode/
```


### 2. Configure backend
```bash
cd backend
uv sync
source .venv/bin/activate
```
then

```bash
cd app #/theReCode/backend/app
cp .env.example .env
```

Edit `.env`:

- `THERECODE_GOOGLE_API_KEY` — required for pipeline and chat
- `THERECODE_GEMINI_MODEL` — `<your-gemini-model>`, default `gemini-3.6-flash` 
- `THERECODE_JWT_SECRET_KEY` — change from dev default in production
- `THERECODE_CREDENTIALS_ENCRYPTION_KEY` — 32+ char key for Git token encryption
- `THERECODE_MONGODB_URI` — ` mongodb://<username>:<password>@localhost:27017/therecode?authSource=admin` or `mongodb+srv://username:password@cluster0.example.mongodb.net`

Backend also reads `backend/app/.env` (used in Docker/Cloud images).

run the application

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Open the following links in your browser:
- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs




### 3. Configure Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

Set `VITE_API_BASE_URL=http://localhost:8000/api/v1` in `.env` or rely on Vite proxy.

### Full stack via Docker

```bash
cp .env.docker.example .env
docker compose --profile app up --build
./scripts/validate-docker.sh
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| MongoDB | localhost:27017 |

---


---

## Environment Variables

Prefix: **`THERECODE_`** (backend). Frontend: **`VITE_`**.

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

### Auth & credentials

| Variable | Description |
|----------|-------------|
| `THERECODE_JWT_SECRET_KEY` | JWT signing secret |
| `THERECODE_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Default `60` |
| `THERECODE_CREDENTIALS_ENCRYPTION_KEY` | Git token encryption key |

### Gemini / ADK

| Variable | Description |
|----------|-------------|
| `THERECODE_GOOGLE_API_KEY` | Gemini API key (**required**) |
| `THERECODE_GOOGLE_GENAI_USE_VERTEXAI` | `false` for AI Studio |
| `THERECODE_GEMINI_MODEL` | e.g. `gemini-2.5-flash` |
| `THERECODE_GOOGLE_ADK_APP_NAME` | Default `therecode` |

### Frontend

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | API base URL (baked at build time for Cloud Run) |

---


# --------------- FILE STRUCTURE --------------------
### Frontend structure

```text
frontend/src/
  api/           HTTP + SSE clients
  pages/         Route-level screens
  components/    Layout, runs, projects, common UI
  stores/        Zustand (auth, app shell)
  routes/        React Router tree
  types/         Shared TypeScript models
```


### Execute data flow

1. User authenticates (JWT).
2. Creates project, links repository, stores encrypted Git credential.
3. Creates run → workspace paths allocated under `THERECODE_WORKSPACE_ROOT`.
4. `POST .../execute` → ADK `Runner` walks the workflow graph.
5. Deterministic `@node` stages write Mongo + disk artifacts; Gemini specialists invoke typed `FunctionTool`s.
6. UI subscribes via SSE (`snapshot`, `run_update`, `state_update`, `agent_event`, `heartbeat`, `complete`).
7. Operator reviews approvals, pushes to GitHub from run overview, reads report and PR link.

---



## Agent Architecture

theReCode is a **multi-agent platform**, not a single monolithic LLM call. Orchestration combines **deterministic pipeline nodes** with **Gemini specialist agents** .

### Orchestration stages

Defined in `backend/app/adk/workflows/stages.py`:

`initialization` → `cloning` → `project_intelligence` → `diagnostics` → `issue_correlation` → `fix_planning` → `risk_assessment` → `code_fixing` → `verification` → `self_correction` → `regression_testing` → `peer_review` → `human_approval` → `memory` → `git_finalization` → `reporting` → `finalization`

### Google ADK workflows

Built in `backend/app/google_adk/workflow_builder.py`:

| Workflow | Purpose |
|----------|---------|
| `therecode_autonomous_run` | Full pipeline from initialize through finalize |
| `therecode_post_risk_approval_run` | Resume after risk-gate human approval (code fix onward) |

### Stage types

| Kind | Examples | Implementation |
|------|----------|----------------|
| **Deterministic nodes** | Clone, diagnostics, correlate, risk, verify, self-correct, regression, memory, git, report | `@node` functions in `pipeline_nodes.py` → service container |
| **LLM specialists** | Fix planning, code fix, peer review | Gemini `LlmAgent` + `FunctionTool` in `specialists.py` |

### Gemini specialist agents

| Agent | Tool | Role |
|-------|------|------|
| `fix_planner_agent` | `create_fix_plans` | Turn correlated issues into scoped patch plans |
| `code_fix_agent` | `apply_autonomous_fixes` | Apply approved/eligible fixes in workspace |
| `peer_review_agent` | `run_multi_agent_peer_review` | Coordinate Security, Testing, Architecture review |

Peer-review sub-roles live under `backend/app/adk/peer_review/` with a **Synthesizer** that produces a final verdict.

### Domain agent packages

Python packages under `backend/app/adk/` implement diagnostics, correlation, fix planner, risk, code fix, verification, self-correction, regression, peer review, memory, git finalization, and reporting — invoked by services and ADK nodes.

### Human-in-the-loop

- **Risk gate** — high-risk patch plans pause the pipeline (`AWAITING_APPROVAL`) until a human decides.
- **Final review** — peer review may request changes; approval cards include diff artifacts.
- **Resume** — `POST /runs/{id}/execute` with `resume_after_approval: true` continues via `therecode_post_risk_approval_run`.

### Sessions

- ADK app name: `THERECODE_GOOGLE_ADK_APP_NAME` (default `therecode`)
- Session service: **in-memory** (`InMemorySessionService`), `session_id = run_id`
- Domain state is durable in MongoDB + workspace; ADK session is orchestration-scoped only

---

## Features

### Operator dashboard

| Route | Capability |
|-------|------------|
| `/login`, `/register` | JWT authentication |
| `/dashboard` | Project/run summary metrics, recent activity |
| `/projects` | Create/list projects; cards show repo count, run count, latest status |
| `/projects/:projectId` | Link repos, start runs, view linked repositories and run history |
| `/runs/:runId` | Run overview — pipeline graph, agent timeline, clone/execute/**git push** |
| `/runs/:runId/findings` | Normalized findings from all diagnostic agents |
| `/runs/:runId/diff` | Fix-attempt diffs |
| `/runs/:runId/approvals` | Human-in-the-loop cards (`approve` / `reject` / `request_changes`) |
| `/runs/:runId/reports` | Generated markdown/PDF run reports |
| `/runs/:runId/chat` | Gemini-powered Q&A about the run (findings, fixes, report context) |
| `/chat` | Select project → run → ask questions |
| `/settings` | Account + encrypted Git credentials (GitHub/GitLab PAT) |

Live progress uses **Server-Sent Events** (`GET /api/v1/runs/{id}/stream`).

### Platform capabilities

- **Authentication** — register, login, JWT bearer tokens
- **Projects & repositories** — link GitHub/GitLab repos, validate access, clone
- **Encrypted Git credentials** — provider tokens encrypted at rest
- **Workspace manager** — isolated per-run directories (`baseline/`, `patches/`, `reports/`)
- **Project intelligence** — structural analysis of the cloned codebase
- **Seven diagnostic agents** — wrap industry scanners (see table below)
- **Issue correlation** — group related findings into actionable issue groups
- **Fix planning** — Gemini fix planner produces scoped patch plans
- **Risk policy engine** — autonomous vs approval-required decisions
- **Code fix agent** — Gemini applies patches with scope enforcement
- **Verification engine** — re-run tests and scanners on applied fixes
- **Self-correction loop** — retry failed verifications (configurable max iterations)
- **Regression tests** — generated/executed after verification passes
- **Multi-agent peer review** — Security, Testing, Architecture reviewers + synthesizer
- **Human approvals** — risk gate and final review with diff viewer
- **Institutional memory** — `project`, `decision`, `failure`, `success_strategy` types
- **Git finalization** — branch `fix/<run_id>`, commit, push, open PR/MR (pipeline + manual UI button)
- **Run reports** — markdown + PDF with health score and PR metadata
- **Run chat** — contextual Gemini chat grounded in run artifacts
- **Dark/light theme** — Flowbite design system


## Technology Stack

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ (`>=3.12,<3.14`) |
| uv | [Astral uv](https://docs.astral.sh/uv/) |
| Node.js | 22+ |
| Docker / Docker Compose | For MongoDB and full-stack deploy |

### Backend

| Component | Role |
|-----------|------|
| FastAPI | HTTP API |
| Uvicorn | ASGI server |
| Pydantic / pydantic-settings | Config & schemas (`THERECODE_` prefix) |
| PyMongo | MongoDB driver |
| PyJWT + bcrypt | Authentication |
| Cryptography | Git credential encryption |
| httpx | Git provider HTTP |
| **google-adk ≥ 2.8** | Workflow orchestration |
| google-genai | Gemini client |
| Ruff, Semgrep, Bandit | Python scanners |
| osv-scanner, gitleaks | Security binaries (Docker image) |
| pytest + coverage | Test/coverage agents |

Docker: **`mongo:7`** for database; backend image is Python **3.12** slim with scanner binaries.

### Frontend

| Component | Role |
|-----------|------|
| React 18 | UI framework |
| Vite 5 | Dev server & production build |
| TypeScript ~5.6 | Type safety |
| React Router 6 | Client routing |
| TanStack Query 5 | Server state / caching |
| Zustand 5 | Auth and shell state |
| Tailwind CSS 3 + Flowbite React | Design system |
| Vitest | Unit tests |
| nginx (Alpine) | Production static hosting |

---

## Gemini Integration

theReCode uses the **Gemini Developer API** (Google AI Studio) by default — not Vertex AI.

| Setting | Purpose |
|---------|---------|
| `THERECODE_GOOGLE_API_KEY` | API key from [AI Studio](https://aistudio.google.com/apikey) |
| `THERECODE_GOOGLE_GENAI_USE_VERTEXAI` | `false` for API-key mode |
| `THERECODE_GEMINI_MODEL` | Model id (e.g. `gemini-2.5-flash`) |

### Where Gemini is used

| Use case | Implementation |
|----------|----------------|
| Fix planning | ADK `fix_planner_agent` |
| Code fixing | ADK `code_fix_agent` |
| Peer review | ADK `peer_review_agent` |
| Run chat | `GeminiChatClient` + `ChatService` (direct `google-genai`, AFC disabled for reliability) |

### Bootstrap

- Settings load from `backend/app/.env` via `backend/app/core/config.py`
- `bootstrap_google_genai` exports the API key for ADK/GenAI clients
- Lifespan startup and execute path call `ensure_google_adk_configured`

### Design principle

**Deterministic stages for reliability; Gemini for reasoning.** Clone, scan, verify, git push, and report generation are service calls — not LLM prompts — so the pipeline is predictable, testable, and cost-controlled.

---

## Google ADK Integration

| Item | Detail |
|------|--------|
| Package | `google-adk>=2.8` |
| Orchestrator | `GoogleAdkOrchestrator` (`backend/app/google_adk/orchestrator.py`) |
| Workflow builder | `backend/app/google_adk/workflow_builder.py` |
| Pipeline nodes | `backend/app/google_adk/nodes/pipeline_nodes.py` |
| Specialists | `backend/app/google_adk/agents/specialists.py` |
| Execute API | `POST /api/v1/runs/{id}/execute` |
| Resume API | Same endpoint with `{ "resume_after_approval": true }` |

### Integration pattern

```text
1. Build ADK Workflow with ordered edges (START → … → finalize_run)
2. Register deterministic @node functions that call FastAPI services
3. Attach LlmAgents with typed FunctionTools for specialist steps
4. Run via ADK Runner with session_id = run_id
5. Persist all domain state in MongoDB + workspace artifacts
6. Stream agent events to UI over SSE
```

### Why ADK for a hackathon project

- **First-class workflow graphs** — explicit stage ordering, not ad-hoc prompt chains
- **Tool calling** — specialists invoke backend services through typed tools
- **Pause/resume** — risk approval gate maps cleanly to a second workflow graph
- **Google ecosystem alignment** — pairs naturally with Gemini API and Cloud Run deployment

---

## Google Cloud Architecture

Typical production layout (see `deploy.txt`):

```text
┌──────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│ Artifact Registry│────►│ Cloud Run        │────►│ MongoDB Atlas      │
│ (Docker images)  │     │ Backend API      │     │ (mongodb+srv)      │
└──────────────────┘     │ PORT 8000/$PORT  │     └────────────────────┘
         │               │ /workspace (ephemeral)
         │               └──────────────────┘
         │                        ▲
         ▼                        │ HTTPS (VITE_API_BASE_URL)
┌──────────────────┐     ┌──────────────────┐
│ Cloud Build      │────►│ Cloud Run        │
│ backend/frontend │     │ Frontend nginx   │
└──────────────────┘     │ PORT 8080        │
                         └──────────────────┘
                                  │
                                  ▼
                         Gemini API (AI Studio key)
```

### Cloud Run constraints

| Concern | Guidance |
|---------|----------|
| MongoDB | Use **Atlas** (`mongodb+srv://…`). In-container Mongo will not work from Cloud Run. |
| Atlas network | Allow `0.0.0.0/0` or known egress — Cloud Run IPs are dynamic. |
| Frontend | Static SPA only on Cloud Run. Bake `VITE_API_BASE_URL=https://<backend>/api/v1` at **build time**. |
| Frontend port | **8080** (`$PORT`). |
| Workspace | `/workspace` is **ephemeral** — clones do not survive instance recycle. |
| Secrets | Use Secret Manager for `THERECODE_GOOGLE_API_KEY`, JWT secret, encryption key in production. |
| CORS | Set `THERECODE_CORS_ORIGINS` to the frontend Cloud Run URL. |

### Compose vs Cloud Run

| Environment | API routing |
|-------------|-------------|
| Docker Compose | nginx proxies `/api` → `backend:8000` |
| Cloud Run frontend | Absolute `VITE_API_BASE_URL` to backend service URL |

---

# --------------- finalize ---------------------------
## Future Improvements

| Area | Improvement |
|------|-------------|
| **Storage** | GCS or Filestore-backed workspace for durable Cloud Run clones |
| **ADK** | Persistent session backend (Redis/Firestore) for multi-replica orchestration |
| **AuthZ** | Organizations, roles, shared projects, audit log |
| **Scanners** | JavaScript, Go, Terraform language packs |
| **Observability** | OpenTelemetry traces per pipeline stage, Cloud Monitoring dashboards |
| **Vertex AI** | Optional `THERECODE_GOOGLE_GENAI_USE_VERTEXAI=true` for enterprise |
| **CI integration** | GitHub Actions trigger on PR; status checks back to provider |
| **Notifications** | Slack/email webhooks on approval required or PR created |
| **Cost controls** | Per-run token budgets, model routing (flash vs pro) |
| **Cost Monitoring** | Cost calculation per run/project |


---

## License

Proprietary — MIT license
