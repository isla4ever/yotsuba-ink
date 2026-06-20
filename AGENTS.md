# AGENTS

This repository follows a repo-specific engineering guardrail set for `Novel Workflow`.

## Product Scope

- Keep the repository focused on the Novel Workflow product.
- Do not reintroduce training assets, vendor snapshots, or historical report logic into the main product tree.

## Frontend Structure

`apps/web/src/features/pipeline` uses one directory system only:

- `layout/`
- `planning/`
- `brief/`
- `running/`
- `settings/`
- `state/`
- `services/`
- `contracts/`
- `lib/`

Do not keep parallel top-level buckets like `components/`, `panels/`, `dialogs/`, `screens/`, or other temporary taxonomy folders after refactors.

## Backend Structure

`src/novel_workflow/api` is an adapter layer only:

- `app.py`
- `bootstrap.py`
- `dependencies.py`
- `sse.py`
- `routes/`
- `run.py`

Reference aggregation, orchestration, quality logic, and persistence rules belong in domain packages, not in route files.

## Naming And Boundaries

- React components: `PascalCase.tsx`
- React hooks: `useXxx.ts`
- TS IO adapters: `xxxApi.ts`, `xxxStream.ts`
- Python modules: `snake_case.py`
- One file, one primary responsibility
- Pure helpers must not live inside component files when they can be extracted cleanly

## Size Guardrails

- Normal source files should stay around `200-250` lines.
- Heavy modules may reach `300` lines when justified.
- Split files by responsibility before adding more behavior past that range.

## Working Rules

- Start with the smallest correct change inside an existing boundary.
- Reuse local helpers and standard/platform capabilities before adding abstractions.
- Preserve API behavior and product semantics unless the task explicitly changes them.
- Keep demo and mock flows working when real providers are unavailable.
