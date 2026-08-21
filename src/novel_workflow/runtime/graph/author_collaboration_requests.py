from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.author_collaboration import (
    CollaborationMode,
    CollaborationPlan,
    CollaborationStageId,
    ProviderCollaborationPatchResult,
    ProviderCollaborationPlanResult,
)
from novel_workflow.providers.base import PROMPT_SYSTEM_SPLIT
from novel_workflow.runtime.graph.provider_input_compiler import (
    secret_free_provider_binding,
)
from novel_workflow.storage.narrative_run_repository import ProviderBinding
from novel_workflow.storage.provider_input_store import (
    ProviderInputPayload,
    ProviderOutputContract,
)


class CollaborationGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    thread_id: str
    turn_id: str
    stage_id: CollaborationStageId
    mode: CollaborationMode
    binding: ProviderBinding
    context_receipt_ref: str
    material: dict[str, str]
    selection_field_path: str = ""


class CollaborationProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=20_000)
    plan: CollaborationPlan | None = None
    replacement: str = Field(default="", max_length=40_000)
    rationale: str = Field(default="", max_length=4_000)
    usage: dict[str, int] = Field(default_factory=dict)
    diagnostic: dict[str, Any] = Field(default_factory=dict)


def compile_collaboration_provider_input(
    request: CollaborationGenerationRequest,
) -> ProviderInputPayload:
    prompt = render_collaboration_prompt(request)
    if request.mode == "plan":
        output = ProviderOutputContract(
            kind="structured_json",
            json_schema_contract=ProviderCollaborationPlanResult.model_json_schema(),
            schema_digest=_digest(
                ProviderCollaborationPlanResult.model_json_schema()
            ),
            structured_mode="strict_json",
        )
    elif request.mode == "revise":
        output = ProviderOutputContract(
            kind="structured_json",
            json_schema_contract=ProviderCollaborationPatchResult.model_json_schema(),
            schema_digest=_digest(
                ProviderCollaborationPatchResult.model_json_schema()
            ),
            structured_mode="strict_json",
        )
    else:
        output = ProviderOutputContract(
            kind="plain_text",
            plain_text_contract=(
                "A concise professional writing consultation in Chinese. "
                "Do not emit JSON, hidden identifiers, or claim to have modified the Artifact."
            ),
        )
    return ProviderInputPayload(
        stage_id=request.stage_id,
        task_name=f"author_collaboration.{request.mode}",
        attempt=1,
        provider_binding=secret_free_provider_binding(request.binding),
        prompt_template_id="author-collaboration-v1",
        prompt_digest=_digest(prompt),
        rendered_prompt=prompt,
        structured_context={
            "thread_id": request.thread_id,
            "turn_id": request.turn_id,
            "stage_id": request.stage_id,
            "mode": request.mode,
            "context_receipt_ref": request.context_receipt_ref,
            "selection_field_path": request.selection_field_path,
        },
        output_contract=output,
    )


def render_collaboration_prompt(request: CollaborationGenerationRequest) -> str:
    mode_instruction = {
        "discuss": (
            "与作者讨论当前局部内容。先回应真实问题，指出依据和不确定处；"
            "不得声称已经修改作品，不得输出内部 ID、哈希或 JSON。"
        ),
        "plan": (
            "输出严格 JSON：response 是面向作者的简洁说明；plan 必须包含 goal、"
            "findings、steps、impacts、risks、questions。方案可以讨论结构变化，"
            "但不得声称已经写回。"
        ),
        "revise": (
            "只改写上下文中 selection 对应的文字，输出严格 JSON：response、replacement、"
            "rationale。replacement 只包含替换后的文字，不要标题、Markdown、解释或省略号。"
            "不得改 ID、顺序、引用、角色主体、卷章结构或事实账本。"
        ),
    }[request.mode]
    system = (
        "你是 Yotsuba Ink 精细模式的专业作者协作编辑。作品权威只来自本轮冻结上下文，"
        "对话不是 Canon、Wiki、Memory 或 Artifact。你必须保持人物动机、因果、世界规则、"
        "伏笔和连续性一致；信息不足时明确追问，不得虚构系统已提供之外的既定事实。\n"
        f"当前阶段：{request.stage_id}。{mode_instruction}"
    )
    sections = []
    for key, value in request.material.items():
        sections.append(f"## {key}\n{value}")
    user = (
        f"上下文回执：{request.context_receipt_ref}\n"
        f"协作模式：{request.mode}\n\n"
        + "\n\n".join(sections)
    )
    return f"{system}{PROMPT_SYSTEM_SPLIT}{user}"


def _digest(value: Any) -> str:
    encoded = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "CollaborationGenerationRequest",
    "CollaborationProviderResult",
    "compile_collaboration_provider_input",
    "render_collaboration_prompt",
]
