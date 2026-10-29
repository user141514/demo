# AGENTS.md

## Project Overview

This repository implements the "Meitai AI Business Innovation Agent" demo: a runnable consulting workflow that helps executives move from pre-class intake to AI business innovation planning, report generation, and post-class follow-up.

The current product flow includes:
- pre-class intake import and company assessment
- company profile generation
- business model canvas diagnosis
- breakthrough factor recommendation and selection
- innovation direction expansion and selection
- differentiated competitiveness analysis
- business endgame design
- AI scenario recommendation
- hierarchical case matching with source notes
- 14-section final report generation and quality review
- Markdown, DOCX, printable HTML, and PDF export
- 30-day follow-up task management
- biweekly case push and recalibration
- instructor dashboard, batch comments, and CSV export

## Tech Stack

- Backend: FastAPI + SQLAlchemy + SQLite + optional ChromaDB
- Frontend: Next.js 15.5 + React 18.2 + TypeScript + Tailwind CSS
- AI: OpenAI-compatible API, defaulting to mock mode
- Runtime: Python 3.11+. On this workstation `.venv` reuses `meitai-project` with project-compatible package overrides. Startup discovers `.venv`, then the named Conda environments `meitai-project` / `rag-env`; `MEITAI_PYTHON` explicitly selects another prepared interpreter.

## Ports

- Frontend: `3001` by default. Do not change it to `3000`.
- Backend: `8000` by default.
- Some startup scripts can auto-fallback to another free port.

## Common Commands

```powershell
# One-click local start from repo root
.\start.bat

# Validate interpreter/ports without starting services
pwsh -NoProfile -File scripts/start_local.ps1 -Check

# Local production frontend after npm run build
.\start.bat -ProductionFrontend

# Backend
cd backend
conda activate rag-env
python run.py

# Backend with fixed port
cd backend
conda activate rag-env
python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Checks

Run the narrowest useful checks for the files changed.

```powershell
# Backend tests
cd backend
python -m pytest tests/ -v

# Full-chain backend test
cd backend
python -m pytest tests/test_e2e_full_chain.py -v -s

# Frontend checks
cd frontend
npm run typecheck
npm run test
npm run build
```

## Key Directories

```text
backend/app/api/routes/  API routes
backend/app/core/        config, LLM client, optional mykey.py loading
backend/app/db/          database session and setup
backend/app/exporters/   report exporters
backend/app/models/      SQLAlchemy models
backend/app/prompts/     LLM prompts
backend/app/rag/         optional RAG retrieval
backend/app/schemas/     Pydantic schemas
backend/app/services/    business logic
backend/data/            local SQLite and Chroma data, gitignored
backend/exports/         generated exports, gitignored
backend/tests/           backend test suite

frontend/src/app/        Next.js pages and routes
frontend/src/components/ React components and component tests
frontend/src/lib/        API client, shared types, utilities

knowledge/raw/           source YAML/Markdown knowledge base
scripts/                 startup and utility scripts
docs/                    architecture, status, and design docs
```

## Important API Areas

- Core assessment flow: `/api/assessments`
- Profile, canvas, breakthrough, directions, competitiveness, endgame, scenarios, cases, report context: under `/api/assessments/{id}/...`
- Reports and exports: `/api/reports/{report_id}/...`
- Follow-up, push, recalibration: under `/api/assessments/{id}/...`
- Instructor workflows: `/api/instructor/...`
- RAG routes use `/rag`, not `/api/rag`

Check `README.md` and `使用方法.md` for the full current endpoint list before adding or changing API behavior.

## Environment Rules

- Local launcher binds to `127.0.0.1`, keeps ports 3001/8000 fixed, and does not start ngrok. AI follows configured `LLM_MODE` / `LLM_REPORT_ENABLED`; `-Live` or `-Mock` explicitly override AI mode. Payments stay mocked. Logs are in gitignored `.local/`. A busy port is an error; never kill unrelated listeners.
- Prefer `.venv\Scripts\python.exe` for this checkout's backend commands. Do not change the shared `meitai-project` environment to run this checkout.
- The browser uses same-origin `/api`; `API_PROXY_TARGET` configures the Next.js server-side destination and is baked into production rewrites during build. Docker uses `http://backend:8000`.
- Development generates a persistent random JWT secret in `backend/data/.jwt-secret` (or `JWT_SECRET_FILE`). Non-development environments require an explicit new `JWT_SECRET_KEY` of at least 32 characters. Never log either secret.
- No implicit/default instructor password is supported. Run `.venv\Scripts\python.exe scripts/create_instructor.py --email teacher` interactively to create an instructor; resetting an existing instructor requires `--reset-password`. Existing old demo passwords are rejected. The tool does not promote existing student accounts.
- `/api/admin/llm-config` requires an authenticated instructor for both GET and PATCH.

- Default mode is mock: `LLM_MODE="mock"`.
- This workstation's ignored `.env` selects live DeepSeek via `LLM_CONFIG_FILE=data/llm_config.json`; the original credential stays in that ignored JSON. Only `api_key`, `base_url`, and `model` are imported from an explicitly selected JSON; its `mode` cannot implicitly enable paid calls. Process environment > .env > mykey.py > selected credential JSON > defaults. Never print or copy credential values.
- DeepSeek thinking mode is controlled by `DEEPSEEK_THINKING_ENABLED`; current local interactive testing sets it to false. The option is sent only to the official DeepSeek host. Report preview must choose “LLM 增强（智能）”; explicitly requested template reports remain templates.
- Ordinary backend pytest runs force offline AI with dummy credentials, an isolated in-memory global database, mock payments, disabled SMTP and disabled RAG before importing application settings. `RUN_LIVE_LLM_TESTS=true` opts into the existing paid live-report test only; database/payment/SMTP/RAG isolation remains enabled. Test eligibility checks the resolved credential source rather than requiring a duplicated key in the environment.
- Live mode uses `LLM_MODE="live"` with `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL`.
- `.env` values override `backend/app/core/mykey.py`; both override config defaults.
- `mykey.py` is local secret configuration and must not be committed.
- Keep `RAG_ENABLED=false` by default.
- Keep `LLM_REPORT_ENABLED=false` by default unless the user explicitly wants live LLM reports.

## Report Rules

- Preserve template report generation.
- Preserve LLM-to-template fallback behavior.
- Template reports are the deterministic baseline and should work without an API key.
- The final report structure currently has 14 sections; do not remove sections casually.
- Export paths include Markdown, DOCX, printable HTML, and PDF.

## Constraints

- Do not commit `.env`, `backend/app/core/mykey.py`, SQLite databases, Chroma stores, generated exports, `.next`, `node_modules`, or test caches.
- Do not refactor the project structure unless the user explicitly asks.
- Do not introduce a new state management library or UI framework without a clear request.
- Prefer existing service, schema, route, and component patterns.
- Keep RAG optional and disabled by default.
- Keep frontend port conventions intact.

## Before Finishing

Summarize:
- files changed
- behavior or documentation updated
- commands/checks run
- anything not verified
