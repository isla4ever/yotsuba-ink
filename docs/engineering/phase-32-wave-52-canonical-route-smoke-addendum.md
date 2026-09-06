# Phase 32 Wave 52 — Canonical Smoke Addendum

## Long-novel rerun after decision-frontier fix

Run: `release-smoke-canonical-long_novel-20260826-r3`
Workflow: `official.long_novel`
Provider/model: `provider-deepseek-text` / `deepseek-v4-pro`

The fresh run completed all ten frozen text units (`chapter_01` through `chapter_10`), accepted the mandatory cover decision, and reached the expected terminal state:

- status: `image_deferred`
- completed stages: brief, book architecture, cast, volumes, rolling detail, text, cover
- export: locked; `export_ready=false`
- provider operations: 28 total, 28 returned, 26 final succeeded plus 2 first-pass contract rejections recovered by the existing writeback correction path
- pending operations: 0
- estimated conservative upper-bound cost: `$0.24674892`
- image operations: 0

The r2 failure is now explained and covered by a regression test: a scalar LangGraph resume value could be consumed by the next mandatory stage after a sequential text stage. The executor now reads the unique active interrupt id from the durable checkpoint and resumes with an interrupt-id mapping. The long route then proceeds from text to cover without decision-id drift.

## Quality signal

The long run is a transport and state-continuity pass, but not a perfect first-pass quality pass. Two writeback evidence proposals were rejected before correction:

1. one transition contained an object where the contract requires a string and omitted `state` on two claims;
2. one response encoded assertion states as JSON strings instead of objects.

Both were recovered deterministically by the existing one-correction path and left no pending operation. Wave 53 should still tighten the writeback prompt/schema examples and track first-pass contract-rejection rate as a quality metric rather than hiding it behind the final status.

## Verification

- Backend: `1154 passed, 1 warning`
- Focused route-graph and graph-execution tests: all passed, including sequential text → mandatory cover regression
- No image provider call was made
