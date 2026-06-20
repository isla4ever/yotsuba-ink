# Copilot Instructions

This repository is an open-source long-form fiction orchestration framework. Optimize for maintainability and product coherence, not just feature throughput.

## Engineering defaults

- Prefer existing repo patterns over introducing a new framework or helper layer.
- Keep files small and responsibility-focused.
- Do not append new product logic to:
  - `src/novel_workflow/workflows/runner.py`
  - `src/novel_workflow/api/app.py`
  - `apps/web/src/App.tsx`
  - `apps/web/src/features/pipeline/components/StageRunWorkbench.tsx`
  unless the file remains a thin facade.
- Preserve mock/demo fallback behavior when online providers are unavailable.

## Product defaults

- Story Brief approval is the main human gate.
- Wiki / Story Bible is the runtime fact layer, not a decorative info panel.
- Quality gate is a decision layer: `pass`, `revise`, or `block`.
- Token/cost feedback should be informative and honest; do not fake precision.
- Structured outputs should be preferred over unstructured text when practical.

## UI defaults

- Planning/configuration and running/workbench modes should stay visually distinct.
- Primary workflow controls first, diagnostics second, ambient effects last.
- Avoid oversized cards and duplicated controls.
- Dense interfaces should still preserve scanning rhythm and readable spacing.
