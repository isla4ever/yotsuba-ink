"""Ports used to admit private Phase 32 text Provider operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from novel_workflow.providers.phase32_contract import (
        Phase32ProviderRequest,
        Phase32StageProviderBindingSnapshot,
        Phase32WritebackProviderRequest,
    )
    from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


class Phase32ProviderOperationAdmissionFence(BaseModel):
    """Exact budget grant that must fence the following transport claim."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    authorization_ref: str = Field(pattern=r"^p32-run-budget-[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    operation_key: str = Field(min_length=1, max_length=500)
    request_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    admission_ref: str = Field(pattern=r"^p32-budget-admission-[a-f0-9]{64}$")
    transport_attempt: int = Field(gt=0)

    @field_validator("transport_attempt", mode="before")
    @classmethod
    def reject_boolean_attempt(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Provider transport attempt cannot be boolean")
        return value


class Phase32TextOperationAdmission(Protocol):
    """Fail-closed gate invoked before private continuity Provider IO."""

    def require_run(self, definition: "GraphRunDefinition") -> Any:
        """Require current persisted readiness and matching budget authority."""

    def admit_text_operation(
        self,
        *,
        definition: "GraphRunDefinition",
        request: "Phase32ProviderRequest | Phase32WritebackProviderRequest",
        binding: "Phase32StageProviderBindingSnapshot",
        request_signature: str,
        max_transport_attempts: int,
    ) -> Phase32ProviderOperationAdmissionFence:
        """Reserve one transport attempt for an exact frozen request."""


__all__ = [
    "Phase32ProviderOperationAdmissionFence",
    "Phase32TextOperationAdmission",
]
