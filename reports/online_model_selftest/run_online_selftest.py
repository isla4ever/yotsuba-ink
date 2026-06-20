import ast
import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
SERVER = ROOT / "deploy" / "openai_compat_server.py"
PORT = 54862
BASE_URL = f"http://127.0.0.1:{PORT}"
CHAT_URL = f"{BASE_URL}/v1/chat/completions"
SERVED_MODEL = "ChiYong-MoE-Novel-18B-A6B"

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
USER_ID = "codex_selftest"
NOVEL_ID = f"online_{STAMP}"
REPORT_DIR = ROOT / "reports" / "online_model_selftest" / STAMP
LOG_DIR = REPORT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

raw: Dict[str, Any] = {
    "started_at": STAMP,
    "user_id": USER_ID,
    "novel_id": NOVEL_ID,
    "health": None,
    "stages": {},
    "fatal_error": None,
}
metrics: Dict[str, Any] = {"service": {}, "stages": {}, "stability": {}}
issues: List[Dict[str, str]] = []


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


load_dotenv_file(ROOT / ".env")
load_dotenv_file(ROOT / ".env.local")


def add_issue(stage: str, severity: str, message: str) -> None:
    issues.append({"stage": stage, "severity": severity, "message": message})


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except Exception:
        return False


def wait_health(timeout_seconds: int = 90) -> Dict[str, Any]:
    start = time.time()
    last_error = "not ready"
    while time.time() - start < timeout_seconds:
        try:
            resp = requests.get(f"{BASE_URL}/health", timeout=5)
            if resp.status_code == 200:
                return resp.json()
            last_error = f"status={resp.status_code} body={resp.text[:300]}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"health timeout: {last_error}")


def start_server() -> Optional[subprocess.Popen]:
    if port_open(PORT):
        health = wait_health(10)
        if health.get("mode") == "online":
            metrics["service"]["reused_existing"] = True
            return None
        raise RuntimeError(f"port {PORT} is occupied by non-online service: {health}")

    env = os.environ.copy()
    env["NOVEL_USE_ONLINE_MODEL"] = "true"
    env.setdefault("TOKENHUB_BASE_URL", "https://tokenhub.tencentmaas.com/v1")
    out = (LOG_DIR / "model_server.out.log").open("w", encoding="utf-8")
    err = (LOG_DIR / "model_server.err.log").open("w", encoding="utf-8")
    cmd = [
        str(PYTHON),
        str(SERVER),
        "--online-model",
        "--served-model-name",
        SERVED_MODEL,
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
        "--include-done-marker",
    ]
    metrics["service"]["reused_existing"] = False
    return subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=out, stderr=err)


def strip_fences(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json|python|text|markdown)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*```$", "", value)
    return value.strip()


def parse_literal(text: str) -> Any:
    source = strip_fences(text)
    candidates = [source]
    for left, right in [("[", "]"), ("{", "}")]:
        start = source.find(left)
        end = source.rfind(right)
        if start >= 0 and end > start:
            candidates.append(source[start : end + 1])
    for candidate in candidates:
        for parser in (json.loads, ast.literal_eval):
            try:
                return parser(candidate)
            except Exception:
                pass
    return None


def message_text(obj: Dict[str, Any]) -> tuple[str, str, str]:
    message = obj.get("choices", [{}])[0].get("message", {})
    content = str(message.get("content") or "")
    structured = str(message.get("structured_content") or "")
    return content, structured, structured or content


def pollution_markers(text: str) -> List[str]:
    probes = [
        "作为AI",
        "我是AI",
        "无法回答",
        "无法完成",
        "无法理解",
        "抱歉",
        "默认内容",
        "兜底",
        "不是bug",
        "feature",
        "编码问题",
        "```",
        "<|im_end|>",
    ]
    return [marker for marker in probes if marker in str(text or "")]


def stage_status(stage: str, checks: List[tuple[bool, str]]) -> str:
    failures = [message for ok, message in checks if not ok]
    for failure in failures:
        add_issue(stage, "fail", failure)
    return "fail" if failures else "pass"


def compact(text: str, limit: int = 700) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def post_nonstream(stage: str, prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
    payload = {
        "model": SERVED_MODEL,
        "task_name": stage,
        "user_id": USER_ID,
        "novel_id": NOVEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 0.9,
    }
    start = time.time()
    resp = requests.post(CHAT_URL, json=payload, timeout=420)
    elapsed = round(time.time() - start, 2)
    try:
        obj = resp.json()
    except Exception:
        obj = {"raw_text": resp.text}

    raw["stages"][stage] = {
        "status_code": resp.status_code,
        "elapsed_seconds": elapsed,
        "request": {"task_name": stage, "max_tokens": max_tokens, "temperature": temperature},
        "response": obj,
    }
    metrics["stages"][stage] = {
        "status_code": resp.status_code,
        "elapsed_seconds": elapsed,
        "stream": False,
    }
    if resp.status_code >= 400:
        add_issue(stage, "fail", f"HTTP {resp.status_code}: {resp.text[:500]}")
        return obj

    content, structured, merged = message_text(obj)
    metrics["stages"][stage].update(
        {
            "model": obj.get("model"),
            "content_length": len(content),
            "structured_length": len(structured),
        }
    )
    raw["stages"][stage]["content_length"] = len(content)
    raw["stages"][stage]["structured_length"] = len(structured)
    raw["stages"][stage]["content_excerpt"] = compact(merged, 500)
    return obj


def post_stream(stage: str, prompt: str, max_tokens: int, chapter_no: int) -> str:
    payload = {
        "model": SERVED_MODEL,
        "task_name": stage,
        "user_id": USER_ID,
        "novel_id": NOVEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": max_tokens,
        "temperature": 0.72,
        "top_p": 0.9,
        "output_format": "markdown",
    }
    start = time.time()
    first_content_at: Optional[float] = None
    content_parts: List[str] = []
    reasoning_length = 0
    status_code: Optional[int] = None

    with requests.post(CHAT_URL, json=payload, timeout=800, stream=True) as resp:
        status_code = resp.status_code
        if resp.status_code >= 400:
            body = resp.text[:800]
            add_issue(f"chapter_{chapter_no}", "fail", f"HTTP {resp.status_code}: {body}")
            raise requests.HTTPError(body)
        for raw_line in resp.iter_lines(decode_unicode=False):
            if not raw_line:
                continue
            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8", errors="replace").strip()
            else:
                line = str(raw_line).strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line:
                continue
            if line == "[DONE]":
                break
            try:
                obj = json.loads(line)
            except Exception:
                continue
            choice = obj.get("choices", [{}])[0]
            delta = choice.get("delta", {}) or {}
            if delta.get("reasoning_content"):
                reasoning_length += len(str(delta.get("reasoning_content")))
            if delta.get("content"):
                if first_content_at is None:
                    first_content_at = time.time()
                content_parts.append(str(delta.get("content")))
            if choice.get("finish_reason"):
                break

    content = "".join(content_parts).strip()
    elapsed = round(time.time() - start, 2)
    first_latency = None if first_content_at is None else round(first_content_at - start, 2)
    key = f"{stage}_chapter_{chapter_no}"
    raw["stages"][key] = {
        "status_code": status_code,
        "elapsed_seconds": elapsed,
        "first_content_latency_seconds": first_latency,
        "content_length": len(content),
        "reasoning_length": reasoning_length,
        "content": content,
        "content_excerpt": compact(content, 800),
    }
    metrics["stages"][key] = {
        "status_code": status_code,
        "elapsed_seconds": elapsed,
        "first_content_latency_seconds": first_latency,
        "stream": True,
        "content_length": len(content),
        "reasoning_length": reasoning_length,
    }
    return content


def visible_overlap(previous: str, current: str) -> int:
    seeds = ["雾港", "潮痕", "档案", "沈听岚", "乔清和", "周予安", "线索", "旧案", "码头", "真相"]
    return sum(1 for seed in seeds if seed in previous and seed in current)


def run_stability_probe() -> None:
    try:
        resp = requests.post(
            CHAT_URL,
            data="{bad json",
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        metrics["stability"]["malformed_status_code"] = resp.status_code
        metrics["stability"]["malformed_body_excerpt"] = resp.text[:300]
        if resp.status_code < 400:
            add_issue("stability", "warn", "malformed JSON unexpectedly succeeded")
    except Exception as exc:
        metrics["stability"]["malformed_exception"] = str(exc)[:300]


def write_reports() -> None:
    pass_count = sum(1 for item in metrics["stages"].values() if item.get("quality_status") == "pass")
    fail_count = sum(1 for item in issues if item["severity"] == "fail")
    warn_count = sum(1 for item in issues if item["severity"] == "warn")

    lines = [
        "# TokenHub 线上模型端标准自测报告",
        "",
        f"- 时间：{STAMP}",
        f"- 隔离 Wiki：{USER_ID}/{NOVEL_ID}",
        f"- 服务模式：{metrics.get('service', {}).get('health_mode')}",
        f"- TokenHub Base URL：{metrics.get('service', {}).get('tokenhub_base_url')}",
        f"- 质量阶段通过数：{pass_count}",
        f"- Fail：{fail_count}",
        f"- Warn：{warn_count}",
        "",
        "## 任务模型映射",
        "```json",
        json.dumps(metrics.get("service", {}).get("task_model_mapping"), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 性能摘要",
        "| 阶段 | 状态 | 耗时(s) | 首内容(s) | 长度 | 推理长度 | 模型 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, item in metrics["stages"].items():
        lines.append(
            f"| {name} | {item.get('quality_status', '')} / {item.get('status_code', '')} | "
            f"{item.get('elapsed_seconds', '')} | {item.get('first_content_latency_seconds', '')} | "
            f"{item.get('content_length', '')} | {item.get('reasoning_length', '')} | {item.get('model', '')} |"
        )

    lines += ["", "## 章节观察"]
    for chapter_no in range(1, 4):
        key = ("text_first_chapter" if chapter_no == 1 else "text_non_first_chapter") + f"_chapter_{chapter_no}"
        content = str(raw["stages"].get(key, {}).get("content") or "")
        lines.append(f"- 第{chapter_no}章：长度 {len(content)}；开头：{compact(content, 180)}")

    lines += [
        "",
        "## 初步结论",
        "- 自测链路跑通。" if fail_count == 0 else "- 自测未完全通过，详见 issues.md。",
        "- 后续优化重点：让细纲输出显式携带伏笔状态，正文 prompt 固化“前章事实-本章目标-本章回收-章末新增钩子”结构，降低模板化兜底污染。",
    ]

    issue_lines = ["# Issues", ""]
    if issues:
        issue_lines += [f"- [{item['severity']}] {item['stage']}: {item['message']}" for item in issues]
    else:
        issue_lines.append("- 未发现 fail/warn 项。")
    issue_lines += [
        "",
        "# Optimization Backlog",
        "",
        "- 修复/压缩细纲归一化里的硬兜底模板，优先保留模型有效输出，只在解析失败时做结构修复。",
        "- 为章节连续性增加机器可读状态：上一章新增线索、本章必须回收、未解决问题。",
        "- 对正文输出增加后验检查：承接上一章关键名词、人物动机不漂移、章末钩子不空泛。",
    ]

    (REPORT_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    (REPORT_DIR / "issues.md").write_text("\n".join(issue_lines), encoding="utf-8")
    (REPORT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "raw_responses.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"REPORT_DIR={REPORT_DIR}")
    print(f"FAIL_COUNT={fail_count}")
    print(f"WARN_COUNT={warn_count}")
    print("STAGE_KEYS=" + ",".join(metrics["stages"].keys()))
    if issues:
        print("ISSUES_EXCERPT=" + " | ".join(f"{i['severity']}:{i['stage']}:{i['message']}" for i in issues[:6]))


def main() -> int:
    proc: Optional[subprocess.Popen] = None
    title = "雾港潮痕档案"
    categories = ["都市异能", "悬疑推理", "群像成长"]
    chapters: List[str] = []
    try:
        if not os.environ.get("TOKENHUB_API_KEY"):
            raise RuntimeError("TOKENHUB_API_KEY missing")
        proc = start_server()
        health = wait_health()
        raw["health"] = health
        metrics["service"].update(
            {
                "health_mode": health.get("mode"),
                "tokenhub_base_url": health.get("tokenhub_base_url"),
                "task_model_mapping": health.get("task_model_mapping"),
            }
        )
        if health.get("mode") != "online":
            add_issue("health", "fail", f"expected online mode, got {health.get('mode')}")

        info_prompt = f"""你是资深类型小说策划编辑。请根据小说标题和分类，生成可直接进入后续梗概、大纲、细纲和正文创作的基础设定。
只输出三个板块：人物信息、故事背景、简介。人物信息至少 5 人，每人包含身份、目标、秘密或冲突、与主线关系。
小说标题：{title}
分类/标签：{categories}"""
        info_obj = post_nonstream("info_recommend", info_prompt, 1600, 0.65)
        _, _, info_text = message_text(info_obj)
        metrics["stages"]["info_recommend"]["quality_status"] = stage_status(
            "info_recommend",
            [
                (len(info_text) >= 500, "信息推荐内容过短"),
                (all(token in info_text for token in ["人物", "背景", "简介"]), "缺少人物/背景/简介板块"),
                (not pollution_markers(info_text), "出现污染：" + ",".join(pollution_markers(info_text))),
            ],
        )

        summary_prompt = f"""你是小说主线策划。固定输出一个 Python 风格列表，列表内 1 个 dict，字段为：主要人物和他们的行为、内容。
要求内容体现主角目标、核心谜团、阶段转折、最终代价，并留下可延展伏笔。
小说标题：{title}
分类/标签：{categories}
人物信息：{compact(info_text, 1600)}
故事背景：{compact(info_text, 1500)}
小说简介：{compact(info_text, 1200)}"""
        summary_obj = post_nonstream("summary", summary_prompt, 1800, 0.62)
        _, _, summary_text = message_text(summary_obj)
        summary_parsed = parse_literal(summary_text)
        metrics["stages"]["summary"]["quality_status"] = stage_status(
            "summary",
            [
                (isinstance(summary_parsed, list) and len(summary_parsed) >= 1, "梗概不能解析为列表"),
                (any(token in summary_text for token in ["伏笔", "真相", "谜", "代价"]), "缺少伏笔/谜团/代价"),
                (not pollution_markers(summary_text), "出现污染：" + ",".join(pollution_markers(summary_text))),
            ],
        )

        outline_prompt = f"""你是长篇小说结构编辑。请基于基础设定和全书梗概，输出 4 卷大纲。
固定输出 Python 风格列表，每项包含：主要人物和他们的行为、故事情节。故事情节内包含开始、发展、高潮、结局。
每卷必须有明确目标、冲突升级、阶段性答案和下一卷钩子。
人物信息：{compact(info_text, 1600)}
小说简介：{compact(summary_text, 1600)}
全书梗概：{summary_text}"""
        outline_obj = post_nonstream("outline", outline_prompt, 2400, 0.62)
        _, _, outline_text = message_text(outline_obj)
        outline_parsed = parse_literal(outline_text)
        metrics["stages"]["outline"]["quality_status"] = stage_status(
            "outline",
            [
                (isinstance(outline_parsed, list) and len(outline_parsed) >= 3, "大纲不能解析为至少 3 卷列表"),
                (sum(1 for token in ["开始", "发展", "高潮", "结局"] if token in outline_text) >= 3, "缺少开始/发展/高潮/结局"),
                (not pollution_markers(outline_text), "出现污染：" + ",".join(pollution_markers(outline_text))),
            ],
        )

        detail_prompt = f"""你是一位长篇网文章节策划，请把当前分卷内容拆成递进明确、可直接用于正文创作的章节细纲。
输出 Python 风格列表，正好 3 项，每项字段为：章节标题、细纲内容。
小说标题：{title}
分类/标签：{categories}
故事背景：{compact(info_text, 1400)}
小说简介：{compact(summary_text, 1200)}
底稿核心人物设定：{compact(info_text, 1700)}
当前分卷人物推进重点：{compact(outline_text, 1600)}
本卷梗概：{compact(outline_text, 1800)}
章节数量：3章
每章内容必须：包含本章场景、本章目标、人物选择、线索推进、章末钩子。第三章要回收第一章一个小伏笔，同时打开更大的谜团。"""
        detail_obj = post_nonstream("detail_outline", detail_prompt, 3000, 0.6)
        _, _, detail_text = message_text(detail_obj)
        detail_parsed = parse_literal(detail_text)
        metrics["stages"]["detail_outline"]["quality_status"] = stage_status(
            "detail_outline",
            [
                (isinstance(detail_parsed, list) and len(detail_parsed) >= 3, "细纲不能解析为至少 3 章列表"),
                (any(token in detail_text for token in ["伏笔", "钩子", "线索"]), "缺少伏笔/钩子/线索"),
                (not pollution_markers(detail_text), "出现污染：" + ",".join(pollution_markers(detail_text))),
            ],
        )

        chapter_outlines: List[str] = []
        if isinstance(detail_parsed, list):
            for item in detail_parsed[:3]:
                if isinstance(item, dict):
                    chapter_outlines.append(str(item.get("细纲内容") or item.get("内容") or item))
                else:
                    chapter_outlines.append(str(item))
        while len(chapter_outlines) < 3:
            chapter_outlines.append(detail_text)

        for index in range(3):
            chapter_no = index + 1
            task = "text_first_chapter" if chapter_no == 1 else "text_non_first_chapter"
            previous = "\n\n".join(chapters[-1:])
            text_prompt = f"""你是成熟的中文类型小说作者。请写《{title}》第 {chapter_no} 章正文。
输出要求：只输出正文，不要解释、不要列提纲、不要代码块。场景、动作、对话、心理必须交织推进，避免空泛总结。章末留下明确钩子。
小说标题：{title}
分类/标签：{categories}
故事背景：{compact(info_text, 800)}
小说简介：{compact(summary_text, 700)}
本卷梗概：{compact(outline_text, 800)}
底稿核心人物设定：{compact(info_text, 900)}
当前阶段人物推进重点：{compact(outline_text, 700)}
小说章节信息：第 {chapter_no} 章 / 共 3 章
当前章节细纲：{chapter_outlines[index]}
上一章正文节选：{compact(previous, 700) if previous else "无，这是第一章。"}
---
请根据以上信息生成正文。第3章必须回收第1章埋下的一个小线索，同时打开更大的谜团。"""
            content = post_stream(task, text_prompt, 4200, chapter_no)
            chapters.append(content)
            markers = pollution_markers(content)
            checks = [
                (len(content) >= 1200, f"第{chapter_no}章正文过短"),
                (not markers, f"第{chapter_no}章正文污染：" + ",".join(markers)),
            ]
            if chapter_no > 1:
                checks.append((visible_overlap(chapters[index - 1], content) >= 1, f"第{chapter_no}章与上一章显性承接弱"))
            metrics["stages"][f"{task}_chapter_{chapter_no}"]["quality_status"] = stage_status(f"chapter_{chapter_no}", checks)

        run_stability_probe()
    except Exception as exc:
        raw["fatal_error"] = repr(exc)
        add_issue("selftest", "fail", repr(exc))
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except Exception:
                proc.kill()
        write_reports()

    return 0 if not any(item["severity"] == "fail" for item in issues) else 1


if __name__ == "__main__":
    raise SystemExit(main())
