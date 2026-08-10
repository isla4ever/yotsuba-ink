---
name: yotsuba-ink-architecture-reboot
description: Reboot or review Yotsuba Ink architecture from one authoritative production path. Use when replacing a workflow runtime, removing legacy or compatibility paths, redesigning stages, artifacts, recovery, approvals, SSE, writeback, memory, RAG, or frontend projections, or when repeated same-class failures show that another local patch would preserve the wrong boundary.
---

# Yotsuba Ink Architecture Reboot

Apply this skill together with `novel-workflow-engineering-guardrails`, `novel-workflow-stage-contract`, `yotsuba-ink-production-closure`, `product-manager-critic`, and `agent-context-engineering`.

## Hold The Safety Boundary

1. Treat the dirty worktree as user-owned. Inspect status and targeted diffs before editing; never reset, revert, clean, or overwrite unrelated work.
2. Keep local services stopped and real Provider calls disabled during architecture research and review.
3. Change architecture documents and this Skill only until the user explicitly approves the new phase document.
4. Use historical runs and old phase documents only to locate failure evidence. Do not inherit their proposed solution by default.

## Find One Authority First

1. Read `AGENTS.md`, `docs/architecture/stage-artifact-contract.md`, the latest active phase document, and the affected source before proposing a design.
2. Trace the actual production path for execution, state, recovery, human decisions, concurrent review, Provider calls, writeback, SSE, and frontend projection.
3. For every concept, name its current writer, reader, persistence owner, recovery owner, and competing source.
4. Distinguish domain authorities from projections. A checkpointer, Artifact store, Canon, Wiki, Outbox, budget ledger, event projection, and UI read model may each own different data, but two systems must not own the same decision.
5. Do not infer authority from filenames, flags, labels, schemas, or intended diagrams. Prove it from call paths and writes.

## Make The Product Decision Before The Framework Decision

Define each stage's unique Artifact, user decision, formal writeback target, and downstream dependency before designing State, Nodes, API, or UI.

Compare candidate architectures against explicit product requirements and current source boundaries. Do not mechanically accept a requested framework. Record why the selected abstraction fits and what changed assumptions would require reevaluation.

When LangChain and LangGraph are candidates, compare them at the same control-plane layer. Evaluate direct LangGraph Graph API against LangChain's high-level agent loop for explicit stage edges, thread/checkpoint authority, interrupt/resume, parallel review, Provider receipts, SSE projection, and existing Artifact/Prompt ports. For the approved Phase 26 architecture, production code must not directly depend on or import LangChain APIs; LangGraph's transitive `langchain-core` dependency is framework internals, not a project API. Reopen this decision only through a separate RFC and source spike proving that direct LangGraph plus existing domain ports cannot cover a concrete need.

Ask the user before proceeding when a material uncertainty would change stage meaning, data authority, migration destructiveness, Provider cost, historical-run policy, or user-visible workflow. Resolve lower-impact implementation details from repository evidence.

## Reboot Instead Of Patching

- When the same failure class recurs after bounded fixes, stop adding guards at the symptom. Return to the lowest responsible Artifact, State, Node, Context, Provider, persistence, or UI-projection boundary.
- Reject Shadow, Dual, feature-flag runtime selection, silent degradation, implicit Provider/model switching, emergency legacy execution, and fallback review waves.
- Reject production aliases, converters, normalizers, default injection, and old-schema read fallbacks once the new contract is authoritative.
- Keep historical runs only in an isolated, read-only, zero-Provider archive viewer. Never convert archived state into executable production input.
- Prefer deleting a redundant path or rewriting an ownership boundary over wrapping it with another facade.

## Require Document Review Before Implementation

The new phase document must contain:

1. Current authority map and root-cause findings.
2. Product decisions and explicit rejected alternatives.
3. External source ledger with repository URL, commit or tag, access date, license, and reuse boundary.
4. Keep/migrate/delete/archive matrix naming concrete production paths.
5. vNext stage sequence and minimal Artifact contracts split into core Artifact, deterministic projection, runtime sidecar, narrow call/tool result, and deleted fields.
6. Runtime State, Node, Edge, parallel branch, interrupt, checkpoint, replay, idempotency, and failure semantics.
7. Memory, Evidence, Canon, Wiki, RAG, budget, Provider receipt, Outbox, SSE, and frontend authority boundaries.
8. Frontend navigation, Artifact forms, decision states, observability, and writeback projections using the same backend semantics.
9. Migration Waves, tests, offline gates, real Provider acceptance, and unresolved decisions.

Do not implement production architecture while this document is awaiting review.

## Enforce Wave Exit Gates

For every Wave:

1. Name the new positive production path.
2. Name the old production files, fields, imports, routes, events, or flags deleted in the same Wave.
3. Add boundary tests that prove the new path and rejection tests that prove the old path cannot execute.
4. Add static searches or import checks that make legacy absence verifiable.
5. Define one explicit exit gate and keep the next Wave blocked until it passes.

Never call a Wave complete because new code exists while the old path still runs. Run deterministic and fake-Provider gates first. Real Provider validation requires separate user approval, fresh Runs, bounded cost, redacted receipts, and human literary review.

## Report Precisely

Separate documented design, local contract proof, browser proof, live Provider proof, and human literary acceptance. Report unresolved gates without converting partial evidence into production closure.
