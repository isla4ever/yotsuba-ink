from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from novel_workflow.knowledge import KnowledgeSearchRequest
from novel_workflow.references import ReferenceSearchRequest


def enrich_reference_summary(app: FastAPI, inputs: dict[str, Any]) -> None:
    inputs["rag_events"] = []
    stage_configs = inputs.get("stage_configs")
    if not isinstance(stage_configs, dict):
        return
    info = stage_configs.get("info")
    if not isinstance(info, dict):
        return
    mode = str(info.get("reference_mode") or "smart_search")
    project_id = str(inputs.get("project_id") or "default")
    if mode == "smart_search":
        keywords = string_list(info.get("reference_keywords"))
        intent = str(info.get("reference_query_intent") or "")
        query = " ".join(keywords) or intent or "类型小说 创作 参考"
        append_rag_event(app, inputs, {"type": "reference_collection_started", "source": "smart_search", "query": query, "intent": intent})
        web_results: list[Any] = []
        web_message = ""
        if info.get("enable_web_search", True):
            append_rag_event(app, inputs, {"type": "web_search_started", "query": query, "intent": intent})
            web_response = app.state.reference_search.search(ReferenceSearchRequest(query=query, max_results=3, search_depth="basic"))
            web_results = list(web_response.results)
            web_message = web_response.message
            append_rag_event(
                app,
                inputs,
                {
                    "type": "web_results_found",
                    "enabled": web_response.enabled,
                    "message": web_response.message,
                    "results": [item.model_dump() for item in web_response.results],
                },
            )
            for item in web_results[:3]:
                append_rag_event(app, inputs, {"type": "reference_source_found", "source": "web", "title": item.title, "url": item.url, "score": item.score})
        append_rag_event(app, inputs, {"type": "rag_query_started", "query": query, "intent": intent})
        kb_response = app.state.knowledge_base.search(KnowledgeSearchRequest(query=query, intent=intent, project_id=project_id, top_k=5))
        append_rag_event(app, inputs, {"type": "rag_results_found", "backend": kb_response.backend, "query_rewrite": kb_response.query_rewrite, "results": [item.model_dump() for item in kb_response.results]})
        for item in kb_response.results[:5]:
            append_rag_event(app, inputs, {"type": "reference_source_found", "source": "knowledge_base", "title": item.title, "section": item.section, "score": item.score})
        info["reference_summary"] = merged_reference_summary(
            web_results=web_results,
            knowledge_results=kb_response.results,
            web_message=web_message,
            knowledge_message=kb_response.message,
            intent=intent,
        )
        append_rag_event(app, inputs, {"type": "reference_understanding_completed", "source": "merged", "message": "已提炼参考资料的结构、节奏、题材约束和风险点。"})
        append_rag_event(app, inputs, {"type": "reference_context_merged", "summary": info["reference_summary"]})
        append_rag_event(app, inputs, {"type": "reference_context_injected", "target": "story_brief", "summary": info["reference_summary"]})
        return

    if mode == "url":
        urls = string_list(info.get("reference_urls"))
        append_rag_event(app, inputs, {"type": "reference_collection_started", "source": "url", "urls": urls})
        info["reference_summary"] = summary_from_urls(urls)
        for url in urls[:5]:
            append_rag_event(app, inputs, {"type": "reference_source_found", "source": "url", "url": url})
        append_rag_event(app, inputs, {"type": "reference_understanding_completed", "source": "url", "message": "已抽取指定链接中的可参考结构与限制。"})
        append_rag_event(app, inputs, {"type": "reference_context_injected", "target": "story_brief", "summary": info["reference_summary"]})
        return

    if mode == "knowledge_base":
        keywords = string_list(info.get("reference_keywords"))
        intent = str(info.get("reference_query_intent") or "")
        query = intent or " ".join(keywords) or str(info.get("core_concept") or info.get("genre") or "小说参考")
        append_rag_event(app, inputs, {"type": "reference_collection_started", "source": "knowledge_base", "query": query, "intent": intent})
        append_rag_event(app, inputs, {"type": "rag_query_started", "query": query, "intent": intent})
        response = app.state.knowledge_base.search(
            KnowledgeSearchRequest(query=query, intent=intent, project_id=project_id, doc_ids=string_list(info.get("knowledge_base_doc_ids")), top_k=6)
        )
        append_rag_event(app, inputs, {"type": "rag_results_found", "backend": response.backend, "query_rewrite": response.query_rewrite, "results": [item.model_dump() for item in response.results]})
        for item in response.results[:6]:
            append_rag_event(app, inputs, {"type": "reference_source_found", "source": "knowledge_base", "title": item.title, "section": item.section, "score": item.score})
        info["reference_summary"] = summary_from_knowledge_results(response.results, fallback=response.message)
        append_rag_event(app, inputs, {"type": "reference_understanding_completed", "source": "knowledge_base", "message": "已从用户私有资料中提炼可注入 Brief 的事实、风格和约束。"})
        append_rag_event(app, inputs, {"type": "reference_context_merged", "summary": info["reference_summary"]})
        append_rag_event(app, inputs, {"type": "reference_context_injected", "target": "story_brief", "summary": info["reference_summary"]})


def summary_from_search_results(results: list[Any]) -> str:
    return "\n\n".join(f"{index}. {item.title}\n{item.content}\nURL: {item.url}" for index, item in enumerate(results, start=1))


def merged_reference_summary(
    *,
    web_results: list[Any],
    knowledge_results: list[Any],
    web_message: str,
    knowledge_message: str,
    intent: str,
) -> str:
    sections = []
    if web_results or web_message:
        sections.append(f"联网参考（优先）\n{summary_from_search_results(web_results) or web_message}")
    if knowledge_results or knowledge_message:
        sections.append(f"用户知识库命中（补充）\n{summary_from_knowledge_results(knowledge_results, fallback=knowledge_message)}")
    if intent:
        sections.append(f"检索意图\n{intent}")
    return "\n\n".join(section for section in sections if section.strip())


def summary_from_knowledge_results(results: list[Any], fallback: str = "") -> str:
    if results:
        return "\n\n".join(
            f"{index}. {item.title}{f' / {item.section}' if item.section else ''}\n{compact(getattr(item, 'content', getattr(item, 'preview', '')), 420)}"
            for index, item in enumerate(results, start=1)
        )
    return fallback or "知识库暂无命中。"


def summary_from_urls(urls: list[str]) -> str:
    return "\n".join(f"- {url}" for url in urls) if urls else "未提供指定链接。"


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.splitlines() if item.strip()]
    return []


def compact(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    return clean if len(clean) <= limit else f"{clean[:limit]}..."


def rag_blocking_issue(app: FastAPI, inputs: dict[str, Any]) -> str:
    stage_configs = inputs.get("stage_configs")
    if not isinstance(stage_configs, dict):
        return ""
    info = stage_configs.get("info")
    if not isinstance(info, dict):
        return ""
    mode = str(info.get("reference_mode") or "smart_search")
    enable_web = bool(info.get("enable_web_search", True))
    if mode == "smart_search" and enable_web:
        return ""
    project_id = str(inputs.get("project_id") or "default")
    has_docs = bool(app.state.knowledge_base.list_documents(project_id))
    selected_docs = string_list(info.get("knowledge_base_doc_ids"))
    if has_docs or selected_docs:
        return ""
    return "当前参考模式需要知识库资料，但项目知识库为空。请先上传背景设定、人物小传或参考资料。"


def append_rag_event(app: FastAPI, inputs: dict[str, Any], event: dict[str, Any]) -> None:
    del app
    inputs.setdefault("rag_events", []).append(event)
