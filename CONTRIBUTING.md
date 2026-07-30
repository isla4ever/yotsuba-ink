# Contributing

Thanks for contributing to Yotsuba Ink.

## What this project is

Yotsuba Ink is an orchestration framework for long-form fiction production:

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

1. Confirm the change belongs to the Yotsuba Ink product path.
2. Prefer refactoring mixed-responsibility files before adding more logic to them.
3. Keep new modules narrow and well named.
4. Preserve or improve tests.

## Local checks

```bash
.venv/bin/python -m pytest -q
cd apps/web
npm test
npm run build
npm run audit:css
npm run check:css-split
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
