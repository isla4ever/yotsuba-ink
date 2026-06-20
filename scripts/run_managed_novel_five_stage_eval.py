import ast
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib import request


ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = ROOT / ".venv" / "Scripts" / "python.exe"
SERVER_SCRIPT = ROOT / "deploy" / "openai_compat_server.py"
MODEL_PATH = Path(r"D:\models\Qwen3.5-4B")
PORT = 54862
BASE_URL = f"http://127.0.0.1:{PORT}"
CHAT_URL = BASE_URL + "/v1/chat/completions"
SERVED_MODEL = "ChiYong-MoE-Novel-18B-A6B"
REPORT_DIR = ROOT / "reports" / "managed_five_stage_eval"

ADAPTERS = {
    "info_recommend": ROOT / "outputs" / "managed_info_recommend_resilient" / "info_recommend_len1024_r8_qv__1773468078" / "final",
    "summary": None,
    "outline": None,
    "detail_outline": None,
    "text_first": ROOT / "outputs" / "managed_text_first_resilient" / "text_first_len2816_r16_qkvo__1773574060" / "final",
}

NOVEL_TITLE = "雾港潮痕档案"
CATEGORIES = ["都市异能", "悬疑推理", "群像成长"]


def resolve_latest_final(search_roots: list[Path]) -> Path:
    candidates: list[tuple[float, Path]] = []
    for root in search_roots:
        if root is None or not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            final_dir = child / "final"
            if final_dir.exists():
                candidates.append((final_dir.stat().st_mtime, final_dir))
    if not candidates:
        raise FileNotFoundError(f"No final adapter found under: {search_roots}")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


ADAPTERS["summary"] = resolve_latest_final([
    ROOT / "outputs" / "summary_hqcorr_resilient",
    ROOT / "outputs" / "managed_summary_resilient",
])
ADAPTERS["outline"] = resolve_latest_final([
    ROOT / "outputs" / "outline_hqcorr_resilient",
    ROOT / "outputs" / "managed_outline_resilient",
])
ADAPTERS["detail_outline"] = resolve_latest_final([
    ROOT / "outputs" / "detail_outline_hqcorr_resilient",
    ROOT / "outputs" / "managed_detail_outline_resilient",
])


def ensure_paths() -> None:
    required = [PYTHON_EXE, SERVER_SCRIPT, MODEL_PATH, *ADAPTERS.values()]
    missing = [str(path) for path in required if path is None or not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required paths:\n" + "\n".join(missing))
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def http_json(url: str, payload: dict | None = None, timeout: int = 1200) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, method="GET" if payload is None else "POST")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_server_ready(timeout_sec: int = 240) -> None:
    start = time.time()
    last_error = "server not ready"
    while time.time() - start < timeout_sec:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=3):
                return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(2)
    raise TimeoutError(f"Server did not become ready within {timeout_sec}s: {last_error}")


def start_server(stage: str, adapter_path: Path) -> tuple[subprocess.Popen, Path, Path]:
    timestamp = int(time.time())
    out_log = REPORT_DIR / f"{stage}_{timestamp}.out.log"
    err_log = REPORT_DIR / f"{stage}_{timestamp}.err.log"
    cmd = [
        str(PYTHON_EXE),
        str(SERVER_SCRIPT),
        "--model-path",
        str(MODEL_PATH),
        "--adapter-path",
        str(adapter_path),
        "--served-model-name",
        SERVED_MODEL,
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
        "--dtype",
        "float16",
        "--max-new-tokens",
        "4200",
        "--include-done-marker",
    ]
    out_fp = open(out_log, "w", encoding="utf-8")
    err_fp = open(err_log, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=out_fp, stderr=err_fp)
    return proc, out_log, err_log


def stop_server(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def call_model(
    task_name: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    repetition_penalty: float,
) -> dict:
    payload = {
        "model": SERVED_MODEL,
        "task_name": task_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": temperature,
        "top_p": top_p,
        "repetition_penalty": repetition_penalty,
        "max_tokens": max_tokens,
    }
    if task_name in {"text", "text_first_chapter", "text_non_first_chapter"}:
        payload["output_format"] = "markdown"
    return http_json(CHAT_URL, payload=payload, timeout=2400)


def extract_content(resp: dict) -> str:
    return str(resp["choices"][0]["message"]["content"] or "").strip()


def extract_structured_content(resp: dict) -> str:
    message = resp["choices"][0]["message"]
    return str(message.get("structured_content") or message.get("content") or "").strip()


def clean_model_text(text: str) -> str:
    text = str(text or "").replace("\ufeff", "").replace("\ufffd", "").replace("<|im_end|>", "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def parse_pythonish(text: str):
    cleaned = clean_model_text(text)
    candidates = [cleaned]
    list_start, list_end = cleaned.find("["), cleaned.rfind("]")
    if list_start >= 0 and list_end > list_start:
        candidates.append(cleaned[list_start : list_end + 1])
    obj_start, obj_end = cleaned.find("{"), cleaned.rfind("}")
    if obj_start >= 0 and obj_end > obj_start:
        candidates.append(cleaned[obj_start : obj_end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            pass
        try:
            return ast.literal_eval(candidate)
        except Exception:
            pass
    return cleaned


def extract_markdown_section(text: str, label: str) -> str:
    import re

    patterns = [
        rf"\*\*{label}\*\*[:：]?\s*(.+?)(?=\n\s*\*\*[^*]+\*\*|\Z)",
        rf"##\s*{label}\s*\n(.+?)(?=\n##\s+|\Z)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.S)
        if match:
            return match.group(1).strip()
    return ""


def parse_info_result(text: str) -> dict:
    cleaned = clean_model_text(text)
    people_raw = extract_markdown_section(cleaned, "人物信息")
    background = extract_markdown_section(cleaned, "故事背景")
    introduction = extract_markdown_section(cleaned, "简介")
    people = parse_pythonish(people_raw)
    if not isinstance(people, list):
        people = [people_raw] if people_raw else []
    return {
        "人物信息": [str(x).strip() for x in people if str(x).strip()],
        "故事背景": background,
        "简介": introduction,
    }


def normalize_summary_result(obj) -> list[dict]:
    if isinstance(obj, list):
        out = []
        for item in obj:
            if not isinstance(item, dict):
                continue
            char_map = item.get("主要人物和他们的行为", {})
            content = str(item.get("内容", "") or "")
            if isinstance(char_map, dict) and content:
                out.append({"主要人物和他们的行为": char_map, "内容": content})
        return out
    return []


def normalize_outline_result(obj) -> list[dict]:
    if isinstance(obj, list):
        out = []
        for item in obj:
            if not isinstance(item, dict):
                continue
            char_map = item.get("主要人物和他们的行为", {})
            story = item.get("故事情节", {})
            if isinstance(char_map, dict) and isinstance(story, dict):
                out.append({"主要人物和他们的行为": char_map, "故事情节": story})
        return out
    return []


def normalize_detail_result(obj) -> list[dict]:
    if isinstance(obj, list):
        out = []
        for item in obj:
            if not isinstance(item, dict):
                continue
            title = str(item.get("章节标题", "") or "")
            content = str(item.get("细纲内容", "") or "")
            if title and content:
                out.append({"章节标题": title, "细纲内容": content})
        return out
    return []


def info_prompt() -> str:
    return "\n".join([
        "你是一位擅长长篇网文策划的小说助手。",
        "请根据给定的小说标题和分类，生成便于后续创作的基础设定。",
        "",
        "请严格按以下 Markdown 结构输出，不要输出额外解释：",
        "## 人物信息",
        "用 Python 列表字面量输出 5-8 个主要人物名，例如：['角色A', '角色B']",
        "",
        "## 故事背景",
        "写一段 180-280 字的完整背景说明，要交代世界状态、主要矛盾和环境压力。",
        "",
        "## 简介",
        "写一段 320-520 字的完整简介，要交代主线冲突、关键人物关系、阶段推进和悬念。",
        "",
        f"小说标题：{NOVEL_TITLE}",
        f"分类：{repr(CATEGORIES)}",
    ])


def summary_prompt(info_result: dict) -> str:
    return "\n".join([
        "你是一位资深网文策划编辑，请把给定的小说基础信息扩展成高质量梗概样本。",
        "只允许输出一个 Python 列表字面量，格式固定如下：",
        "[{'主要人物和他们的行为': {...}, '内容': '...'}]",
        "",
        "要求：",
        "1. 只输出 1 个 item。",
        "2. “主要人物和他们的行为”里保留 5-7 个主要人物，每个人的职责、立场、行动方式必须不同，不能写成同一句话换名字。",
        "3. “内容”必须写成详细梗概，不少于 650 字，明确写出触发事件、调查推进、关系变化、阶段升级和阶段性结局。",
        "4. 不要写成简介，不要过度压缩，不要模板化复述。",
        "",
        f"小说标题：{NOVEL_TITLE}",
        f"分类：{repr(CATEGORIES)}",
        f"人物信息：{repr(info_result.get('人物信息', []))}",
        f"故事背景：{info_result.get('故事背景', '')}",
        f"简介：{info_result.get('简介', '')}",
    ])


def outline_prompt(summary_item: dict) -> str:
    return "\n".join([
        "任务：生成分卷大纲。",
        "只允许输出如下 Python 列表字面量：",
        "[{'主要人物和他们的行为': {...}, '故事情节': {'开始': '...', '发展': '...', '高潮': '...', '结局': '...'}}, ...]",
        "",
        "要求：",
        "1. 输出 4 卷。",
        "2. 每一卷的人物行为都要紧贴该卷走向变化，不能把上一卷的说法原样复用。",
        "3. 每卷的“开始/发展/高潮/结局”都要写成完整段落，每段建议 120-220 字，明确目标、阻力、代价和结果。",
        "4. 四卷必须形成明显递进：立局、深入、对撞、收束。",
        "5. 禁止空泛总结和模板化表达。",
        "",
        f"小说标题：{NOVEL_TITLE}",
        f"主要人物和他们的行为：{repr(summary_item.get('主要人物和他们的行为', {}))}",
        f"梗概：{summary_item.get('内容', '')}",
    ])


def detail_prompt(outline_item: dict, info_result: dict, chapter_count: int = 8) -> str:
    story_map = outline_item.get("故事情节", {})
    return "\n".join([
        "你是一位擅长网文章节策划的创作编辑，请把当前分卷大纲拆成章节细纲。",
        "只允许输出如下 Python 列表字面量：",
        "[{'章节标题': '...', '细纲内容': '...'}, ...]",
        "",
        f"要求输出 {chapter_count} 章，按顺序推进。",
        "要求：",
        "1. 章节标题要有小说感，建议 6-14 个字，不能重复，不能只是同义词替换。",
        "2. 每章“细纲内容”写成自然段，不要写标签式条目，不要写模板腔。",
        "3. 每章细纲建议 180-320 字，要包含场景、事件推进、人物互动、情绪变化和章末悬念。",
        "4. 相邻章节要有明显承接，不要只是同一情节反复改写。",
        "",
        f"小说标题：{NOVEL_TITLE}",
        f"人物信息：{repr(info_result.get('人物信息', []))}",
        f"当前卷人物行为：{repr(outline_item.get('主要人物和他们的行为', {}))}",
        "当前卷故事情节：" + " ".join([f"{k}：{v}" for k, v in story_map.items()]),
        f"小说简介：{info_result.get('简介', '')}",
    ])


def text_first_prompt(info_result: dict, summary_item: dict, chapter_outline: dict, total_chapters: int = 24) -> str:
    return "\n".join([
        "你是一位擅长模仿网文节奏的小说写作助手。",
        "请根据小说基础信息、梗概和首章细纲，创作完整首章正文。",
        "",
        "要求：",
        "1. 只输出 Markdown 正文，不要输出额外解释。",
        "2. 正文不少于 2600 字，必须写成完整可读的一章，而不是提纲扩写。",
        "3. 必须完整落下开场吸引点、第一次推进、人物互动、阶段收束和章末钩子。",
        "4. 语言自然，情节清楚，人物行为要和前文设定一致。",
        "",
        f"小说标题：{NOVEL_TITLE}",
        f"分类：{repr(CATEGORIES)}",
        f"人物信息：{repr(info_result.get('人物信息', []))}",
        f"故事背景：{info_result.get('故事背景', '')}",
        f"小说简介：{info_result.get('简介', '')}",
        f"本卷梗概：{summary_item.get('内容', '')}",
        f"主要人物和他们的行为：{repr(summary_item.get('主要人物和他们的行为', {}))}",
        f"章节信息：本小说共 {total_chapters} 章，当前为第 1 章。",
        f"第1章细纲：{chapter_outline.get('细纲内容', '')}",
        f"第1章标题：{chapter_outline.get('章节标题', '第一章')}",
    ])


def to_json_string(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def markdown_for_result(all_results: dict) -> str:
    parts = [
        f"# 五阶段联测报告：{NOVEL_TITLE}",
        "",
        f"- 分类：{' / '.join(CATEGORIES)}",
        "",
    ]
    ordered = [
        ("info_recommend", "小说信息推荐"),
        ("summary", "梗概"),
        ("outline", "大纲"),
        ("detail_outline", "细纲"),
        ("text_first", "首章正文"),
    ]
    for key, title in ordered:
        item = all_results.get(key, {})
        parts.extend([f"## {title}", ""])
        parts.append("### 原始 Markdown 返回")
        parts.append(item.get("raw_text", "").strip() or "暂无。")
        parts.extend(["", "### 解析结果", "```json", to_json_string(item.get("parsed")), "```", ""])
    return "\n".join(parts).strip() + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def json_dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ensure_paths()
    results: dict = {}
    server_proc: subprocess.Popen | None = None
    try:
        server_proc, out_log, err_log = start_server("info_recommend", ADAPTERS["info_recommend"])
        wait_server_ready()
        info_resp = call_model("info_recommend", info_prompt(), max_tokens=1800, temperature=0.75, top_p=0.93, repetition_penalty=1.08)
        info_text = extract_content(info_resp)
        info_structured = extract_structured_content(info_resp)
        info_parsed = parse_info_result(info_structured)
        results["info_recommend"] = {
            "logs": {"out": str(out_log), "err": str(err_log)},
            "response": info_resp,
            "raw_text": info_text,
            "structured_text": info_structured,
            "parsed": info_parsed,
        }
        stop_server(server_proc)
        server_proc = None

        server_proc, out_log, err_log = start_server("summary", ADAPTERS["summary"])
        wait_server_ready()
        summary_resp = call_model("summary", summary_prompt(info_parsed), max_tokens=2600, temperature=0.78, top_p=0.94, repetition_penalty=1.15)
        summary_text = extract_content(summary_resp)
        summary_structured = extract_structured_content(summary_resp)
        summary_parsed = normalize_summary_result(parse_pythonish(summary_structured))
        results["summary"] = {
            "logs": {"out": str(out_log), "err": str(err_log)},
            "response": summary_resp,
            "raw_text": summary_text,
            "structured_text": summary_structured,
            "parsed": summary_parsed,
        }
        stop_server(server_proc)
        server_proc = None

        summary_item = summary_parsed[0] if summary_parsed else {"主要人物和他们的行为": {}, "内容": ""}
        server_proc, out_log, err_log = start_server("outline", ADAPTERS["outline"])
        wait_server_ready()
        outline_resp = call_model("outline", outline_prompt(summary_item), max_tokens=3200, temperature=0.76, top_p=0.93, repetition_penalty=1.18)
        outline_text = extract_content(outline_resp)
        outline_structured = extract_structured_content(outline_resp)
        outline_parsed = normalize_outline_result(parse_pythonish(outline_structured))
        results["outline"] = {
            "logs": {"out": str(out_log), "err": str(err_log)},
            "response": outline_resp,
            "raw_text": outline_text,
            "structured_text": outline_structured,
            "parsed": outline_parsed,
        }
        stop_server(server_proc)
        server_proc = None

        outline_item = outline_parsed[0] if outline_parsed else {"主要人物和他们的行为": {}, "故事情节": {}}
        server_proc, out_log, err_log = start_server("detail_outline", ADAPTERS["detail_outline"])
        wait_server_ready()
        detail_resp = call_model("detail_outline", detail_prompt(outline_item, info_parsed), max_tokens=3400, temperature=0.78, top_p=0.94, repetition_penalty=1.18)
        detail_text = extract_content(detail_resp)
        detail_structured = extract_structured_content(detail_resp)
        detail_parsed = normalize_detail_result(parse_pythonish(detail_structured))
        results["detail_outline"] = {
            "logs": {"out": str(out_log), "err": str(err_log)},
            "response": detail_resp,
            "raw_text": detail_text,
            "structured_text": detail_structured,
            "parsed": detail_parsed,
        }
        stop_server(server_proc)
        server_proc = None

        chapter_item = detail_parsed[0] if detail_parsed else {"章节标题": "第一章", "细纲内容": ""}
        server_proc, out_log, err_log = start_server("text_first", ADAPTERS["text_first"])
        wait_server_ready()
        text_resp = call_model("text_first_chapter", text_first_prompt(info_parsed, summary_item, chapter_item), max_tokens=4200, temperature=0.74, top_p=0.92, repetition_penalty=1.10)
        text_first_text = extract_content(text_resp)
        results["text_first"] = {
            "logs": {"out": str(out_log), "err": str(err_log)},
            "response": text_resp,
            "raw_text": text_first_text,
            "parsed": text_first_text,
        }
        stop_server(server_proc)
        server_proc = None

        json_dump(REPORT_DIR / "five_stage_eval_raw.json", results)
        markdown = markdown_for_result(results)
        write_text(REPORT_DIR / "five_stage_eval_report.md", markdown)
        print(str(REPORT_DIR / "five_stage_eval_report.md"))
        return 0
    finally:
        stop_server(server_proc)


if __name__ == "__main__":
    sys.exit(main())
