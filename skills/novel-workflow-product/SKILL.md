---
name: novel-workflow-product
description: Use when modifying this repository's online-API novel workflow product, including React Flow workflow UI, LangGraph/FastAPI backend, provider adapters, wiki memory, quality gates, cover generation, or open-source packaging.
---

# Novel Workflow Product

## Core Rules

- Prefer high-quality open-source bases before building from scratch. Record source, commit, license, and retained ideas in `vendor/NOTES.md`.
- Keep online provider access as the only generation path. Do not add local model training, LoRA, torch serving, or GPU setup to the product runtime.
- Keep product code modular: API, workflows, stages, providers, memory, storage, and frontend UI must stay in separate modules.
- Do not add large all-purpose files. Split files before they become difficult to scan.
- Provider integrations must have a mock path so tests and demos run without API keys.
- Workflow nodes must be schema-driven and serializable from the frontend. Do not hide business execution logic inside React components.
- Wiki memory is a runtime capability, not a visible default workflow node. Inject constraints before creative nodes, write memory after nodes, and return status/refs to the UI.

## Backend Pattern

- Put FastAPI routes under `src/novel_workflow/api`.
- Put workflow schemas, compiler, templates, and runner under `src/novel_workflow/workflows`.
- Put novel stage behavior under `src/novel_workflow/stages`.
- Put online API clients under `src/novel_workflow/providers`; expose each through `ProviderRegistry`.
- Keep `NovelRunState` as the state contract between nodes.
- Stream run progress as JSON SSE events with stable event types: `run_started`, `memory_context_loaded`, `node_started`, `node_completed`, `memory_writeback_completed`, `node_failed`, `run_completed`, `run_failed`.

## Frontend Pattern

- Build from the React Flow base in `apps/web`.
- The first screen is the usable workflow workspace, not a landing page.
- Keep nodes visually compact and domain-specific: info recommendation, summary, outline, detail outline, chapter text, quality gate, cover image, export. Do not expose Wiki query/writeback as default canvas nodes.
- Show progress, partial results, quality report, wiki status, and cover output during runs.
- Keep node config serializable into backend `WorkflowDefinition`.

## Quality Gates

- Add or update Python tests for workflow compiler, runner, providers, wiki, and API changes.
- Add frontend build or component tests when changing UI behavior.
- For visual changes, run the app and inspect desktop and mobile layout before finishing.
