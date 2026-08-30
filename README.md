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

**Phase 31 complete — orchestration runs on Google ADK 2.0 with Gemini API (not Vertex AI).**

### Phase 31 Google ADK 2.0

- Package: `google-adk>=2.8` in `backend/pyproject.toml`
- Config in `backend/app/.env`:
  - `THERECODE_GOOGLE_API_KEY` — Gemini API key from [AI Studio](https://aistudio.google.com/apikey)
  - `THERECODE_GOOGLE_GENAI_USE_VERTEXAI=false`
  - `THERECODE_GEMINI_MODEL=gemini-2.5-flash`
- `POST /api/v1/runs/{id}/execute` uses `GoogleAdkOrchestrator` + ADK `Workflow` graph
- LLM agents: fix planner, code fix, peer review (Gemini + typed `FunctionTool`s)
- Deterministic stages: clone, intelligence, diagnostics, correlate, risk, verify, etc.

### Phase 28 Docker

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| `mongodb` | `mongo:7` | 27017 | Persistent volume |
| `backend` | `backend/Dockerfile` | 8000 | git + curl, `/workspace` mount |
| `frontend` | `frontend/Dockerfile` | 5173→8080 | Cloud Run: static SPA on `$PORT`; bake `VITE_API_BASE_URL` to backend. Compose: nginx proxies `/api` → backend |

Files: `.env.docker.example`, `scripts/validate-docker.sh`, `.dockerignore` per service

### Phase 25 API

- `GET /api/v1/runs/{id}/fix-attempts/{fix_attempt_id}/diff` — read fix attempt diff artifact
- `GET /api/v1/runs/{id}/approvals/{approval_id}/diff` — read approval diff artifact
- `POST /api/v1/runs/{id}/approvals/prepare` — prepare approval cards (existing)
- `POST /api/v1/runs/{id}/approvals/{approval_id}/decide` — submit approve/reject/request_changes (existing)

### Phase 24 API

- `GET /api/v1/runs/{id}/stream` — Server-Sent Events stream for live run progress

SSE events: `snapshot`, `run_update`, `state_update`, `agent_event`, `heartbeat`, `complete`

### Phase 23 Frontend

Pages:

- `/login`, `/register` — authentication
- `/dashboard` — recent runs and summary metrics
- `/projects`, `/projects/:id` — project and repository management, run creation
- `/runs/:id` — primary autonomous run dashboard (pipeline, timeline, summary)
- `/runs/:id/findings`, `/diff`, `/approvals`, `/reports` — run sub-views
- `/settings` — account overview

Stack: React 18, Vite, TypeScript, TanStack Query, Zustand, React Router

### Phase 22 API

- `POST /api/v1/runs/{id}/reports/generate` — generate markdown and PDF run reports
- `GET /api/v1/runs/{id}/reports` — get the persisted run report metadata

Artifacts: `reports/run_report.md`, `reports/run_report.pdf`  
Summary artifact: `baseline/run_report.json`  
MongoDB collection: `reports`  
Run status: `COMPLETED` after successful report generation

### Phase 21 API

- `POST /api/v1/runs/{id}/git/finalize` — create agent branch, commit, push, and open PR/MR
- `GET /api/v1/runs/{id}/git/operations` — list git finalization operations
- `GET /api/v1/runs/{id}/git/operations/{id}` — get a single git operation

Artifact: `baseline/git_operations.json`  
Per-operation artifacts: `baseline/git/<git_operation_id>/operation.json`  
MongoDB collection: `git_operations`  
Branch pattern: `fix/<run_id>`  
Run status: `REPORTING` on success; `FAILED` on git errors

### Phase 20 API

- `POST /api/v1/runs/{id}/memory/capture` — extract and persist memories from run artifacts
- `GET /api/v1/projects/{id}/memories` — list project memories
- `GET /api/v1/projects/{id}/memories/{id}` — get a single memory entry

Artifact: `baseline/project_memories.json`  
Per-memory artifacts: `baseline/memory/<memory_id>/memory.json`  
MongoDB collection: `memories`  
Memory types: `project`, `decision`, `failure`, `success_strategy`  
Fix planner integration: relevant memories are injected into patch plan rationale before planning

### Phase 19 API

- `POST /api/v1/runs/{id}/approvals/prepare` — build approval cards when a run is awaiting approval
- `GET /api/v1/runs/{id}/approvals` — list approval requests
- `GET /api/v1/runs/{id}/approvals/{id}` — get a single approval card
- `POST /api/v1/runs/{id}/approvals/{id}/decide` — submit `approve`, `reject`, or `request_changes` with optional feedback

Artifact: `baseline/approvals.json`  
Per-approval artifacts: `baseline/approvals/<approval_id>/approval.json`  
Human feedback artifact: `baseline/human_feedback.json`  
MongoDB collection: `approvals`  
Run status: `FIXING` or `FINAL_REVIEW` on approve; `PLANNING` on request changes; `FAILED` on reject

### Phase 18 API

- `POST /api/v1/runs/{id}/peer-review` — run multi-agent peer review for completed regression tests
- `GET /api/v1/runs/{id}/peer-reviews` — list peer review results
- `GET /api/v1/runs/{id}/peer-reviews/{id}` — get a single peer review result

Artifact: `baseline/peer_review_results.json`  
Per-plan artifacts: `baseline/peer_review/<patch_plan_id>/result.json`  
MongoDB collection: `reviews`  
Run status: `FINAL_REVIEW` when all reviewers approve; `AWAITING_APPROVAL` when changes are requested; `FAILED` when rejected

### Phase 17 API

- `POST /api/v1/runs/{id}/regression-tests` — generate and run regression tests for passed verifications
- `GET /api/v1/runs/{id}/regression-tests` — list regression test results
- `GET /api/v1/runs/{id}/regression-tests/{id}` — get a single regression test result

Artifact: `baseline/regression_test_results.json`  
Per-plan artifacts: `baseline/regression/<patch_plan_id>/result.json`  
MongoDB collection: `regression_test_results`  
Run status: `VERIFYING` when regression passes or is skipped; `FAILED` when regression fails

### Phase 16 API

- `POST /api/v1/runs/{id}/self-correct` — retry fixes for failed verifications
- `GET /api/v1/runs/{id}/self-correction-cycles` — list self-correction cycles
- `GET /api/v1/runs/{id}/self-correction-cycles/{id}` — get a single cycle

Artifact: `baseline/self_correction_cycles.json`  
Per-cycle artifacts: `baseline/self_correction/<cycle_id>/cycle.json`  
MongoDB collection: `self_correction_cycles`  
Run status: `VERIFYING` when retry passes; `SELF_CORRECTING` if still failing; `AWAITING_APPROVAL` when iterations are exhausted

### Phase 15 API

- `POST /api/v1/runs/{id}/verify` — verify applied fixes via tests and scanners
- `GET /api/v1/runs/{id}/verification-results` — list verification results
- `GET /api/v1/runs/{id}/verification-results/{id}` — get a single verification result

Artifact: `baseline/verification_results.json`  
Per-attempt artifacts: `baseline/verification/<fix_attempt_id>/result.json`  
MongoDB collection: `verification_results`  
Run status: `VERIFYING` when all checks pass; `SELF_CORRECTING` when verification fails

### Phase 14 API

- `POST /api/v1/runs/{id}/fix` — apply autonomous fixes for eligible patch plans
- `GET /api/v1/runs/{id}/fix-attempts` — list fix attempts
- `GET /api/v1/runs/{id}/fix-attempts/{id}` — get a single fix attempt

Artifact: `baseline/fix_attempts.json`  
Patch artifacts: `patches/<plan_id>/pre-patch/`, `changes.diff`  
MongoDB collection: `fix_attempts`  
Run status: `FIXING` during and after autonomous fix application

### Phase 13 API

- `POST /api/v1/runs/{id}/assess-risk` — assess patch-plan risk via policy engine
- `GET /api/v1/runs/{id}/risk-decisions` — list risk decisions
- `GET /api/v1/runs/{id}/risk-decisions/{id}` — get a single risk decision

Artifact: `baseline/risk_decisions.json`  
MongoDB collection: `risk_decisions`  
Run status: `AWAITING_APPROVAL` when any plan requires approval; stays `PLANNING` if all plans are autonomous

## License

Proprietary — theReCode
