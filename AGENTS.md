# AGENTS

This repository follows a repo-specific engineering guardrail set for `Yotsuba Ink`.

## Product Scope

- Keep the repository focused on the Yotsuba Ink product.
- Do not reintroduce training assets, vendor snapshots, or historical report logic into the main product tree.
- Follow the stage artifact contract in `docs/architecture/stage-artifact-contract.md` before changing stage UI, model outputs, SSE events, runtime panels, or route-per-stage behavior.
- Do not design stage pages by filling empty space. Define the stage artifact, user decision, writeback target, and next-stage dependency first.

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

- File size is a maintainability signal, not a mechanical limit.
- Normal source files should usually stay around `250-350` lines when the responsibility remains clear.
- Cohesive, implementation-heavy modules may reach roughly `450-500` lines when keeping the behavior together improves correctness, testability, or readability.
- Files above that range require a responsibility review, but must not be split only to satisfy a line count.
- Split when a file mixes independently changing responsibilities, becomes difficult to test in isolation, creates frequent merge conflicts, or requires unrelated knowledge to understand. Do not trade a complete implementation for artificial brevity or excessive indirection.

## Working Rules

- Start with the smallest correct change inside an existing boundary.
- Reuse local helpers and standard/platform capabilities before adding abstractions.
- Preserve API behavior and product semantics unless the task explicitly changes them.
- Keep demo and mock flows working when real providers are unavailable.
