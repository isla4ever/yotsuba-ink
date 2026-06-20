#!/usr/bin/env python3
"""Run a real backend-driven novel creation chain for local QA.

The script mimics the current frontend flow and writes every generated stage to
the configured backend database through HTTP APIs. It is intentionally standard
library only so it can run inside the cleaned model repo without extra deps.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


TARGET_CHAPTER_WORDS = 2500
PF_CONFIGS = {
    1: {"name": "投稿", "min_words": 10_000, "max_words": 80_000, "default_words": 50_000, "chapters_per_volume": 8, "max_volumes": 6},
    2: {"name": "出版", "min_words": 60_000, "max_words": 150_000, "default_words": 120_000, "chapters_per_volume": 10, "max_volumes": 12},
    3: {"name": "长篇", "min_words": 80_000, "max_words": 500_000, "default_words": 200_000, "chapters_per_volume": 10, "max_volumes": 20},
}


def clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


def round_to_thousand(value: int) -> int:
    return max(1_000, math.floor(value / 1_000 + 0.5) * 1_000)


def normalize_pf(pf: int | None) -> int:
    return pf if pf in PF_CONFIGS else 1


def resolve_story_plan(pf: int | None, target_words: int | None) -> dict[str, Any]:
    safe_pf = normalize_pf(pf)
    config = PF_CONFIGS[safe_pf]
    total_words = int(target_words or config["default_words"])
    total_words = round_to_thousand(clamp(total_words, config["min_words"], config["max_words"]))
    chapter_count = max(1, math.ceil(total_words / TARGET_CHAPTER_WORDS))
    if chapter_count <= config["chapters_per_volume"]:
        volume_count = 1
    else:
        volume_count = clamp(math.ceil(chapter_count / config["chapters_per_volume"]), 2, config["max_volumes"])
    ranges = []
    for index in range(volume_count):
        start = 1 + math.floor(index * chapter_count / volume_count)
        end = chapter_count if index == volume_count - 1 else math.floor((index + 1) * chapter_count / volume_count)
        ranges.append(
            {
                "volume": index + 1,
                "minChapter": start,
                "maxChapter": max(start, end),
                "chapterCount": max(start, end) - start + 1,
            }
        )
    return {
        "pf": safe_pf,
        "scaleName": config["name"],
        "targetWords": total_words,
        "targetChapterWords": TARGET_CHAPTER_WORDS,
        "chapterCount": chapter_count,
        "volumeCount": volume_count,
        "chaptersPerVolumeTarget": config["chapters_per_volume"],
        "maxVolumeCount": config["max_volumes"],
        "ranges": ranges,
    }


def assert_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise AssertionError(f"{label} mismatch: actual={actual!r}, expected={expected!r}")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def make_token(user_id: int = 1, secret: str = "txdy") -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": "auth0",
        "userId": int(user_id),
        "exp": now + 3 * 24 * 60 * 60,
    }
    signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


class BackendClient:
    def __init__(self, base_url: str, token: str, progress_path: Path) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.progress_path = progress_path

    def log(self, event: str, **fields: Any) -> None:
        payload = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            **fields,
        }
        line = json.dumps(payload, ensure_ascii=False)
        print(line, flush=True)
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        with self.progress_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 2400,
        unwrap: bool = True,
    ) -> Any:
        url = self.base_url + path
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url += "?" + query
        data = None
        headers = {
            "Authorization": self.token,
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} {method} {path}: {raw[:1000]}") from exc
        except Exception as exc:
            raise RuntimeError(f"{method} {path} failed: {exc}") from exc
        elapsed = round(time.perf_counter() - start, 2)
        if status < 200 or status >= 300:
            raise RuntimeError(f"HTTP {status} {method} {path}: {raw[:1000]}")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return raw
        if not unwrap:
            return parsed
        if isinstance(parsed, dict) and "code" in parsed:
            if parsed.get("code") != 200:
                raise RuntimeError(f"backend code={parsed.get('code')} message={parsed.get('message')} path={path}")
            return parsed.get("data")
        return parsed


def word_count(text: Any) -> int:
    return len("".join(str(text or "").split()))


def make_info_markdown(title: str, info: dict[str, Any]) -> str:
    parts = ["## 人物信息"]
    for item in info.get("characters") or []:
        parts.append(f"- {item}")
    parts += ["", "## 故事背景", str(info.get("background") or ""), "", "## 简介", str(info.get("introduction") or "")]
    return "\n".join(parts).strip()


def summarize_quality(report: dict[str, Any]) -> dict[str, Any]:
    findings = report.get("findings") if isinstance(report, dict) else None
    return {
        "score": report.get("score") if isinstance(report, dict) else None,
        "level": report.get("level") if isinstance(report, dict) else None,
        "finding_count": len(findings) if isinstance(findings, list) else None,
        "latest_chapter_quality": report.get("latest_chapter_quality") if isinstance(report, dict) else None,
    }


def run_chain(args: argparse.Namespace) -> dict[str, Any]:
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    progress_path = report_dir / f"{stamp}_{args.title}_progress.jsonl"
    token = make_token(args.user_id)
    client = BackendClient(args.backend, token, progress_path)
    expected_plan = resolve_story_plan(args.pf, args.target_words)

    tags = [
        {"id": 1, "name": "短篇", "isShow": 1, "categoryId": 1},
        {"id": 68, "name": "克制", "isShow": 1, "categoryId": 2},
        {"id": 8, "name": "当代", "isShow": 1, "categoryId": 3},
        {"id": 189, "name": "沿海旧城", "isShow": 1, "categoryId": 4},
        {"id": 20, "name": "悬疑", "isShow": 1, "categoryId": 5},
        {"id": 190, "name": "案件追查", "isShow": 1, "categoryId": 5},
    ]
    keywords = args.keywords or ["旧港", "录音带", "父女裂痕", "潮汐证据"]
    result: dict[str, Any] = {
        "title": args.title,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "backend": args.backend,
        "progress_log": str(progress_path),
        "expected_plan": expected_plan,
        "durations": {},
        "stages": {},
        "warnings": [],
    }

    def timed(stage: str, fn):
        client.log("stage_start", stage=stage)
        start = time.perf_counter()
        value = fn()
        elapsed = round(time.perf_counter() - start, 2)
        result["durations"][stage] = elapsed
        client.log("stage_done", stage=stage, elapsed_seconds=elapsed)
        return value

    info = timed(
        "info_recommend",
        lambda: client.request("POST", "/front/template", body={"title": args.title, "tags": tags, "creativeKeywords": keywords}),
    )
    result["stages"]["info_recommend"] = {
        "character_count": len(info.get("characters") or []),
        "characters": info.get("characters") or [],
        "background_chars": word_count(info.get("background")),
        "introduction_chars": word_count(info.get("introduction")),
        "topology_quality": (info.get("topology") or {}).get("quality") if isinstance(info.get("topology"), dict) else None,
    }

    novel_id = timed(
        "create_novel",
        lambda: client.request(
            "POST",
            "/front/novel/create",
            body={
                "title": args.title,
                "introduction": info.get("introduction") or f"{args.title} 测试简介",
                "img": "https://example.com/novel-cover.png",
                "tags": tags,
                "characters": info.get("characters") or [],
                "creativeKeywords": keywords,
                "isQr": 1,
                "zhang": expected_plan["chapterCount"],
                "zi": expected_plan["targetWords"],
                "pf": expected_plan["pf"],
            },
        ),
    )
    result["novel_id"] = novel_id
    client.log("novel_created", novel_id=novel_id)

    novel_info = timed(
        "novel_info_after_create",
        lambda: client.request("GET", "/front/novel/novelInfo", params={"n_id": novel_id}),
    )
    result["stages"]["novel_info_after_create"] = {
        "pf": novel_info.get("pf") if isinstance(novel_info, dict) else None,
        "zi": novel_info.get("zi") if isinstance(novel_info, dict) else None,
        "zhang": novel_info.get("zhang") if isinstance(novel_info, dict) else None,
    }
    if isinstance(novel_info, dict):
        if novel_info.get("pf") is not None:
            assert_equal("novel.pf", int(novel_info.get("pf")), expected_plan["pf"])
        if novel_info.get("zhang") is not None:
            assert_equal("novel.zhang", int(novel_info.get("zhang")), expected_plan["chapterCount"])

    info_markdown = make_info_markdown(args.title, info)
    topology = info.get("topology") or {}
    if topology:
        topo_result = timed(
            "persist_topology",
            lambda: client.request(
                "POST",
                f"/front/novelWiki/{novel_id}/topology",
                body={
                    "title": args.title,
                    "infoRecommend": info_markdown,
                    "persist": True,
                    "sourceStage": "info_recommend",
                    "topology": topology,
                },
            ),
        )
        result["stages"]["persist_topology"] = topo_result

    summary = timed(
        "summary",
        lambda: client.request("GET", "/front/getCompletionsSummary", params={"novelId": novel_id, "type": 1}),
    )
    result["stages"]["summary"] = {
        "items": len(summary or []),
        "word_count": word_count(summary),
        "preview": str(summary[0].get("content") if summary else "")[:800],
    }
    timed("finalize_summary", lambda: client.request("POST", "/front/novel/finalizeSynopsis", params={"n_id": novel_id}))

    outline = timed(
        "outline",
        lambda: client.request("GET", "/front/getCompletionsOutline", params={"novelId": novel_id, "type": 2}),
    )
    result["stages"]["outline"] = {
        "items": len(outline or []),
        "volumes": [
            {
                "volume": item.get("volume"),
                "title": item.get("title"),
                "minChapter": item.get("minChapter"),
                "maxChapter": item.get("maxChapter"),
                "characters": list((item.get("characterActions") or {}).keys()),
            }
            for item in (outline or [])
        ],
    }
    assert_equal("outline volume count", len(outline or []), expected_plan["volumeCount"])
    expected_ranges = {item["volume"]: item for item in expected_plan["ranges"]}
    for item in outline or []:
        volume_no = int(item.get("volume") or 0)
        expected_range = expected_ranges.get(volume_no)
        if not expected_range:
            raise AssertionError(f"unexpected outline volume={volume_no}")
        if item.get("minChapter") is not None:
            assert_equal(f"outline v{volume_no}.minChapter", int(item.get("minChapter")), expected_range["minChapter"])
        if item.get("maxChapter") is not None:
            assert_equal(f"outline v{volume_no}.maxChapter", int(item.get("maxChapter")), expected_range["maxChapter"])
    timed("finalize_outline", lambda: client.request("POST", "/front/novel/finalizeOutline", params={"n_id": novel_id}))

    all_chapters: list[dict[str, Any]] = []
    max_volume = max([int(item.get("volume") or 0) for item in (outline or [])] or [1])
    if args.max_detail_volumes is not None and args.max_detail_volumes >= 0:
        detail_volume_limit = min(max_volume, args.max_detail_volumes)
    else:
        detail_volume_limit = max_volume
    result["stages"]["detail_outline_scope"] = {
        "outline_volumes": max_volume,
        "detail_volume_limit": detail_volume_limit,
    }
    for volume in range(1, detail_volume_limit + 1):
        detail = timed(
            f"detail_outline_v{volume}",
            lambda volume=volume: client.request("POST", "/front/detailOutline", body={"novelId": str(novel_id), "volume": volume}),
        )
        expected_range = expected_ranges.get(volume)
        if expected_range:
            assert_equal(f"detail outline v{volume} chapter count", len(detail or []), expected_range["chapterCount"])
        result["stages"][f"detail_outline_v{volume}"] = {
            "items": len(detail or []),
            "chapters": [{"sort": item.get("sort"), "title": item.get("title"), "content_chars": word_count(item.get("content"))} for item in (detail or [])],
        }
        chapters = client.request("GET", f"/front/novel/chapters/{novel_id}/{volume}")
        for chapter in chapters or []:
            if isinstance(chapter, dict):
                all_chapters.append(chapter)

    all_chapters = sorted(all_chapters, key=lambda x: int(x.get("sort") or 0))
    if args.skip_text:
        chapters_to_generate = []
    elif args.max_chapters and args.max_chapters > 0:
        chapters_to_generate = all_chapters[: args.max_chapters]
    else:
        chapters_to_generate = all_chapters
    result["stages"]["chapters_planned"] = {
        "total": len(all_chapters),
        "to_generate": len(chapters_to_generate),
        "chapters": [{"id": c.get("id"), "sort": c.get("sort"), "title": c.get("title"), "volume": c.get("volume")} for c in all_chapters],
    }

    generated: list[dict[str, Any]] = []
    continuity_snapshots: list[dict[str, Any]] = []
    for chapter in chapters_to_generate:
        chapter_id = chapter.get("id")
        sort = chapter.get("sort")
        title = chapter.get("title")
        text = timed(
            f"text_chapter_{sort}",
            lambda chapter_id=chapter_id: client.request("POST", "/front/getText", params={"novelId": novel_id, "chapterId": chapter_id}),
        )
        wc = word_count(text)
        if wc < 1800:
            result["warnings"].append({"stage": f"text_chapter_{sort}", "message": f"正文明显偏短：{wc} 字"})
        elif wc < 2300:
            result["warnings"].append({"stage": f"text_chapter_{sort}", "message": f"正文低于建议区间：{wc} 字"})
        elif wc > 3200:
            result["warnings"].append({"stage": f"text_chapter_{sort}", "message": f"正文超过建议上限：{wc} 字"})
        generated.append({"id": chapter_id, "sort": sort, "title": title, "word_count": wc, "preview": str(text or "")[:700]})
        try:
            client.request("POST", "/front/novel/finalizeText", params={"chapterId": chapter_id, "wordNumber": wc}, timeout=120)
        except Exception as exc:
            client.log("finalize_text_warning", chapter_id=chapter_id, message=str(exc))
        continuity = timed(
            f"continuity_after_chapter_{sort}",
            lambda: client.request("GET", f"/front/novelWiki/{novel_id}/continuity"),
        )
        continuity_snapshots.append({"chapter_sort": sort, **summarize_quality(continuity or {})})

    result["stages"]["generated_chapters"] = generated
    result["stages"]["continuity_snapshots"] = continuity_snapshots
    result["stages"]["wiki_status"] = timed(
        "wiki_status",
        lambda: client.request("GET", f"/front/novelWiki/{novel_id}/status"),
    )
    result["stages"]["wiki_documents"] = timed(
        "wiki_documents",
        lambda: client.request("GET", f"/front/novelWiki/{novel_id}/documents"),
    )
    result["finished_at"] = datetime.now().isoformat(timespec="seconds")
    result["status"] = "ok"
    report_path = report_dir / f"novel_{novel_id}_{stamp}_e2e_report.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    client.log("report_written", path=str(report_path), novel_id=novel_id)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://127.0.0.1:8090")
    parser.add_argument("--title", default="潮线未眠")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--pf", type=int, default=1, choices=sorted(PF_CONFIGS), help="1=投稿, 2=出版, 3=长篇.")
    parser.add_argument("--target-words", type=int, help="Planned total words, in Chinese characters/words.")
    parser.add_argument("--keywords", nargs="*")
    parser.add_argument("--max-detail-volumes", type=int, default=None, help="Limit generated detail-outline volumes. 0 means outline-only.")
    parser.add_argument("--max-chapters", type=int, default=0, help="0 means generate all chapters.")
    parser.add_argument("--skip-text", action="store_true", help="Stop after detail outline/wiki checks without generating chapter text.")
    parser.add_argument("--report-dir", default="reports/platform_e2e")
    args = parser.parse_args()
    try:
        result = run_chain(args)
    except Exception as exc:
        failed = {
            "status": "failed",
            "title": args.title,
            "error": str(exc),
            "failed_at": datetime.now().isoformat(timespec="seconds"),
        }
        Path(args.report_dir).mkdir(parents=True, exist_ok=True)
        failed_path = Path(args.report_dir) / f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{args.title}.json"
        failed_path.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"event": "failed", "path": str(failed_path), "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1
    print(json.dumps({"event": "done", "novel_id": result.get("novel_id"), "status": result.get("status")}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
