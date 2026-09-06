"""Frozen creation-language authority for future Phase 32 Runs."""

from __future__ import annotations

from typing import Literal

from novel_workflow.workflows.route_specs import CreationRouteId


CreationLanguage = Literal["zh-CN"]

PHASE32_CREATION_LANGUAGE: CreationLanguage = "zh-CN"
PHASE32_INPUTS_CONTRACT_REVISION = "r2"
PHASE32_LANGUAGE_PROMPT_CONTRACT_MARKER = (
    "inputs.creation_language 是唯一输出语言权威"
)


def phase32_inputs_contract_id(route_id: CreationRouteId | str) -> str:
    return f"inputs.{route_id}.v2"


__all__ = [
    "CreationLanguage",
    "PHASE32_CREATION_LANGUAGE",
    "PHASE32_INPUTS_CONTRACT_REVISION",
    "PHASE32_LANGUAGE_PROMPT_CONTRACT_MARKER",
    "phase32_inputs_contract_id",
]
