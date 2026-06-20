# Contributing

Thanks for contributing to Novel Workflow.

## What this project is

Novel Workflow is an orchestration framework for long-form fiction production:

- Story Brief approval gate
- Story Bible / Wiki continuity layer
- quality gates and revision loops
- provider-agnostic stage orchestration
- token-aware and cost-aware runtime surfaces

## What we optimize for

- Small, readable modules
- Stable public behavior
- Clear domain boundaries
- Demo-friendly local development
- Open-source friendliness for adapters and workflow extensions

## Before you open a PR

1. Confirm the change belongs to the Novel Workflow product path.
2. Prefer refactoring mixed-responsibility files before adding more logic to them.
3. Keep new modules narrow and well named.
4. Preserve or improve tests.

## Local checks

```bash
cd apps/web && npm run build
.venv/bin/python -m pytest tests/test_workflow_runner.py -q
```

## Layout expectations

- Backend route logic belongs in `src/novel_workflow/api/routes/`.
- Runtime coordination belongs in `src/novel_workflow/orchestration/`.
- Usage and token accounting belongs in `src/novel_workflow/usage/`.
- UI stateful containers belong in `apps/web/src/features/pipeline/state/`.
- Large React screens should compose smaller presentational modules.

## Dependency policy

- Prefer stdlib and existing repo dependencies first.
- Add a new dependency only when it materially reduces complexity or unlocks a core platform advantage.
- Repository conventions inspired by Ponytail are documentation-level rules, not runtime product dependencies.
