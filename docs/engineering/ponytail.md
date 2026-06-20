# Ponytail-Inspired Engineering Rules

This repository adopts Ponytail as a repository-level engineering discipline rather than an application dependency.

## Why

Ponytail is valuable here as a review posture:

- question whether the feature should exist before writing it
- prefer simpler primitives over new abstraction layers
- reduce unnecessary code volume
- keep interfaces explicit and easy to audit

What we do **not** do:

- ship Ponytail as a runtime dependency
- couple product code to a specific AI coding plugin
- require contributors to install a plugin before contributing

## Rules we apply here

### 1. Solve the real product problem

If a requested change adds noise, cognitive load, or maintenance cost without improving the novel-creation flow, push back and refine it.

### 2. Prefer stable seams

- stage contracts
- event schemas
- API routers
- typed UI state
- Story Bible update boundaries

Avoid hidden coupling across planning UI, run-time UI, and model adapter code.

### 3. Keep abstractions earned

Add a helper, hook, or service only when it:

- removes repeated logic
- creates a real domain boundary
- improves testability or replacement

### 4. Make fallback paths real

The project should still run in demo mode without paid provider credentials.

### 5. Measure honestly

Token, cost, cache, and quality telemetry should be explicit about what is:

- estimated
- observed
- unavailable

We prefer an honest approximation over a fake exact number.
