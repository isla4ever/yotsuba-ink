# Changelog

All notable user-visible changes to Yotsuba Ink are documented here.

## [0.1.0] - 2026-09-06

This release reboots Yotsuba Ink around three deliverable-specific creation routes and one authoritative production path.

### Added

- Three canonical official routes: screenplay sample, short fiction, and long-form novel.
- Route-specific stage artifacts and workbenches, including Beat Board, Scene Deck, Story Map, Book Architecture, Volume Architecture, Rolling Detail, sequential prose, and deterministic text delivery.
- Durable run checkpoints, operation and attempt receipts, frozen usage budgets, failure projection, idempotent writeback, and cold-process recovery.
- Author decisions, source-bound editing, one directed revision, contract-repair quarantine, amendment successors, and Canon/Wiki writeback.
- Route-aware run monitoring, Story Bible projections, Provider usage and cost evidence, SSE replay, and explicit recovery states.
- Immutable release-evidence bundles with cold-process validation and a supervised 12-chapter live DeepSeek continuity sample.

### Changed

- New projects use `official.screenplay_sample`, `official.short_novel`, or `official.long_novel`; retired Fast/Balanced/Deep identities are not accepted by the canonical creation path.
- The public workflow catalog, creation wizard, project shell, command palette, settings, stage navigation, and health response now use route-native identities and manifests.
- API version, Python package, web package, and lock metadata are aligned at `0.1.0`.
- CORS defaults to the local workbench origins and requires an explicit allowlist for additional origins.
- README documentation now describes the actual three-route product, acceptance boundary, Provider setup, and release gates.

### Verified

- The live long-form sample completed 12/12 chapters and 12/12 committed writebacks.
- Three network failures across 48 transport attempts recovered within their original logical operations.
- Frozen evidence can be validated from a fresh process without depending on in-memory state.
- Offline contract suites cover all three routes, stage artifacts, decisions, recovery, writeback, delivery, and public API boundaries.

### Known limits

- Cover image generation is deferred and is not part of the `0.1.0` acceptance gate. Short and long fiction end in the explicit `image_deferred` state after producing a CoverBrief.
- Workflow continuity passed, but the live literary sample still reports chapter-length shortfall, procedural repetition, and causal-confidence warnings. Literary production acceptance remains separate from runtime acceptance.
