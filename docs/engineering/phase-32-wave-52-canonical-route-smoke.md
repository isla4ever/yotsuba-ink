# Phase 32 Wave 52 — Canonical Route Smoke Evidence

## Scope

This record covers the first bounded live-provider validation of the three official text routes. Image generation is explicitly outside acceptance for this wave. The canonical short-novel and long-novel routes therefore stop at `image_deferred`; no image provider operation is allowed.

Provider: `provider-deepseek-text`
Models: `deepseek-v4-flash` for `official.screenplay_sample`; `deepseek-v4-pro` for `official.short_novel` and `official.long_novel`.

## Results

| Route | Run | Result | Provider ops | Contract rejects | Estimated upper-bound cost | Image ops |
|---|---|---:|---:|---:|---:|---:|
| Screenplay sample | `release-smoke-canonical-screenplay-20260826-r2` | `completed` | 10/10 | 0 | `$0.01612248` | 0 |
| Short novel | `release-smoke-canonical-short_novel-20260826-r2` | `image_deferred` | 11/11 | 0 | `$0.06370848` | 0 |
| Long novel | `release-smoke-canonical-long_novel-20260826-r3` | `image_deferred` | 28/28 returned; 26 final successes + 2 corrected contract rejects | 2 first-pass writeback rejects, recovered | `$0.24674892` | 0 |

### Screenplay

The canonical route completed the full text loop: brief, beat board, three script scenes, writeback, and export readiness. The terminal state was `completed`, with 44 SSE events and no contract rejection.

### Short novel

The canonical route completed brief, story map, three text units, cover brief, and writeback. The terminal state was `image_deferred`; export remained locked by contract. There were 46 SSE events, no pending operations, no rejected contracts, and zero image operations.

### Long novel

The first r2 attempt was diagnostic only: a local `PermissionError` interrupted the runtime before cover completion. After the checkpoint-resume fix, fresh r3 completed all ten configured text chapters, accepted the mandatory cover decision, and reached `image_deferred` with export locked. The two first-pass writeback contract rejects were recovered by the existing one-correction path and are retained as a quality signal.

## Findings fixed during this wave

1. Canonical screenplay route was inheriting the Pro default instead of the official Flash route. Canonical route model selection is now explicit and deterministic.
2. Canonical short/long stages were falling back to a generic 1800-token cap. Stage-specific generation budgets are now used for canonical bindings.
3. Nested long-novel detail schemas emitted shallow examples such as `chapters: ["value"]`, which encouraged structurally invalid strings. The example-depth window now preserves nested chapter and scene objects.

## Acceptance gates still open

- Repeat the long-novel route in a clean writable runtime and verify terminal `image_deferred`.
- Verify recovery and cold-read continuity after a fresh process restart.
- Run human literary review for continuity, causal progression, and prose quality; transport success alone is insufficient.
- Keep image generation deferred until the text gates are green; then begin the separate Wave 56 image re-entry acceptance.
