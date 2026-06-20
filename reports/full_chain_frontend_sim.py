import base64
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8090/front"
USER_ID = 507453444
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_DIR = ROOT / "full_chain_frontend_sim" / STAMP
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TITLE = f"雾港回声档案-联调-{STAMP}"
TAGS = [{"id": 1, "name": "悬疑", "isShow": 1, "categoryId": 1}]
KEYWORDS = ["港口旧档案", "群像悬疑", "城市异能", "失踪案", "关系网反转"]


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_token(user_id: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": "auth0",
        "userId": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(days=3)).timestamp()),
    }
    signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    sig = hmac.new(b"txdy", signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(sig)}"


TOKEN = make_token(USER_ID)
HEADERS = {"Authorization": TOKEN, "Content-Type": "application/json;charset=utf-8"}


raw: Dict[str, Any] = {"started_at": STAMP, "user_id": USER_ID, "title": TITLE, "stages": {}}
metrics: Dict[str, Any] = {"stages": {}, "chapters": [], "totals": {}}
issues: List[Dict[str, str]] = []


def add_issue(stage: str, severity: str, message: str) -> None:
    issues.append({"stage": stage, "severity": severity, "message": message})


def compact(text: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def timed_request(stage: str, method: str, path: str, **kwargs: Any) -> requests.Response:
    url = f"{BASE_URL}{path}"
    start = time.time()
    resp = requests.request(method, url, headers=HEADERS, timeout=kwargs.pop("timeout", 1800), **kwargs)
    elapsed = round(time.time() - start, 2)
    metrics["stages"][stage] = {"status_code": resp.status_code, "elapsed_seconds": elapsed}
    raw["stages"][stage] = {
        "request": {"method": method, "path": path, "kwargs": safe_kwargs(kwargs)},
        "status_code": resp.status_code,
        "elapsed_seconds": elapsed,
        "body_excerpt": resp.text[:1200],
    }
    if resp.status_code >= 400:
        add_issue(stage, "fail", f"HTTP {resp.status_code}: {resp.text[:500]}")
    return resp


def safe_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    copied = dict(kwargs)
    if "headers" in copied:
        copied["headers"] = "<headers>"
    return copied


def response_data(resp: requests.Response, stage: str) -> Any:
    try:
        obj = resp.json()
    except Exception as exc:
        add_issue(stage, "fail", f"invalid JSON: {exc}")
        return None
    raw["stages"][stage]["response"] = obj
    if isinstance(obj, dict) and obj.get("code") not in (None, 200):
        add_issue(stage, "fail", f"business code={obj.get('code')} msg={obj.get('msg') or obj.get('message')}")
    return obj.get("data") if isinstance(obj, dict) and "data" in obj else obj


def post_json(stage: str, path: str, payload: Dict[str, Any]) -> Any:
    resp = timed_request(stage, "POST", path, json=payload)
    return response_data(resp, stage)


def get_json(stage: str, path: str) -> Any:
    resp = timed_request(stage, "GET", path)
    return response_data(resp, stage)


def normalize_summary_updates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    updates = []
    for item in items:
        updates.append(
            {
                "volume": item.get("volume") or 1,
                "title": item.get("title") or "",
                "minChapter": item.get("minChapter") or 1,
                "maxChapter": item.get("maxChapter") or 1,
                "content": item.get("content") or "",
                "characterActions": item.get("characterActions") or {},
                "characters": [],
            }
        )
    return updates


def story_to_content(story: Any) -> str:
    if isinstance(story, dict):
        return "\n".join(str(story.get(k) or "") for k in ("start", "development", "climax", "end", "开始", "发展", "高潮", "结局")).strip()
    return str(story or "")


def normalize_outline_updates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    updates = []
    for item in items:
        updates.append(
            {
                "volume": item.get("volume") or 1,
                "title": item.get("title") or "",
                "minChapter": item.get("minChapter") or 1,
                "maxChapter": item.get("maxChapter") or 1,
                "characterActions": item.get("characterActions") or {},
                "story": item.get("story") or {},
                "content": item.get("content") or story_to_content(item.get("story")),
            }
        )
    return updates


def consume_stream(novel_id: int, chapter_id: int) -> Dict[str, Any]:
    params = {"novelId": novel_id, "chapterId": chapter_id, "userId": USER_ID}
    url = f"{BASE_URL}/stream"
    start = time.time()
    first_content_at: Optional[float] = None
    content_parts: List[str] = []
    thinking_len = 0
    progress_events = 0
    status_code = 0
    raw_lines: List[str] = []
    with requests.get(url, params=params, stream=True, timeout=1800) as resp:
        status_code = resp.status_code
        if resp.status_code >= 400:
            body = resp.text[:800]
            raise RuntimeError(f"stream HTTP {resp.status_code}: {body}")
        event_name = "message"
        for line in resp.iter_lines(decode_unicode=True):
            if line is None:
                continue
            line = line.strip()
            if not line:
                continue
            raw_lines.append(line[:400])
            if line.startswith("event:"):
                event_name = line[6:].strip() or "message"
                continue
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data:
                continue
            if event_name == "content":
                try:
                    payload = json.loads(data)
                    piece = str(payload.get("content") or "")
                except Exception:
                    piece = data
                if piece:
                    if first_content_at is None:
                        first_content_at = time.time()
                    content_parts.append(piece)
            elif event_name == "thinking":
                try:
                    payload = json.loads(data)
                    thinking_len += len(str(payload.get("content") or ""))
                except Exception:
                    thinking_len += len(data)
            elif event_name == "progress":
                progress_events += 1
            elif event_name == "generation_error":
                raise RuntimeError(f"generation_error: {data}")
    elapsed = round(time.time() - start, 2)
    content = "".join(content_parts)
    return {
        "status_code": status_code,
        "elapsed_seconds": elapsed,
        "first_content_latency_seconds": None if first_content_at is None else round(first_content_at - start, 2),
        "content_length": len(content),
        "thinking_length": thinking_len,
        "progress_events": progress_events,
        "content": content,
        "raw_lines": raw_lines[:50],
    }


def save_text(chapter_id: int, text: str) -> None:
    word_number = len(re.sub(r"\s+", "", text))
    payload = {"chapterId": chapter_id, "text": text, "wordNumber": word_number}
    resp = timed_request(f"save_text_{chapter_id}", "POST", "/chapter/updateText", json=payload)
    response_data(resp, f"save_text_{chapter_id}")
    resp = timed_request(f"finalize_text_{chapter_id}", "POST", f"/novel/finalizeText?chapterId={chapter_id}&wordNumber={word_number}")
    response_data(resp, f"finalize_text_{chapter_id}")


def write_reports() -> None:
    fail_count = sum(1 for i in issues if i["severity"] == "fail")
    warn_count = sum(1 for i in issues if i["severity"] == "warn")
    metrics["totals"]["fail_count"] = fail_count
    metrics["totals"]["warn_count"] = warn_count
    (REPORT_DIR / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "issues.md").write_text(
        "# Issues\n\n" + ("\n".join(f"- [{i['severity']}] {i['stage']}: {i['message']}" for i in issues) if issues else "- 未发现 fail/warn 项。"),
        encoding="utf-8",
    )
    lines = [
        "# Full Chain Frontend Simulation",
        "",
        f"- started_at: {STAMP}",
        f"- novel_id: {raw.get('novel_id')}",
        f"- title: {TITLE}",
        f"- fail_count: {fail_count}",
        f"- warn_count: {warn_count}",
        f"- generated_chars: {metrics['totals'].get('generated_chars', 0)}",
        "",
        "| stage | status | elapsed(s) | notes |",
        "|---|---:|---:|---|",
    ]
    for stage, item in metrics["stages"].items():
        lines.append(f"| {stage} | {item.get('status_code')} | {item.get('elapsed_seconds')} | {item.get('note', '')} |")
    lines += ["", "## Chapters"]
    for chapter in metrics["chapters"]:
        lines.append(
            f"- chapter {chapter.get('sort')} id={chapter.get('id')} chars={chapter.get('content_length')} first={chapter.get('first_content_latency_seconds')}s elapsed={chapter.get('elapsed_seconds')}s"
        )
    (REPORT_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"REPORT_DIR={REPORT_DIR}")
    print(f"NOVEL_ID={raw.get('novel_id')}")
    print(f"FAIL_COUNT={fail_count}")
    print(f"WARN_COUNT={warn_count}")
    print(f"GENERATED_CHARS={metrics['totals'].get('generated_chars', 0)}")


def main() -> int:
    try:
        health = requests.get("http://127.0.0.1:54862/health", timeout=10).json()
        raw["model_health"] = health
        if health.get("mode") != "online":
            add_issue("health", "fail", f"model mode={health.get('mode')}")

        template = post_json(
            "template",
            "/template",
            {"title": TITLE, "tags": TAGS, "creativeKeywords": KEYWORDS},
        )
        if not isinstance(template, dict):
            raise RuntimeError("template response invalid")
        metrics["stages"]["template"]["note"] = f"chars={len(json.dumps(template, ensure_ascii=False))}"

        intro = str(template.get("introduction") or "一部发生在雾港旧档案馆的群像悬疑小说。")
        characters = template.get("characters") if isinstance(template.get("characters"), list) else []
        create_payload = {
            "title": TITLE,
            "introduction": intro,
            "img": "https://mugenovel.com/default-cover.png",
            "tags": TAGS,
            "characters": characters,
            "creativeKeywords": KEYWORDS,
            "isQr": 1,
            "pf": 1,
            "zi": 50000,
            "zhang": 13,
        }
        novel_id = post_json("create_novel", "/novel/create", create_payload)
        raw["novel_id"] = int(novel_id)

        summary = get_json("summary", f"/getCompletionsSummary?novelId={novel_id}&type=1")
        if not isinstance(summary, list) or not summary:
            raise RuntimeError("summary response invalid")
        update_summary = {"nId": str(novel_id), "version": 1, "type": 1, "updates": normalize_summary_updates(summary)}
        post_json("save_summary", "/novel/updateSummaryAndHistory", update_summary)
        post_json("finalize_summary", f"/novel/finalizeSynopsis?n_id={novel_id}", {})

        outline = get_json("outline", f"/getCompletionsOutline?novelId={novel_id}&type=2")
        if not isinstance(outline, list) or not outline:
            raise RuntimeError("outline response invalid")
        update_outline = {"nId": str(novel_id), "version": 1, "type": 2, "updates": normalize_outline_updates(outline)}
        post_json("save_outline", "/novel/updateOutlineAndHistory", update_outline)
        post_json("finalize_outline", f"/novel/finalizeOutline?n_id={novel_id}", {})

        volumes = sorted({int(item.get("volume") or 1) for item in outline if isinstance(item, dict)})
        total_chars = 0
        for volume in volumes:
            detail = post_json("detail_outline_v" + str(volume), "/detailOutline", {"novelId": str(novel_id), "volume": volume})
            if not isinstance(detail, list) or not detail:
                raise RuntimeError(f"detail outline invalid for volume {volume}")
            chapters = get_json(f"chapters_v{volume}", f"/novel/chapters/{novel_id}/{volume}")
            if not isinstance(chapters, list) or not chapters:
                add_issue(f"chapters_v{volume}", "fail", "empty chapter list after detail outline")
                continue
            save_items = []
            for item in chapters:
                save_items.append(
                    {
                        "id": item.get("id"),
                        "doId": item.get("doId"),
                        "sort": item.get("sort"),
                        "title": item.get("title"),
                        "content": item.get("content"),
                        "isDg": item.get("isDg"),
                    }
                )
            post_json(f"save_detail_v{volume}", "/chapter/updateChapters", {"nId": int(novel_id), "volume": volume, "streamList": save_items})
            post_json(f"finalize_detail_v{volume}", "/chapter/finalize", {"nId": int(novel_id), "volume": volume})

            finalized_chapters = get_json(f"finalized_chapters_v{volume}", f"/novel/chapters/{novel_id}/{volume}")
            if not isinstance(finalized_chapters, list):
                finalized_chapters = chapters
            for chapter in sorted(finalized_chapters, key=lambda x: int(x.get("sort") or 0)):
                chapter_id = int(chapter.get("id"))
                sort = int(chapter.get("sort") or 0)
                stage = f"text_chapter_{sort}"
                try:
                    result = consume_stream(int(novel_id), chapter_id)
                    text = result["content"]
                    if len(text) < 2000:
                        add_issue(stage, "warn", f"chapter content short: {len(text)}")
                    save_text(chapter_id, text)
                    total_chars += len(text)
                    metrics["chapters"].append(
                        {
                            "id": chapter_id,
                            "sort": sort,
                            "volume": volume,
                            "content_length": len(text),
                            "thinking_length": result["thinking_length"],
                            "first_content_latency_seconds": result["first_content_latency_seconds"],
                            "elapsed_seconds": result["elapsed_seconds"],
                        }
                    )
                    raw["stages"][stage] = {k: v for k, v in result.items() if k != "content"}
                    (REPORT_DIR / f"chapter_{sort:03d}.md").write_text(text, encoding="utf-8")
                    if total_chars >= 50000:
                        break
                except Exception as exc:
                    add_issue(stage, "fail", repr(exc))
                    raise
            if total_chars >= 50000:
                break
        metrics["totals"]["generated_chars"] = total_chars
        if total_chars < 50000:
            add_issue("total_length", "warn", f"generated below target: {total_chars}")
    except Exception as exc:
        raw["fatal_error"] = repr(exc)
        add_issue("full_chain", "fail", repr(exc))
    finally:
        write_reports()
    return 0 if not any(i["severity"] == "fail" for i in issues) else 1


if __name__ == "__main__":
    raise SystemExit(main())
