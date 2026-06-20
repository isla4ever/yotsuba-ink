# AGENTS

This repository uses a Ponytail-style engineering discipline for both humans and AI coding agents.

## Product Focus

- The primary open-source product is `Novel Workflow`.
- Training, evaluation, and experimental assets exist, but they are secondary.
- Do not add product logic to legacy training paths unless the change explicitly belongs there.

## Coding Rules

- Start with the smallest correct change.
- Reuse standard library, platform features, and existing local helpers before adding dependencies.
- New abstractions must remove real duplication or isolate a domain boundary.
- Avoid god files. Product logic, UI composition, adapters, and experiments must not be mixed in one file.
- Default to structured data and typed contracts over ad hoc string parsing.
- Preserve local demo paths when real API keys or external services are unavailable.

## File Size Guidelines

- Normal source files should stay under `200-250` lines.
- Domain orchestrators and schema modules may grow to `300` lines when justified.
- If a file grows beyond that, split by responsibility before adding more features.

## Novel Workflow Domain Boundaries

- `orchestration/`: run coordination, stage transitions, pause/approval flow.
- `quality/`: checks, reports, revision directives, blocking decisions.
- `story_bible/` or runtime memory layers: canonical facts and continuity writeback.
- `usage/`: token, latency, cost, cache-awareness, stage usage summaries.
- `output_contracts/`: stage output schemas and normalization/repair hooks.
- `apps/web/src/features/pipeline`: planning UI, stage workbench UI, shared state and services.

## Review Checklist

- Does this change strengthen the main novel-production workflow?
- Does it preserve clear product hierarchy: creation path first, diagnostics second, decoration last?
- Is the change observable in tests or obvious behavior, not just in code structure?
- Did we keep the implementation provider-agnostic where possible?
- Did we avoid inventing knobs that add complexity without improving control?
