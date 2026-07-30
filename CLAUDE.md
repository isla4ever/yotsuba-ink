# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Yotsuba Ink — an open-source long-form fiction production workbench. A monorepo with a React frontend (`apps/web/`), a Python FastAPI backend (`src/novel_workflow/`), version-controlled runtime resources (`runtime/novel_workflow/`), regression tests (`tests/`), and architecture docs (`docs/`).

## Commands

```bash
# Backend API server (port 8787)
.venv/bin/python -m uvicorn novel_workflow.api.app:app --host 127.0.0.1 --port 8787 --reload

# Frontend dev server (port 5173)
cd apps/web && npm run dev

# Backend tests (pytest; pythonpath=src is configured in pyproject.toml)
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest tests/test_workflow_runner.py -q          # single file
.venv/bin/python -m pytest tests/test_workflow_runner.py::test_name -q  # single test

# Frontend tests (vitest; *.test.ts(x) files live next to sources)
cd apps/web && npm run test
cd apps/web && npm run test -- src/features/pipeline/state/runReducer.test.ts  # single file

# Frontend type-check + production build (the standard pre-PR check)
cd apps/web && npm run build

# CSS audit
cd apps/web && npm run audit:css
```

Python is 3.12+, virtualenv at `.venv/`. Dev deps: `pip install -e ".[dev]"` (or uv; `uv.lock` is present).

## Architecture

### Request flow

1. User configures a workflow in the planning workbench; frontend saves workflow/stage config via the API.
2. On run start, the backend reads workflow + prompts + provider config + runtime storage.
3. `workflows/runner.py` (the runner facade) orchestrates stages and emits SSE events.
4. Frontend state (`apps/web/src/features/pipeline/state/`) merges SSE events into run state and drives stage pages.
5. During execution the backend writes back to the Story Bible/Wiki, quality reports, and run artifacts.

Product invariants: the Story Brief approval is the only default human gate; chapter text generation must not start before the full chapter detail outline is complete; the Wiki/Story Bible is a writable continuity fact system; quality gates make pass/revise/block decisions.

### Backend (`src/novel_workflow/`)

`api/` is a **thin adapter layer only** (`app.py`, `bootstrap.py`, `dependencies.py`, `sse.py`, `run.py`, `routes/`). Business logic never goes in route files. Domain packages:

- `workflows/` — workflow schema, default templates, compiler, runner facade
- `orchestration/` — stage transitions and execution (chapter pipeline, artifacts, revision, cover, export)
- `quality/` — quality gate engine
- `memory/` — Wiki / continuity writeback
- `knowledge/` — document ingestion, chunking, storage, retrieval
- `references/` — external reference retrieval and injection (reference merging belongs here)
- `providers/` — model adapters and registry
- `usage/` — token and usage accounting
- `storage/` — JSON-based persistence
- `output_contracts/`, `stages/` — stage output contracts

### Frontend (`apps/web/src/features/pipeline/`)

One directory taxonomy only — do not add parallel buckets like `components/`, `panels/`, `dialogs/`, `screens/`:

- `layout/` — header, global shell
- `planning/` — planning/config-mode workbench
- `brief/` — Story Brief and reference intake
- `running/` — run-mode workbench and diagnostics
- `settings/` — settings dialogs, provider config
- `services/` — API requests and event streams (IO only)
- `state/` — app state, persistence, SSE event merging (React-only)
- `contracts/` — workflow and event contracts
- `lib/` — pure functions and formatting helpers

Keep screens thin, services IO-only, state React-only, lib pure. Entry points: `apps/web/src/App.tsx`, `apps/web/src/features/pipeline/state/useNovelWorkflowApp.ts`.

### Runtime (`runtime/novel_workflow/`)

Version-controlled defaults: `workflows/`, `prompts/`, `providers/`, `examples/`. Generated local state (**not** source, don't commit): `runs/`, `wiki/`, `references/`, `knowledge/`, and the `*.sqlite3` provider profile/secret stores (all gitignored).

## Engineering rules

- Before changing stage UI, model outputs, SSE events, runtime panels, or route-per-stage behavior, read `docs/architecture/stage-artifact-contract.md`. Define the stage artifact, user decision, writeback target, and next-stage dependency first — never design stage pages by filling empty space.
- When adding a new pipeline stage, follow `docs/development/how-to-add-stage.md`.
- File size guardrails: normal files ~200–250 lines, heavy modules up to ~300; split by responsibility before growing past that.
- Naming: React components `PascalCase.tsx`, hooks `useXxx.ts`, TS IO adapters `xxxApi.ts` / `xxxStream.ts`, Python modules `snake_case.py`. One file, one primary responsibility; extract pure helpers out of component files.
- Prefer existing repo boundaries and local helpers over new abstractions or dependencies; prefer structured contracts over stringly-typed payloads.
- Preserve API paths, product semantics, and demo/mock fallback behavior (flows must keep working when real providers are unavailable) unless the task explicitly changes them.
- Full guardrails: `AGENTS.md`, `docs/engineering/ponytail.md`. Architecture starting points: `docs/architecture/overview.md`, `docs/architecture/product-production-workflow.md`, `docs/architecture/run-state-event-matrix.md`.
