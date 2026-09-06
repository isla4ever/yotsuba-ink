"""Append-only transport-attempt evidence for Phase 32 Provider receipts."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from novel_workflow.workflows.frozen_route_contract import canonical_digest


TransportAttemptEventKind = Literal[
    "claimed",
    "lease_expired",
    "transport_failed",
    "provider_returned",
]

_EVENT_REF_PREFIX = "p32-transport-attempt-event-"
_PUBLIC_CODE = re.compile(r"^[a-z][a-z0-9_.-]{1,119}$")


class Phase32ProviderTransportAttemptEvent(BaseModel):
    """One immutable observation in a Provider operation's attempt history."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    event_ref: str = Field(pattern=r"^p32-transport-attempt-event-[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    operation_key: str = Field(min_length=1, max_length=500)
    request_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    transport_attempt: int = Field(gt=0)
    event_kind: TransportAttemptEventKind
    admission_ref: str = Field(
        default="",
        pattern=r"^$|^p32-budget-admission-[a-f0-9]{64}$",
    )
    lease_owner_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    occurred_at: str = Field(min_length=1, max_length=80)
    elapsed_ms: int | None = Field(default=None, ge=0)
    error_code: str = Field(default="", max_length=120)

    @field_validator("transport_attempt", mode="before")
    @classmethod
    def reject_boolean_attempt(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Provider transport attempt cannot be boolean")
        return value

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        _parse_timestamp(self.occurred_at)
        is_claim = self.event_kind == "claimed"
        if is_claim != (self.elapsed_ms is None):
            raise ValueError("Only terminal attempt events record elapsed time")
        if self.event_kind in {"lease_expired", "transport_failed"}:
            if not self.error_code or _PUBLIC_CODE.fullmatch(self.error_code) is None:
                raise ValueError("Failed attempt events require a public error code")
        elif self.error_code:
            raise ValueError("Successful attempt events cannot carry an error code")
        expected_ref = _content_ref(
            self.model_dump(mode="json", exclude={"event_ref"})
        )
        if self.event_ref != expected_ref:
            raise ValueError("Provider attempt event is not content addressed")
        return self


def build_claimed_attempt_event(
    *,
    run_id: str,
    operation_key: str,
    request_signature: str,
    transport_attempt: int,
    admission_ref: str,
    lease_owner: str,
    occurred_at: str,
) -> Phase32ProviderTransportAttemptEvent:
    payload = {
        "architecture_version": "phase32-routes-v1",
        "run_id": run_id,
        "operation_key": operation_key,
        "request_signature": request_signature,
        "transport_attempt": transport_attempt,
        "event_kind": "claimed",
        "admission_ref": admission_ref,
        "lease_owner_digest": lease_owner_summary(lease_owner),
        "occurred_at": occurred_at,
        "elapsed_ms": None,
        "error_code": "",
    }
    return Phase32ProviderTransportAttemptEvent.model_validate(
        {**payload, "event_ref": _content_ref(payload)}
    )


def append_terminal_attempt_event(
    events: tuple[Phase32ProviderTransportAttemptEvent, ...],
    *,
    transport_attempt: int,
    event_kind: Literal["lease_expired", "transport_failed", "provider_returned"],
    lease_owner: str,
    occurred_at: str,
    error_code: str = "",
) -> tuple[Phase32ProviderTransportAttemptEvent, ...]:
    claim = next(
        (
            event
            for event in reversed(events)
            if event.transport_attempt == transport_attempt
            and event.event_kind == "claimed"
        ),
        None,
    )
    if claim is None:
        # Pre-Wave-60 receipts remain readable, but cannot pass the release
        # evidence verifier because their earlier transport was unobserved.
        return events
    terminal = next(
        (
            event
            for event in events
            if event.transport_attempt == transport_attempt
            and event.event_kind != "claimed"
        ),
        None,
    )
    if terminal is not None:
        if terminal.event_kind != event_kind:
            raise ValueError("Provider transport attempt already has another terminal event")
        return events
    ended_at = _parse_timestamp(occurred_at)
    started_at = _parse_timestamp(claim.occurred_at)
    if ended_at < started_at:
        # Wall clocks may move backwards (or deterministic tests may inject a
        # future claim time). Preserve causal ordering instead of fabricating
        # a negative duration.
        ended_at = started_at
        occurred_at = claim.occurred_at
    payload = {
        "architecture_version": "phase32-routes-v1",
        "run_id": claim.run_id,
        "operation_key": claim.operation_key,
        "request_signature": claim.request_signature,
        "transport_attempt": transport_attempt,
        "event_kind": event_kind,
        "admission_ref": claim.admission_ref,
        "lease_owner_digest": lease_owner_summary(lease_owner),
        "occurred_at": occurred_at,
        "elapsed_ms": int(round((ended_at - started_at).total_seconds() * 1_000)),
        "error_code": public_transport_error_code(error_code) if event_kind != "provider_returned" else "",
    }
    event = Phase32ProviderTransportAttemptEvent.model_validate(
        {**payload, "event_ref": _content_ref(payload)}
    )
    return (*events, event)


def append_claimed_attempt_event(
    events: tuple[Phase32ProviderTransportAttemptEvent, ...],
    event: Phase32ProviderTransportAttemptEvent,
) -> tuple[Phase32ProviderTransportAttemptEvent, ...]:
    if event.event_kind != "claimed":
        raise ValueError("Provider attempt ledger can only claim with a claimed event")
    if any(item.transport_attempt == event.transport_attempt for item in events):
        raise ValueError("Provider transport attempt was already recorded")
    tracked_attempts = tuple(
        item.transport_attempt for item in events if item.event_kind == "claimed"
    )
    if tracked_attempts and event.transport_attempt != tracked_attempts[-1] + 1:
        raise ValueError("Provider attempt ledger claim sequence is not contiguous")
    if tracked_attempts and not any(
        item.transport_attempt == tracked_attempts[-1] and item.event_kind != "claimed"
        for item in events
    ):
        raise ValueError("Previous Provider transport attempt has no terminal evidence")
    return (*events, event)


def validate_transport_attempt_events(
    events: tuple[Phase32ProviderTransportAttemptEvent, ...],
    *,
    run_id: str,
    operation_key: str,
    request_signature: str,
    transport_attempts: int,
    admission_refs: tuple[str, ...],
) -> None:
    seen_refs: set[str] = set()
    claims: list[int] = []
    terminal_attempts: set[int] = set()
    open_attempt: int | None = None
    for event in events:
        if event.event_ref in seen_refs:
            raise ValueError("Provider attempt ledger event references must be unique")
        seen_refs.add(event.event_ref)
        if (
            event.run_id != run_id
            or event.operation_key != operation_key
            or event.request_signature != request_signature
        ):
            raise ValueError("Provider attempt ledger belongs to another frozen request")
        if event.transport_attempt > transport_attempts:
            raise ValueError("Provider attempt ledger exceeds the receipt attempt count")
        if event.event_kind == "claimed":
            if open_attempt is not None:
                raise ValueError(
                    "Provider attempt ledger starts a claim before closing the previous attempt"
                )
            if event.transport_attempt in claims:
                raise ValueError("Provider attempt ledger contains a duplicate claim")
            if claims and event.transport_attempt != claims[-1] + 1:
                raise ValueError("Provider attempt ledger claim sequence is not contiguous")
            claims.append(event.transport_attempt)
            if admission_refs:
                if event.admission_ref != admission_refs[event.transport_attempt - 1]:
                    raise ValueError("Provider attempt event admission differs from its receipt")
            elif event.admission_ref:
                raise ValueError("Unbudgeted Provider attempt cannot carry an admission")
            open_attempt = event.transport_attempt
            continue
        if event.transport_attempt not in claims or open_attempt != event.transport_attempt:
            raise ValueError("Provider attempt terminal event precedes its claim")
        if event.transport_attempt in terminal_attempts:
            raise ValueError("Provider attempt ledger contains duplicate terminal evidence")
        claim = next(
            item
            for item in events
            if item.transport_attempt == event.transport_attempt
            and item.event_kind == "claimed"
        )
        if event.admission_ref != claim.admission_ref:
            raise ValueError("Provider attempt terminal admission differs from its claim")
        if event.lease_owner_digest != claim.lease_owner_digest:
            raise ValueError("Provider attempt terminal owner differs from its claim")
        started_at = _parse_timestamp(claim.occurred_at)
        ended_at = _parse_timestamp(event.occurred_at)
        expected_elapsed = int(round((ended_at - started_at).total_seconds() * 1_000))
        if ended_at < started_at or event.elapsed_ms != expected_elapsed:
            raise ValueError("Provider attempt terminal duration is inconsistent")
        terminal_attempts.add(event.transport_attempt)
        open_attempt = None
    if claims and claims[-1] != transport_attempts:
        raise ValueError("Provider attempt ledger does not end at the receipt head")


def lease_owner_summary(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def public_transport_error_code(value: object) -> str:
    candidate = str(value or "provider_transport_failed").strip().casefold()
    if _PUBLIC_CODE.fullmatch(candidate) is None:
        return "provider_transport_failed"
    return candidate


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Provider attempt timestamp must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("Provider attempt timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _content_ref(payload: dict[str, object]) -> str:
    return f"{_EVENT_REF_PREFIX}{canonical_digest(payload)}"


__all__ = [
    "Phase32ProviderTransportAttemptEvent",
    "TransportAttemptEventKind",
    "append_claimed_attempt_event",
    "append_terminal_attempt_event",
    "build_claimed_attempt_event",
    "lease_owner_summary",
    "public_transport_error_code",
    "validate_transport_attempt_events",
]
