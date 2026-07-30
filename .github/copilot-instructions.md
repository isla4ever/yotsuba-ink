# Copilot Instructions

This repository is the open-source `Yotsuba Ink` product. Optimize for structural consistency and maintainability before feature sprawl.

## Frontend Rules

- `apps/web/src/features/pipeline` must use one structure only:
  - `layout/`
  - `planning/`
  - `brief/`
  - `running/`
  - `settings/`
  - `state/`
  - `services/`
  - `contracts/`
  - `lib/`
- Do not reintroduce mixed top-level buckets such as `components/`, `panels/`, `dialogs/`, or `screens/`.
- Keep screens thin, services IO-only, state files React-only, and lib files pure.

## Backend Rules

- `src/novel_workflow/api` is a thin adapter layer only.
- Keep business logic out of `api/routes`.
- Reference merging belongs in `references/`.
- Orchestration belongs in `orchestration/` or workflow-domain modules.
- Quality logic belongs in `quality/`.

## General Rules

- Prefer existing repo boundaries over new abstractions.
- Avoid god files; keep most files near `200-250` lines and heavy files under `300`.
- Preserve API paths, current product semantics, and demo fallback behavior unless the task explicitly changes them.
- Prefer structured contracts over loose stringly-typed payloads.
