from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.openai_compat import (
    OpenAICompatibleTextProvider,
    _request_thinking_enabled,
)
from novel_workflow.providers.usage import provider_usage_snapshot
from novel_workflow.providers.structured_parsing import (
    parse_exact_json_object_result,
)


class _FakeSdkClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.content = content
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        if kwargs.get("stream") is True:
            return _FakeSdkStream(self.content)
        return {
            "choices": [
                {"finish_reason": "stop", "message": {"content": self.content}}
            ],
            "usage": {
                "prompt_tokens": 21,
                "completion_tokens": 8,
                "total_tokens": 29,
            },
        }


class _ReasoningUsageSdkClient(_FakeSdkClient):
    async def create(self, **kwargs: object) -> dict[str, object]:
        response = await super().create(**kwargs)
        usage = response["usage"]
        assert isinstance(usage, dict)
        usage["completion_tokens_details"] = {"reasoning_tokens": 5}
        return response


class _ReasoningOnlySdkClient(_FakeSdkClient):
    async def create(self, **kwargs: object) -> dict[str, object]:
        response = await super().create(**kwargs)
        choice = response["choices"][0]
        assert isinstance(choice, dict)
        message = choice["message"]
        assert isinstance(message, dict)
        message["content"] = ""
        message["reasoning_content"] = "仅用于诊断存在推理输出，不应作为结构化结果。"
        return response


class _FakeSdkStream:
    def __init__(self, content: str) -> None:
        midpoint = max(1, len(content) // 2)
        self.chunks = [
            {"choices": [{"finish_reason": None, "delta": {"content": content[:midpoint]}}]},
            {"choices": [{"finish_reason": "stop", "delta": {"content": content[midpoint:]}}]},
        ]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.chunks:
            raise StopAsyncIteration
        return self.chunks.pop(0)


def _provider(
    template_id: str,
    *,
    content: str = '{"ok":true}',
    model: str = "unit-model",
) -> tuple[OpenAICompatibleTextProvider, _FakeSdkClient]:
    client = _FakeSdkClient(content)
    provider = OpenAICompatibleTextProvider(
        base_url="https://example.test/v1",
        api_key="unit-test-secret",
        model=model,
        template_id=template_id,
        client=client,
    )
    return provider, client


def test_thinking_observability_treats_explicit_none_as_disabled() -> None:
    assert _request_thinking_enabled({"reasoning_effort": "none"}) is False
    assert _request_thinking_enabled({"reasoning_effort": "minimal"}) is True
    assert _request_thinking_enabled(
        {"extra_body": {"thinking": {"type": "enabled"}}}
    ) is True


@pytest.mark.asyncio
async def test_provider_exposes_standard_response_usage_for_budget_settlement() -> None:
    provider, _ = _provider("deepseek-text", content="潮声压住了最后一句辩解。")

    await provider.generate_text("prompt", task_name="text", context={})

    assert provider.last_usage == {
        "prompt_tokens": 21,
        "completion_tokens": 8,
        "total_tokens": 29,
    }


@pytest.mark.asyncio
async def test_provider_exposes_reasoning_usage_when_reported() -> None:
    client = _ReasoningUsageSdkClient("正文。")
    provider = OpenAICompatibleTextProvider(
        base_url="https://example.test/v1",
        api_key="unit-test-secret",
        model="deepseek-v4-flash",
        template_id="deepseek-text",
        client=client,
    )

    await provider.generate_text("prompt", task_name="text", context={})

    assert provider.last_usage["reasoning_tokens"] == 5
    assert provider_usage_snapshot(provider)["reasoning_tokens"] == 5


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"ok":true}\n```',
        '最终结果：{"ok":true}',
        '{"ok"：true}',
        '{"ok":true,}',
        '[{"ok":true}]',
    ],
)
def test_exact_json_parser_rejects_wrappers_repairs_and_non_objects(content: str) -> None:
    result = parse_exact_json_object_result(content)

    assert result.value is None
    assert result.diagnostic.repairs_applied == ()


def test_exact_json_parser_accepts_only_the_complete_object() -> None:
    result = parse_exact_json_object_result('  {"ok":true}  ')

    assert result.value == {"ok": True}
    assert result.diagnostic.selection == "exact_object"
    assert result.diagnostic.candidate_count == 1


def test_exact_json_parser_diagnostic_redacts_sensitive_key_names() -> None:
    result = parse_exact_json_object_result('{"api_key":"never-persist-this"}')

    assert result.value == {"api_key": "never-persist-this"}
    assert result.diagnostic.object_keys == (("[redacted-key]",),)
    assert "never-persist-this" not in str(result.diagnostic.as_dict())


@pytest.mark.asyncio
async def test_strict_structured_output_rejects_explanatory_wrapper() -> None:
    provider, _ = _provider(
        "openai-compatible-text",
        content='最终结果：{"ok":true}',
    )

    with pytest.raises(ProviderResponseError, match="exactly one complete JSON object"):
        await provider.generate_strict_structured(
            "return JSON",
            task_name="info",
            context={"idempotency_key": "strict-wrapper"},
            schema={"type": "object", "required": ["ok"]},
        )


def test_live_deepseek_text_evidence_fixture_matches_local_contract() -> None:
    fixture = json.loads(
        (
            Path(__file__).parent
            / "fixtures/provider_text_evidence_deepseek_v4_live.json"
        ).read_text()
    )
    content = fixture["content"]
    result = parse_exact_json_object_result(content)

    assert fixture["response_diagnostic"]["finish_reason"] == "stop"
    assert len(content) == fixture["response_diagnostic"]["response_chars"]
    assert hashlib.sha256(content.encode("utf-8")).hexdigest() == fixture["response_diagnostic"]["response_sha256"]
    assert result.value is not None
    assert result.diagnostic.selection == "exact_object"
    assert result.diagnostic.repairs_applied == ()


@pytest.mark.asyncio
async def test_non_json_structured_response_is_rejected() -> None:
    for content in (
        "以下是正文：" + "潮声逼近。" * 80,
        '{"chapter_title":"第2章","content":"未闭合"',
    ):
        provider = OpenAICompatibleTextProvider(
            base_url="https://example.test/v1",
            api_key="unit-test-secret",
            model="unit-model",
            client=_FakeSdkClient(content),
        )
        with pytest.raises(ProviderResponseError, match="JSON object"):
            await provider.generate_strict_structured(
                "prompt",
                task_name="text",
                context={},
                schema={"type": "object"},
            )


@pytest.mark.asyncio
async def test_structured_parse_failure_exposes_only_shape_diagnostics() -> None:
    private_response = "内部构思，不应写入事件。"
    provider, _ = _provider("deepseek-text", content=private_response)

    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_strict_structured(
            "return JSON",
            task_name="info",
            context={},
            schema={"type": "object", "required": ["selected_title"]},
        )

    details = raised.value.diagnostic_details
    assert details["finish_reason"] == "stop"
    assert details["response_chars"] == len(private_response)
    assert details["structured_parse"]["selection"] == "invalid_json"
    assert details["structured_parse"]["parsed_object_count"] == 0
    assert private_response not in str(details)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "template_id",
        "expected_format",
        "token_field",
        "sampling_fields",
        "expects_prompt_protocol",
    ),
    [
        ("openai-chat", "json_schema", "max_completion_tokens", set(), False),
        ("deepseek-text", "json_object", "max_tokens", {"temperature"}, True),
        ("xiaomi-mimo-api-text", "json_object", "max_completion_tokens", {"temperature"}, True),
        ("moonshot-text", "json_schema", "max_completion_tokens", set(), True),
        ("zhipu-text", "json_object", "max_tokens", {"temperature"}, True),
        ("zhipu-coding-plan", "json_object", "max_tokens", {"temperature"}, True),
        ("gemini-text", "json_schema", "max_tokens", set(), False),
    ],
)
async def test_vendor_templates_build_documented_structured_requests(
    template_id: str,
    expected_format: str,
    token_field: str,
    sampling_fields: set[str],
    expects_prompt_protocol: bool,
) -> None:
    provider, client = _provider(template_id)

    await provider.generate_strict_structured(
        "return data",
        task_name="summary",
        context={},
        schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
    )

    request = client.calls[0]
    assert request["response_format"]["type"] == expected_format
    assert token_field in request
    assert ({"temperature", "top_p"} & request.keys()) == sampling_fields
    assert ("JSON" in request["messages"][1]["content"]) is expects_prompt_protocol


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("template_id", "model", "expected_format", "expected_strict"),
    [
        ("siliconflow-text", "Qwen/Qwen3-8B", "json_object", None),
        ("openrouter-text", "openai/gpt-4.1-mini", "json_schema", True),
        ("groq-text", "openai/gpt-oss-120b", "json_schema", True),
        ("groq-text", "qwen/qwen3.6-27b", "json_object", None),
        ("together-text", "openai/gpt-oss-120b", "json_schema", False),
        ("xai-text", "grok-4.5", "json_schema", True),
        ("mistral-text", "mistral-large-latest", "json_schema", False),
        ("fireworks-text", "accounts/fireworks/models/gpt-oss-120b", "json_schema", False),
        ("cerebras-text", "gpt-oss-120b", "json_schema", True),
        ("tokenhub-text", "deepseek-v4-pro", "json_object", None),
    ],
)
async def test_compatibility_vendor_structured_output_is_model_aware(
    template_id: str,
    model: str,
    expected_format: str,
    expected_strict: bool | None,
) -> None:
    provider, client = _provider(template_id, model=model)

    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="summary",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    response_format = client.calls[0]["response_format"]
    assert response_format["type"] == expected_format
    if expected_strict is not None:
        assert response_format["json_schema"]["strict"] is expected_strict


@pytest.mark.asyncio
async def test_openrouter_requires_an_upstream_that_supports_all_parameters() -> None:
    provider, client = _provider("openrouter-text", model="openai/gpt-4.1-mini")
    await provider.generate_strict_structured(
        "return JSON",
        task_name="summary",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    assert client.calls[0]["extra_body"]["provider"] == {
        "require_parameters": True,
        "allow_fallbacks": False,
    }


@pytest.mark.asyncio
async def test_dashscope_structured_request_omits_max_tokens_per_official_contract() -> None:
    provider, client = _provider("dashscope-text")

    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="summary",
        context={},
        schema={"type": "object"},
    )

    request = client.calls[0]
    assert request["response_format"] == {"type": "json_object"}
    assert "max_tokens" not in request
    assert "max_completion_tokens" not in request


@pytest.mark.asyncio
async def test_qwen_37_plus_streams_thinking_for_complex_structured_stages() -> None:
    detail_provider, detail_client = _provider(
        "dashscope-text",
        model="qwen3.7-plus",
    )
    await detail_provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )
    prose_provider, prose_client = _provider(
        "dashscope-text",
        content="潮线继续向堤岸逼近。",
        model="qwen3.7-plus",
    )
    await prose_provider.generate_text("write", task_name="text", context={})

    detail_request = detail_client.calls[0]
    assert detail_request["stream"] is True
    assert detail_request["extra_body"] == {
        "enable_thinking": True,
        "thinking_budget": 12288,
    }
    assert "max_tokens" not in detail_request
    assert "max_completion_tokens" not in detail_request
    assert prose_client.calls[0]["stream"] is False
    assert prose_client.calls[0]["extra_body"] == {"enable_thinking": False}


@pytest.mark.asyncio
async def test_qwen_37_flash_uses_documented_json_mode_without_max_tokens() -> None:
    provider, client = _provider("dashscope-text", model="qwen3.7-flash")

    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["stream"] is True
    assert request["extra_body"] == {
        "enable_thinking": True,
        "thinking_budget": 8192,
    }
    assert request["response_format"] == {"type": "json_object"}
    assert "max_tokens" not in request
    assert "max_completion_tokens" not in request


@pytest.mark.asyncio
async def test_qwen_36_flash_keeps_the_compatible_thinking_profile() -> None:
    provider, client = _provider("dashscope-text", model="qwen3.6-flash")

    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["stream"] is True
    assert request["extra_body"] == {
        "enable_thinking": True,
        "thinking_budget": 8192,
    }


@pytest.mark.asyncio
async def test_deepseek_stage_policy_reserves_budget_for_structured_artifacts() -> None:
    prose_provider, prose_client = _provider("deepseek-text", content="正文继续。", model="deepseek-v4-pro")
    await prose_provider.generate_text("write", task_name="text", context={})
    outline_provider, outline_client = _provider("deepseek-text", model="deepseek-v4-pro")
    await outline_provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="outline",
        context={},
        schema={"type": "object"},
    )
    detail_provider, detail_client = _provider("deepseek-text", model="deepseek-v4-pro")
    await detail_provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object"},
    )

    assert prose_client.calls[0]["extra_body"]["thinking"] == {"type": "disabled"}
    assert prose_client.calls[0]["temperature"] == 0.2
    assert "reasoning_effort" not in prose_client.calls[0]
    assert outline_client.calls[0]["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in outline_client.calls[0]
    assert outline_client.calls[0]["temperature"] == 0.2
    assert detail_client.calls[0]["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in detail_client.calls[0]
    assert detail_client.calls[0]["temperature"] == 0.2


@pytest.mark.asyncio
async def test_internal_override_disables_deepseek_thinking_for_review() -> None:
    provider, client = _provider("deepseek-text", model="deepseek-v4-flash")

    await provider.generate_strict_structured(
        'return JSON data like {"findings":[]}',
        task_name="text.review",
        context={"_thinking_override": "disabled"},
        schema={"type": "object"},
    )

    request = client.calls[0]
    assert request["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in request
    assert request["temperature"] == 0.2
    assert request["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_deepseek_semantic_review_reserves_its_budget_for_json_output() -> None:
    provider, client = _provider(
        "deepseek-text",
        model="deepseek-v4-flash",
    )

    await provider.generate_strict_structured(
        'return compact JSON data like {"ok":true}',
        task_name="text.review",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["response_format"] == {"type": "json_object"}
    assert request["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in request
    assert request["temperature"] == 0.2


@pytest.mark.asyncio
async def test_internal_override_disables_deepseek_thinking_for_causal_audit() -> None:
    provider, client = _provider("deepseek-text", model="deepseek-v4-flash")

    await provider.generate_strict_structured(
        'return JSON data like {"contract_checks":[]}',
        task_name="text.review",
        context={
            "review_focus": "causal_fact",
            "_thinking_override": "disabled",
        },
        schema={"type": "object"},
    )

    request = client.calls[0]
    assert request["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in request
    assert request["temperature"] == 0.2


@pytest.mark.asyncio
async def test_internal_enable_marker_cannot_reenable_template_disabled_review_thinking() -> None:
    provider, client = _provider("deepseek-text", model="deepseek-v4-flash")

    await provider.generate_strict_structured(
        'return JSON data like {"findings":[]}',
        task_name="text.review",
        context={"_thinking_override": "enabled"},
        schema={"type": "object"},
    )

    request = client.calls[0]
    assert request["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in request
    assert request["response_format"] == {"type": "json_object"}
    assert request["temperature"] == 0.2


@pytest.mark.asyncio
async def test_deepseek_disables_thinking_for_narrow_evidence() -> None:
    provider, client = _provider("deepseek-text", model="deepseek-v4-pro")

    await provider.generate_strict_structured(
        'return JSON data like {"patches":[]}',
        task_name="text.evidence",
        context={},
        schema={"type": "object"},
    )

    request = client.calls[0]
    assert request["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in request
    assert request["temperature"] == 0.2


@pytest.mark.asyncio
async def test_deepseek_reasoning_effort_is_matched_to_the_selected_model() -> None:
    flash_provider, flash_client = _provider("deepseek-text", model="deepseek-v4-flash")
    await flash_provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="info",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    assert flash_client.calls[0]["reasoning_effort"] == "high"
    assert flash_client.calls[0]["extra_body"]["thinking"] == {"type": "enabled"}


@pytest.mark.asyncio
async def test_existing_json_output_contract_is_not_appended_twice() -> None:
    provider, client = _provider("deepseek-text", model="deepseek-v4-flash")

    await provider.generate_strict_structured(
        '## JSON 输出示例\n只返回合法 JSON object，例如 {"ok":true}',
        task_name="text.review",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    prompt = client.calls[0]["messages"][1]["content"]
    assert prompt.count("## JSON 输出示例") == 1
    assert "## JSON 输出协议" not in prompt


@pytest.mark.asyncio
async def test_deepseek_structured_review_tasks_disable_thinking_by_default() -> None:
    provider, client = _provider("deepseek-text", model="deepseek-v4-flash")

    await provider.generate_strict_structured(
        'return JSON data like {"ok":true}',
        task_name="text.review",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in request
    assert request["response_format"] == {"type": "json_object"}
    assert request["temperature"] == 0.2


@pytest.mark.asyncio
async def test_deepseek_summary_reserves_budget_but_prose_remains_non_thinking() -> None:
    summary_provider, summary_client = _provider("deepseek-text", model="deepseek-v4-pro")
    await summary_provider.generate_strict_structured(
        'return JSON data like {"ok":true}',
        task_name="summary",
        context={},
        schema={"type": "object"},
    )
    prose_provider, prose_client = _provider("deepseek-text", content="正文。", model="deepseek-v4-pro")
    await prose_provider.generate_text("write", task_name="text", context={})

    assert summary_client.calls[0]["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in summary_client.calls[0]
    assert prose_client.calls[0]["extra_body"]["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("template_id", "model"),
    [("deepseek-text", "deepseek-v4-pro"), ("zhipu-text", "glm-5.2")],
)
async def test_unlisted_tasks_explicitly_disable_provider_default_thinking(
    template_id: str,
    model: str,
) -> None:
    provider, client = _provider(template_id, content="连接正常。", model=model)

    await provider.generate_text("check", task_name="provider_smoke_test", context={})

    request = client.calls[0]
    assert request["extra_body"]["thinking"] == {"type": "disabled"}
    assert request["temperature"] == 0.2
    assert "reasoning_effort" not in request


@pytest.mark.asyncio
async def test_mimo_pro_thinking_is_reserved_for_complex_planning_and_review() -> None:
    detail_provider, detail_client = _provider(
        "xiaomi-mimo-api-text",
        model="mimo-v2.5-pro",
    )
    await detail_provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object"},
    )
    prose_provider, prose_client = _provider(
        "xiaomi-mimo-api-text",
        content="正文继续。",
        model="mimo-v2.5-pro",
    )
    await prose_provider.generate_text("write", task_name="text", context={})

    assert detail_client.calls[0]["extra_body"]["thinking"] == {"type": "enabled"}
    assert "temperature" not in detail_client.calls[0]
    assert prose_client.calls[0]["extra_body"]["thinking"] == {"type": "disabled"}
    assert prose_client.calls[0]["temperature"] == 0.2


@pytest.mark.asyncio
async def test_kimi_k26_uses_documented_schema_and_completion_contract() -> None:
    provider, client = _provider("moonshot-text", model="kimi-k2.6")
    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["response_format"]["json_schema"]["strict"] is False
    assert "reasoning_effort" not in request
    assert request["extra_body"]["thinking"] == {"type": "disabled"}
    assert "max_completion_tokens" in request
    assert "temperature" not in request


@pytest.mark.asyncio
async def test_qwen_37_max_uses_documented_json_mode_without_max_tokens() -> None:
    provider, client = _provider("dashscope-text", model="qwen3.7-max")

    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["stream"] is True
    assert request["response_format"] == {"type": "json_object"}
    assert request["extra_body"] == {
        "enable_thinking": True,
        "thinking_budget": 16384,
    }
    assert "max_tokens" not in request
    assert "max_completion_tokens" not in request


@pytest.mark.asyncio
async def test_glm_reasoning_effort_is_only_sent_to_glm_5_2() -> None:
    glm_52, glm_52_client = _provider("zhipu-text", model="glm-5.2")
    await glm_52.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object"},
    )
    await glm_52.generate_strict_structured(
        'return JSON data like {"ok":true}',
        task_name="text.review",
        context={},
        schema={"type": "object"},
    )
    glm_51, glm_51_client = _provider("zhipu-text", model="glm-5.1")
    await glm_51.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object"},
    )

    assert glm_52_client.calls[0]["reasoning_effort"] == "high"
    assert glm_52_client.calls[0]["stream"] is True
    assert glm_52_client.calls[0]["extra_body"]["thinking"] == {"type": "enabled"}
    assert glm_52_client.calls[1]["reasoning_effort"] == "high"
    assert glm_52_client.calls[1]["extra_body"]["thinking"] == {"type": "enabled"}
    assert "reasoning_effort" not in glm_51_client.calls[0]
    assert glm_51_client.calls[0]["extra_body"]["thinking"] == {"type": "enabled"}


@pytest.mark.asyncio
async def test_xai_grok_uses_stage_reasoning_with_strict_schema() -> None:
    provider, client = _provider("xai-text", model="grok-4.5")
    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    assert client.calls[0]["reasoning_effort"] == "high"
    assert client.calls[0]["response_format"]["json_schema"]["strict"] is True


@pytest.mark.asyncio
async def test_groq_uses_completion_token_field_for_gpt_oss() -> None:
    provider, client = _provider("groq-text", model="openai/gpt-oss-120b")

    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert "max_completion_tokens" in request
    assert "max_tokens" not in request
    assert request["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_groq_qwen_uses_hidden_reasoning_for_complex_json_stages() -> None:
    provider, client = _provider("groq-text", model="qwen/qwen3.6-27b")

    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["reasoning_effort"] == "default"
    assert request["reasoning_format"] == "hidden"
    assert request["response_format"] == {"type": "json_object"}
    assert request["temperature"] == 0.2
    assert request["top_p"] == 0.95


@pytest.mark.asyncio
async def test_groq_qwen_disables_reasoning_for_summary_and_prose() -> None:
    summary, summary_client = _provider("groq-text", model="qwen/qwen3.6-27b")
    await summary.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="summary",
        context={},
        schema={"type": "object"},
    )
    prose, prose_client = _provider(
        "groq-text",
        model="qwen/qwen3.6-27b",
        content="正文继续。",
    )
    await prose.generate_text("write", task_name="text", context={})

    assert summary_client.calls[0]["reasoning_effort"] == "none"
    assert "reasoning_format" not in summary_client.calls[0]
    assert prose_client.calls[0]["reasoning_effort"] == "none"
    assert "reasoning_format" not in prose_client.calls[0]


@pytest.mark.asyncio
async def test_gemini_flash_lite_uses_minimal_effort_only_on_its_template() -> None:
    lite, lite_client = _provider("gemini-text", model="gemini-3.5-flash-lite")
    await lite.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="summary",
        context={},
        schema={"type": "object"},
    )
    flash, flash_client = _provider("gemini-text", model="gemini-3.6-flash")
    await flash.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="summary",
        context={},
        schema={"type": "object"},
    )

    assert lite_client.calls[0]["reasoning_effort"] == "minimal"
    assert flash_client.calls[0]["reasoning_effort"] == "low"


@pytest.mark.asyncio
@pytest.mark.parametrize("template_id", ["moonshot-text", "mistral-text"])
async def test_supported_prompt_cache_templates_send_a_stable_hashed_key(
    template_id: str,
) -> None:
    provider, client = _provider(template_id)
    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="summary",
        context={"_prompt_cache_key": "run-42:summary"},
        schema={"type": "object"},
    )

    assert client.calls[0]["prompt_cache_key"] == hashlib.sha256(
        b"run-42:summary"
    ).hexdigest()
    assert "x-grok-conv-id" not in client.calls[0]["extra_headers"]


@pytest.mark.asyncio
async def test_xai_chat_cache_key_uses_documented_header_not_request_body() -> None:
    provider, client = _provider("xai-text", model="grok-4.5")
    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="summary",
        context={"_prompt_cache_key": "run-42:summary"},
        schema={"type": "object"},
    )

    request = client.calls[0]
    assert request["extra_headers"]["x-grok-conv-id"] == hashlib.sha256(
        b"run-42:summary"
    ).hexdigest()
    assert "prompt_cache_key" not in request


@pytest.mark.asyncio
async def test_deepseek_does_not_receive_prompt_cache_key_without_documented_support() -> None:
    provider, client = _provider("deepseek-text")
    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="summary",
        context={"_prompt_cache_key": "run-42:summary"},
        schema={"type": "object"},
    )

    assert "prompt_cache_key" not in client.calls[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_name", "expected_effort"),
    [
        ("summary", "low"),
        ("outline", "medium"),
        ("detail", "high"),
        ("text", "low"),
        ("text.review", "high"),
    ],
)
async def test_together_gpt_oss_uses_stage_reasoning_effort(
    task_name: str,
    expected_effort: str,
) -> None:
    provider, client = _provider("together-text", model="openai/gpt-oss-120b")

    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name=task_name,
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["reasoning_effort"] == expected_effort
    assert "temperature" not in request
    assert "top_p" not in request


@pytest.mark.asyncio
async def test_anthropic_compatibility_does_not_claim_response_format() -> None:
    provider, client = _provider("anthropic-openai-text", model="claude-sonnet-5")
    await provider.generate_strict_structured(
        "return JSON data like {\"ok\":true}",
        task_name="summary",
        context={},
        schema={"type": "object"},
    )

    assert "response_format" not in client.calls[0]
    assert "reasoning_effort" not in client.calls[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "template_id",
    [
        "openai-compatible-text",
        "volcengine-ark-text",
        "litellm-proxy-text",
        "portkey-gateway-text",
    ],
)
async def test_unknown_upstream_templates_use_prompt_only_json_contract(
    template_id: str,
) -> None:
    provider, client = _provider(template_id)

    await provider.generate_strict_structured(
        "return the stage artifact",
        task_name="summary",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert "response_format" not in request
    assert "JSON 格式示例" in request["messages"][1]["content"]


@pytest.mark.asyncio
async def test_openai_schema_is_normalized_before_strict_structured_request() -> None:
    provider, client = _provider("openai-chat", model="gpt-5.6-terra")
    await provider.generate_strict_structured(
        "return data",
        task_name="summary",
        context={},
        schema={
            "type": "object",
            "properties": {"title": {"type": "string", "minLength": 1, "default": ""}},
        },
    )

    json_schema = client.calls[0]["response_format"]["json_schema"]
    assert json_schema["strict"] is True
    assert json_schema["schema"]["required"] == ["title"]
    assert json_schema["schema"]["additionalProperties"] is False
    assert "minLength" not in json_schema["schema"]["properties"]["title"]
    assert "default" not in json_schema["schema"]["properties"]["title"]


@pytest.mark.asyncio
async def test_incompatible_schema_is_rejected_before_any_provider_request() -> None:
    provider, client = _provider("openai-chat", model="gpt-5.6-terra")
    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_strict_structured(
            "return JSON",
            task_name="summary",
            context={},
            schema={"type": "array", "items": {"type": "string"}},
        )

    assert raised.value.code == "strict_schema_unsupported"
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsupported_schema",
    [
        {"type": "object", "properties": {"value": False}},
        {"type": "object", "properties": {"value": {"type": "string", "enum": []}}},
        {"type": "object", "properties": {"value": {"anyOf": []}}},
        {"type": "object", "properties": {"value": {"$ref": "https://example.com/schema.json"}}},
    ],
)
async def test_rejected_schema_shapes_fail_before_request(
    unsupported_schema: dict[str, object],
) -> None:
    provider, client = _provider("xai-text", model="grok-4.5")

    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_strict_structured(
            "return JSON",
            task_name="summary",
            context={},
            schema=unsupported_schema,
        )

    assert raised.value.code == "strict_schema_unsupported"
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("template_id", ["together-text", "fireworks-text"])
async def test_schema_definition_is_repeated_in_prompt_when_vendor_requires_it(
    template_id: str,
) -> None:
    provider, client = _provider(template_id)
    schema = {
        "type": "object",
        "properties": {"artifact_title": {"type": "string"}},
    }

    await provider.generate_strict_structured(
        "return the stage artifact",
        task_name="summary",
        context={},
        schema=schema,
    )

    prompt = client.calls[0]["messages"][1]["content"]
    assert "JSON Schema" in prompt
    assert '"artifact_title":{"type":"string"}' in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("template_id", ["together-text", "fireworks-text"])
async def test_required_schema_is_not_skipped_by_an_existing_json_example(
    template_id: str,
) -> None:
    provider, client = _provider(template_id)
    schema = {
        "type": "object",
        "properties": {"artifact_title": {"type": "string"}},
    }

    await provider.generate_strict_structured(
        '## 输出结构\n只返回 JSON，例如 {"ok":true}',
        task_name="summary",
        context={},
        schema=schema,
    )

    prompt = client.calls[0]["messages"][1]["content"]
    assert "JSON Schema" in prompt
    assert '"artifact_title":{"type":"string"}' in prompt


@pytest.mark.asyncio
async def test_kimi_k3_uses_documented_stage_reasoning_and_schema_contract() -> None:
    provider, client = _provider("moonshot-text", model="kimi-k3")

    await provider.generate_strict_structured(
        "提取当前阶段产物",
        task_name="summary",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert "max_completion_tokens" in request
    assert "max_tokens" not in request
    assert "JSON 格式示例" in request["messages"][1]["content"]
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["reasoning_effort"] == "low"
    assert "extra_body" not in request


@pytest.mark.asyncio
async def test_siliconflow_json_object_prompt_uses_example_without_full_schema() -> None:
    provider, client = _provider("siliconflow-text", model="Qwen/Qwen3-8B")

    await provider.generate_strict_structured(
        "return the stage artifact",
        task_name="summary",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    prompt = client.calls[0]["messages"][1]["content"]
    assert "JSON 格式示例" in prompt
    assert "JSON Schema" not in prompt


@pytest.mark.asyncio
async def test_cerebras_oversized_schema_is_rejected_before_request() -> None:
    provider, client = _provider("cerebras-text", model="gpt-oss-120b")
    properties = {
        f"field_{index:03d}": {
            "type": "string",
            "description": "结构化阶段字段说明" * 8,
        }
        for index in range(80)
    }

    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_strict_structured(
            "return JSON",
            task_name="summary",
            context={},
            schema={"type": "object", "properties": properties},
        )

    assert raised.value.code == "strict_schema_unsupported"
    assert client.calls == []


@pytest.mark.asyncio
async def test_cerebras_excessive_enum_values_are_rejected_before_request() -> None:
    provider, client = _provider("cerebras-text", model="gpt-oss-120b")

    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_strict_structured(
            "return JSON",
            task_name="summary",
            context={},
            schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "enum": [str(index) for index in range(501)]},
                },
            },
        )

    assert raised.value.code == "strict_schema_unsupported"
    assert client.calls == []


@pytest.mark.asyncio
async def test_deepseek_documented_structured_empty_content_is_visible_without_hidden_retry() -> None:
    provider, client = _provider("deepseek-text", content="")

    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_strict_structured(
            "return JSON data like {\"ok\":true}",
            task_name="summary",
            context={},
            schema={"type": "object"},
        )

    assert raised.value.code == "structured_empty_content"
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_deepseek_reasoning_only_structured_response_has_diagnostic_without_exposing_reasoning() -> None:
    client = _ReasoningOnlySdkClient("")
    provider = OpenAICompatibleTextProvider(
        base_url="https://example.test/v1",
        api_key="unit-test-secret",
        model="deepseek-v4-flash",
        template_id="deepseek-text",
        client=client,
    )

    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_strict_structured(
            'return JSON data like {"ok":true}',
            task_name="text.review",
            context={},
            schema={"type": "object"},
        )

    assert raised.value.code == "structured_empty_content"
    assert raised.value.diagnostic_code == "reasoning_only_content_empty"
    assert raised.value.partial_content == ""
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_structured_parse_failure_preserves_provider_content_for_local_revalidation() -> None:
    raw = "分析草稿，没有 JSON 对象。"
    provider, _ = _provider("deepseek-text", content=raw)

    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_strict_structured(
            'return JSON data like {"ok":true}',
            task_name="text.review",
            context={},
            schema={"type": "object"},
        )

    assert raised.value.code == "json_parse_failed"
    assert raised.value.partial_content == raw


@pytest.mark.asyncio
async def test_deepseek_prefix_completion_requires_explicit_text_context_and_beta_client() -> None:
    primary = _FakeSdkClient("unused")
    beta = _FakeSdkClient("潮声从门缝里继续涌进来。")
    provider = OpenAICompatibleTextProvider(
        base_url="https://api.deepseek.com",
        api_key="unit-test-secret",
        model="deepseek-v4-pro",
        template_id="deepseek-text",
        client=primary,
        prefill_client=beta,
    )

    prefix = "门外的潮声没有停。\n"
    result = await provider.generate_text(
        "续写当前场景",
        task_name="text",
        context={"_assistant_prefill": prefix},
    )

    assert result == "潮声从门缝里继续涌进来。"
    assert primary.calls == []
    assert beta.calls[0]["messages"][-1] == {
        "role": "assistant",
        "content": prefix,
        "prefix": True,
    }


@pytest.mark.asyncio
async def test_assistant_prefill_is_rejected_outside_explicit_prose_tasks() -> None:
    provider, client = _provider("deepseek-text", model="deepseek-v4-pro")

    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_text(
            "check provider",
            task_name="provider_smoke_test",
            context={"_assistant_prefill": "固定开头"},
        )

    assert raised.value.code == "unsupported_assistant_prefill"
    assert client.calls == []


@pytest.mark.asyncio
async def test_kimi_partial_mode_cannot_mix_with_structured_output() -> None:
    provider, _ = _provider("moonshot-text")

    with pytest.raises(ProviderResponseError) as raised:
        await provider.generate_strict_structured(
            "return JSON",
            task_name="summary",
            context={"_assistant_prefill": "{"},
            schema={"type": "object"},
        )

    assert raised.value.code == "provider_feature_conflict"


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["kimi-k3", "kimi-k2.6"])
async def test_kimi_partial_restores_the_omitted_prefix_for_documented_models(model: str) -> None:
    provider, client = _provider(
        "moonshot-text",
        content="潮声继续逼近。",
        model=model,
    )

    result = await provider.generate_text(
        "续写当前场景",
        task_name="text",
        context={"_assistant_prefill": "门外没有人，"},
    )

    assert result == "门外没有人，潮声继续逼近。"
    assert client.calls[0]["messages"][-1] == {
        "role": "assistant",
        "content": "门外没有人，",
        "partial": True,
    }


@pytest.mark.asyncio
async def test_tokenhub_kimi_k3_uses_gateway_specific_fixed_parameters() -> None:
    provider, client = _provider("tokenhub-text", model="kimi-k3")

    await provider.generate_strict_structured(
        "return JSON",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["max_completion_tokens"] > 0
    assert "max_tokens" not in request
    assert "temperature" not in request
    assert "top_p" not in request
    assert request["reasoning_effort"] == "max"
    assert request["response_format"]["json_schema"]["strict"] is True


@pytest.mark.asyncio
async def test_tokenhub_glm_52_keeps_reasoning_inside_gateway_extra_body() -> None:
    provider, client = _provider("tokenhub-text", model="glm-5.2")

    await provider.generate_strict_structured(
        "return JSON",
        task_name="detail",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    assert request["extra_body"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "max",
    }
    assert "temperature" not in request
    assert request["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "expected_format", "expected_extra_body"),
    [
        ("deepseek-v4-pro", "json_object", {"thinking": {"type": "disabled"}}),
        ("minimax-m3", "json_object", {"thinking": {"type": "disabled"}}),
        ("minimax-m2.7", None, {"reasoning_split": True}),
    ],
)
async def test_tokenhub_model_families_avoid_unsupported_structured_thinking_combinations(
    model: str,
    expected_format: str | None,
    expected_extra_body: dict[str, object],
) -> None:
    provider, client = _provider("tokenhub-text", model=model)

    await provider.generate_strict_structured(
        "return JSON",
        task_name="summary",
        context={},
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    request = client.calls[0]
    if expected_format is None:
        assert "response_format" not in request
    else:
        assert request["response_format"] == {"type": expected_format}
    assert request["extra_body"] == expected_extra_body


@pytest.mark.asyncio
async def test_mistral_prefix_is_available_only_for_explicit_plain_text_prose() -> None:
    provider, client = _provider(
        "mistral-text",
        content="潮声继续逼近。",
        model="mistral-large-latest",
    )

    result = await provider.generate_text(
        "续写当前场景",
        task_name="text",
        context={"_assistant_prefill": "门外没有人，"},
    )

    assert result == "潮声继续逼近。"
    assert client.calls[0]["messages"][-1] == {
        "role": "assistant",
        "content": "门外没有人，",
        "prefix": True,
    }
