import base64
import hashlib
import hmac
import json
import math
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8090/front"
MODEL_URL = "http://127.0.0.1:54862"
USER_ID = 507453444
TARGET_CHARS = int(os.environ.get("FULL_CHAIN_TARGET_CHARS", "80000"))
TARGET_CHAPTER_CHARS = int(os.environ.get("FULL_CHAIN_TARGET_CHAPTER_CHARS", "2500"))
TEST_PF = int(os.environ.get("FULL_CHAIN_PF", "1"))
PF_RULES = {
    1: {"name": "投稿", "min_words": 10_000, "max_words": 80_000, "default_words": 50_000, "chapters_per_volume": 8, "max_volumes": 6},
    2: {"name": "出版", "min_words": 60_000, "max_words": 150_000, "default_words": 120_000, "chapters_per_volume": 10, "max_volumes": 12},
    3: {"name": "自定义", "min_words": 80_000, "max_words": 500_000, "default_words": 200_000, "chapters_per_volume": 10, "max_volumes": 20},
}


def normalize_pf(pf: Any) -> int:
    try:
        value = int(pf)
    except Exception:
        value = 1
    return value if value in PF_RULES else 1


def normalize_words(words: Any, pf: int) -> int:
    rule = PF_RULES[normalize_pf(pf)]
    try:
        raw = float(words)
    except Exception:
        raw = 0
    if raw > 0 and raw < 1000:
        raw *= 10000
    if raw <= 0:
        raw = rule["default_words"]
    value = max(rule["min_words"], min(rule["max_words"], round(raw)))
    return max(1000, round(value / 1000) * 1000)


def volume_ranges_for(pf: Any, chapters: Any) -> List[Dict[str, int]]:
    safe_pf = normalize_pf(pf)
    rule = PF_RULES[safe_pf]
    try:
        chapter_count = max(1, int(chapters))
    except Exception:
        chapter_count = 1
    target = int(rule["chapters_per_volume"])
    max_volumes = int(rule["max_volumes"])
    volume_count = 1 if chapter_count <= target else min(max_volumes, max(2, math.ceil(chapter_count / target)))
    ranges = []
    for idx in range(volume_count):
        start = 1 + math.floor(idx * chapter_count / volume_count)
        end = chapter_count if idx == volume_count - 1 else math.floor((idx + 1) * chapter_count / volume_count)
        ranges.append({"volume": idx + 1, "minChapter": start, "maxChapter": max(start, end)})
    return ranges


def plan_for(pf: Any, words: Any, chapters: Any = None) -> Dict[str, Any]:
    safe_pf = normalize_pf(pf)
    total_words = normalize_words(words, safe_pf)
    try:
        requested_chapters = int(chapters) if chapters is not None else 0
    except Exception:
        requested_chapters = 0
    chapter_count = max(1, math.ceil(total_words / TARGET_CHAPTER_CHARS))
    if total_words <= 0 and requested_chapters > 0:
        chapter_count = requested_chapters
    ranges = volume_ranges_for(safe_pf, chapter_count)
    return {
        "pf": safe_pf,
        "pf_name": PF_RULES[safe_pf]["name"],
        "target_chars": total_words,
        "target_chapter_chars": TARGET_CHAPTER_CHARS,
        "expected_chapters": chapter_count,
        "expected_volumes": len(ranges),
        "expected_ranges": ranges,
    }


EXPECTED_PLAN = plan_for(TEST_PF, TARGET_CHARS)
EXPECTED_CHAPTERS = EXPECTED_PLAN["expected_chapters"]
EXPECTED_VOLUMES = EXPECTED_PLAN["expected_volumes"]
EXPECTED_RANGES = EXPECTED_PLAN["expected_ranges"]
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_DIR = ROOT / "full_chain_80k_wiki_sim" / STAMP
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TITLE = f"回声雾港-八万联调-{STAMP}"
TAGS = [{"id": 1, "name": "悬疑", "isShow": 1, "categoryId": 1}]
KEYWORDS = ["声纹档案", "城市秘史", "群像悬疑", "记忆频率", "旧港失踪案"]
WORLD_TERMS = ["回声层", "声纹盐", "雾钟", "蓝潮禁区", "静默七分钟"]
WORLD_DOMAIN_TERMS = ["声纹", "回声", "雾港", "旧港", "低频", "频率", "磁带", "金属", "盐", "管道", "共鸣", "声纹井"]


WORLD_BUILDING_MD = """# 回声雾港世界观设定

## 城市与年代
雾港是一座建立在旧港区、防空洞和近海填海带上的现代滨海城市。城市常年被潮雾笼罩，旧港区地下保留大量民国时期防空洞、废弃医院管线和早期港务通信设施。

## 回声层
回声层是旧港区地下的一片异常声学结构。它会吸收人在强烈恐惧、愧疚或求救时留下的记忆频率，并把频率刻进金属、盐晶和老式磁带介质中。回声层不会主动解释真相，只保留被记录那一刻的感官碎片。

## 声纹盐
旧港地下墙面和管道上会析出细小的灰白盐粒，俗称声纹盐。声纹盐遇到特定低频震动时会短暂排列成纹路，用来指向地点、时间或一段被切断的记忆。声纹盐不能直接制造幻觉，但会放大已有记忆的错位感。

## 雾钟
雾钟是旧港灯塔退役后留下的报时装置。它每天凌晨二点十七分会发生一次无源振动，持续约十三秒。雾钟振动期间，回声层最容易被读取，也最容易把不同人的记忆频率互相串联。

## 蓝潮禁区
蓝潮禁区位于旧港区最深处，原是战时防空洞和废弃解剖室改造出的地下空间。禁区内的金属柜、旧开盘机和管线共同构成回声层的读写节点。进入蓝潮禁区后，任何人都必须保持静默七分钟，否则自身最近一次强烈情绪会被回声层记录。

## 静默七分钟
静默七分钟是旧港调查者之间流传的安全规则。进入回声层活跃区域后，前七分钟内不能说出完整姓名、不能播放未知磁带、不能用金属物敲击墙面。违反规则不会立刻致命，但会留下可被追踪的声纹锚点。

## 调查规则
磁带只是索引，不是真相本身。真正的档案藏在金属表面的微痕、声纹盐的排列和雾钟振动后的短暂回声里。每条线索都必须同时满足地点、频率和时间三个条件，才能确认它是稳定事实。

## 叙事约束
世界观只解释异常现象的规则，不替代人物动机。任何失踪案、背叛、救援和牺牲都必须由人物选择推动，不能简单归因于回声层本身。
"""


sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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
MODEL_HEADERS = {"Content-Type": "application/json;charset=utf-8"}

raw: Dict[str, Any] = {"started_at": STAMP, "user_id": USER_ID, "title": TITLE, "target_chars": TARGET_CHARS, "stages": {}}
metrics: Dict[str, Any] = {"stages": {}, "chapters": [], "wiki": [], "totals": {}}
issues: List[Dict[str, str]] = []


metrics["planning"] = {
    **EXPECTED_PLAN,
    "source": "pre_create_pf_rules",
}


def add_issue(stage: str, severity: str, message: str) -> None:
    issues.append({"stage": stage, "severity": severity, "message": message})
    print(f"[{severity}] {stage}: {message}")


def safe_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    copied = dict(kwargs)
    if "headers" in copied:
        copied["headers"] = "<headers>"
    return copied


def timed_request(stage: str, method: str, url: str, headers: Optional[Dict[str, str]] = None, **kwargs: Any) -> requests.Response:
    start = time.time()
    resp = requests.request(method, url, headers=headers or HEADERS, timeout=kwargs.pop("timeout", 1800), **kwargs)
    resp.encoding = "utf-8"
    elapsed = round(time.time() - start, 2)
    metrics["stages"][stage] = {"status_code": resp.status_code, "elapsed_seconds": elapsed}
    raw["stages"][stage] = {
        "request": {"method": method, "url": url, "kwargs": safe_kwargs(kwargs)},
        "status_code": resp.status_code,
        "elapsed_seconds": elapsed,
        "body_excerpt": resp.text[:1600],
    }
    if resp.status_code >= 400:
        add_issue(stage, "fail", f"HTTP {resp.status_code}: {resp.text[:500]}")
    return resp


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


def response_data_soft(resp: requests.Response, stage: str) -> Any:
    try:
        obj = resp.json()
    except Exception as exc:
        add_issue(stage, "warn", f"soft invalid JSON: {exc}")
        return None
    raw["stages"][stage]["response"] = obj
    if isinstance(obj, dict) and obj.get("code") not in (None, 200):
        add_issue(stage, "warn", f"soft business code={obj.get('code')} msg={obj.get('msg') or obj.get('message')}")
    return obj.get("data") if isinstance(obj, dict) and "data" in obj else obj


def post_front(stage: str, path: str, payload: Dict[str, Any]) -> Any:
    return response_data(timed_request(stage, "POST", f"{BASE_URL}{path}", json=payload), stage)


def get_front(stage: str, path: str) -> Any:
    return response_data(timed_request(stage, "GET", f"{BASE_URL}{path}"), stage)


def get_front_soft(stage: str, path: str) -> Any:
    return response_data_soft(timed_request(stage, "GET", f"{BASE_URL}{path}"), stage)


def get_model(stage: str, path: str) -> Any:
    return response_data(timed_request(stage, "GET", f"{MODEL_URL}{path}", headers=MODEL_HEADERS), stage)


def normalize_summary_updates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "volume": item.get("volume") or idx,
            "title": item.get("title") or f"第{idx}卷",
            "minChapter": item.get("minChapter") or item.get("min_chapter") or idx,
            "maxChapter": item.get("maxChapter") or item.get("max_chapter") or idx,
            "content": item.get("content") or "",
            "characterActions": item.get("characterActions") or {},
            "characters": [],
        }
        for idx, item in enumerate(items, start=1)
        if isinstance(item, dict)
    ]


def story_to_content(story: Any) -> str:
    if isinstance(story, dict):
        return "\n".join(str(story.get(k) or "") for k in ("start", "development", "climax", "end", "开始", "发展", "高潮", "结局")).strip()
    return str(story or "")


def normalize_outline_updates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    updates = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        updates.append(
            {
                "volume": item.get("volume") or idx,
                "title": item.get("title") or f"第{idx}卷",
                "minChapter": item.get("minChapter") or item.get("min_chapter") or idx,
                "maxChapter": item.get("maxChapter") or item.get("max_chapter") or idx,
                "characterActions": item.get("characterActions") or {},
                "story": item.get("story") or {},
                "content": item.get("content") or story_to_content(item.get("story")),
            }
        )
    return updates


def clean_text(text: str) -> str:
    value = str(text or "").replace("\ufeff", "").replace("\ufffd", "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"(?m)^\s*#{1,6}\s*(第[一二三四五六七八九十百零〇0-9]+章[^\n]*|正文|小说正文)\s*$", "", value)
    value = value.replace("```", "")
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def chinese_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def iter_sse_events(resp: requests.Response) -> Iterable[Tuple[str, str]]:
    event_name = "message"
    data_lines: List[str] = []
    for raw_line in resp.iter_lines(decode_unicode=False):
        if raw_line is None:
            continue
        line = raw_line.decode("utf-8", errors="replace")
        if line == "":
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip() or "message"
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif data_lines:
            data_lines[-1] += line
    if data_lines:
        yield event_name, "\n".join(data_lines)


def consume_stream(novel_id: int, chapter_id: int) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            result = consume_stream_once(novel_id, chapter_id)
            result["attempt"] = attempt
            return result
        except Exception as exc:
            last_error = exc
            add_issue(f"text_chapter_{chapter_id}", "warn", f"stream attempt {attempt} failed: {exc}")
            time.sleep(min(30, 5 * attempt))
    raise RuntimeError(f"stream failed after retries: {last_error}")


def consume_stream_once(novel_id: int, chapter_id: int) -> Dict[str, Any]:
    params = {"novelId": novel_id, "chapterId": chapter_id, "userId": USER_ID}
    start = time.time()
    first_content_at: Optional[float] = None
    parts: List[str] = []
    thinking_len = 0
    progress_events = 0
    raw_events: List[Dict[str, str]] = []
    with requests.get(f"{BASE_URL}/stream", headers=HEADERS, params=params, stream=True, timeout=2400) as resp:
        resp.encoding = "utf-8"
        if resp.status_code >= 400:
            raise RuntimeError(f"stream HTTP {resp.status_code}: {resp.text[:800]}")
        for event_name, data in iter_sse_events(resp):
            if len(raw_events) < 80:
                raw_events.append({"event": event_name, "data": data[:500]})
            if event_name == "content":
                try:
                    piece = str(json.loads(data).get("content") or "")
                except Exception:
                    piece = data
                if piece:
                    if first_content_at is None:
                        first_content_at = time.time()
                    parts.append(piece)
            elif event_name == "thinking":
                try:
                    thinking_len += len(str(json.loads(data).get("content") or ""))
                except Exception:
                    thinking_len += len(data)
            elif event_name == "progress":
                progress_events += 1
            elif event_name == "generation_error":
                raise RuntimeError(f"generation_error: {data}")
    content = clean_text("".join(parts))
    return {
        "elapsed_seconds": round(time.time() - start, 2),
        "first_content_latency_seconds": None if first_content_at is None else round(first_content_at - start, 2),
        "content_length": len(content),
        "chinese_length": chinese_len(content),
        "thinking_length": thinking_len,
        "progress_events": progress_events,
        "content": content,
        "raw_events": raw_events,
    }


def fetch_saved_chapter(chapter_id: int) -> Dict[str, Any]:
    data = get_front(f"fetch_saved_chapter_{chapter_id}", f"/chapter/getContent/{chapter_id}")
    return data if isinstance(data, dict) else {}


def finalize_text(chapter_id: int, word_number: int) -> None:
    response_data(
        timed_request(
            f"finalize_text_{chapter_id}",
            "POST",
            f"{BASE_URL}/novel/finalizeText?chapterId={chapter_id}&wordNumber={word_number}",
            json={},
        ),
        f"finalize_text_{chapter_id}",
    )


def text_ngrams(text: str, n: int = 3) -> set:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}", text or "")
    joined = "".join(tokens)
    return {joined[i : i + n] for i in range(max(0, len(joined) - n + 1))}


def overlap_ratio(a: str, b: str) -> float:
    sa = text_ngrams(a, 4)
    sb = text_ngrams(b, 4)
    if not sa or not sb:
        return 0.0
    return round(len(sa & sb) / max(1, min(len(sa), len(sb))), 4)


def keyword_hits(text: str, terms: Iterable[str]) -> List[str]:
    return [term for term in terms if term and term in text]


def top_terms(text: str, limit: int = 20) -> List[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,6}", text or "")
    banned = {"一个", "他们", "自己", "没有", "什么", "已经", "时候", "声音", "看着", "知道", "这里", "那里", "出来"}
    counts = Counter(w for w in words if w not in banned)
    return [w for w, _ in counts.most_common(limit)]


def inspect_chapter_quality(chapter: Dict[str, Any], previous: Optional[Dict[str, Any]], volume_first: bool) -> None:
    stage = f"quality_chapter_{chapter['sort']}"
    text = chapter["content"]
    if chinese_len(text) < int(TARGET_CHAPTER_CHARS * 0.82):
        add_issue(stage, "warn", f"正文偏短 chinese_len={chinese_len(text)}")
    if chinese_len(text) > int(TARGET_CHAPTER_CHARS * 1.42):
        add_issue(stage, "warn", f"正文偏长 chinese_len={chinese_len(text)}")
    if '{"content"' in text or "event:" in text or "data:" in text:
        add_issue(stage, "fail", "正文中混入 SSE/JSON 片段")
    if re.search(r"(?m)^\s*#{1,6}\s*", text):
        add_issue(stage, "warn", "正文中仍包含 Markdown 标题")
    if "那边的潮气和铁锈味一直没散" in text or "只把呼吸放得更轻" in text:
        add_issue(stage, "fail", "正文尾部混入模型端确定性桥接模板")
    hits = keyword_hits(text, WORLD_TERMS)
    domain_hits = keyword_hits(text, WORLD_DOMAIN_TERMS)
    chapter["world_term_hits"] = hits
    chapter["world_domain_hits"] = domain_hits
    if not hits and len(domain_hits) < 3 and chapter["sort"] <= 3:
        add_issue(stage, "warn", "前三章未体现世界观 Wiki 术语或领域词")
    if previous:
        ratio = overlap_ratio(previous["content"], text)
        chapter["previous_overlap_ratio"] = ratio
        if ratio > 0.38:
            add_issue(stage, "warn", f"与上一章四字片段重合偏高 overlap={ratio}")
        if chapter["sort"] == 2 and ratio > 0.3:
            add_issue(stage, "fail", f"第1章/第2章主体重复风险高 overlap={ratio}")
        prev_tail = previous["content"][-900:]
        current_head = text[:900]
        anchors = set(top_terms(prev_tail, 16))
        bridge_hits = [term for term in anchors if term in current_head]
        chapter["bridge_hits"] = bridge_hits[:10]
        if not bridge_hits:
            add_issue(stage, "warn", "章首未明显承接上一章尾段关键词")
        if volume_first and not bridge_hits:
            add_issue(stage, "warn", "分卷首章缺少上一卷尾段承接信号")


def inspect_outline_quality(chapters: List[Dict[str, Any]], volume: int, previous_titles: Dict[str, int]) -> None:
    seen: set[str] = set()
    for chapter in chapters:
        title = clean_text(str(chapter.get("title") or ""))
        if not title:
            add_issue(f"detail_title_v{volume}", "warn", "细纲章节标题为空")
            continue
        if title in seen:
            add_issue(f"detail_title_v{volume}", "fail", f"同卷章节标题重复：{title}")
        seen.add(title)
        if title in previous_titles and previous_titles[title] != volume:
            add_issue(f"detail_title_v{volume}", "fail", f"跨卷章节标题重复：{title} 已出现在第 {previous_titles[title]} 卷")
        previous_titles.setdefault(title, volume)


def inspect_planning(novel_info: Any, outline_updates: List[Dict[str, Any]]) -> None:
    actual_chapters = int(metrics.get("planning", {}).get("expected_chapters") or EXPECTED_CHAPTERS)
    if isinstance(novel_info, dict):
        for key in ("zhang", "chapterCount", "chapters"):
            if novel_info.get(key) is not None:
                try:
                    actual_chapters = int(novel_info.get(key))
                    break
                except Exception:
                    pass
    expected_chapters = int(metrics.get("planning", {}).get("expected_chapters") or EXPECTED_CHAPTERS)
    if actual_chapters is not None and actual_chapters != expected_chapters:
        add_issue("planning", "fail", f"章节数未按 {TARGET_CHAPTER_CHARS}/章 动态计算：actual={actual_chapters}, expected={expected_chapters}")

    actual_ranges = []
    for item in sorted(outline_updates, key=lambda x: int(x.get("volume") or 0)):
        try:
            actual_ranges.append((int(item.get("volume") or 0), int(item.get("minChapter") or 0), int(item.get("maxChapter") or 0)))
        except Exception:
            add_issue("planning", "fail", f"分卷范围字段不可解析：{item}")

    expected_ranges = [
        (int(item.get("volume") or 0), int(item.get("minChapter") or 0), int(item.get("maxChapter") or 0))
        for item in metrics.get("planning", {}).get("expected_ranges", EXPECTED_RANGES)
        if isinstance(item, dict)
    ]
    if actual_ranges and actual_ranges != expected_ranges:
        add_issue("planning", "fail", f"分卷范围不符合均分规划：actual={actual_ranges}, expected={expected_ranges}")


def wiki_snapshot(stage: str, novel_id: int) -> Dict[str, Any]:
    status = get_front_soft(f"wiki_status_{stage}", f"/novelWiki/{novel_id}/status")
    continuity = get_front_soft(f"wiki_continuity_{stage}", f"/novelWiki/{novel_id}/continuity")
    searches = {}
    for term in WORLD_TERMS[:3]:
        try:
            searches[term] = get_model(f"wiki_search_{stage}_{term}", f"/v1/novel/wiki/projects/{novel_id}/search?user_id={USER_ID}&q={term}")
        except Exception as exc:
            searches[term] = {"error": repr(exc)}
    snap = {"stage": stage, "status": status, "continuity": continuity, "searches": searches}
    metrics["wiki"].append(snap)
    return snap


def write_reports() -> None:
    fail_count = sum(1 for i in issues if i["severity"] == "fail")
    warn_count = sum(1 for i in issues if i["severity"] == "warn")
    metrics["totals"]["fail_count"] = fail_count
    metrics["totals"]["warn_count"] = warn_count
    (REPORT_DIR / "worldbuilding.md").write_text(WORLD_BUILDING_MD, encoding="utf-8")
    (REPORT_DIR / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "issues.md").write_text(
        "# Issues\n\n" + ("\n".join(f"- [{i['severity']}] {i['stage']}: {i['message']}" for i in issues) if issues else "- 未发现 fail/warn 项。"),
        encoding="utf-8",
    )
    lines = [
        "# Full Chain 80k Wiki Simulation",
        "",
        f"- started_at: {STAMP}",
        f"- novel_id: {raw.get('novel_id')}",
        f"- title: {TITLE}",
        f"- target_chars: {TARGET_CHARS}",
        f"- target_chapter_chars: {TARGET_CHAPTER_CHARS}",
        f"- expected_chapters: {metrics.get('planning', {}).get('expected_chapters', EXPECTED_CHAPTERS)}",
        f"- expected_volumes: {metrics.get('planning', {}).get('expected_volumes', EXPECTED_VOLUMES)}",
        f"- expected_ranges: {metrics.get('planning', {}).get('expected_ranges')}",
        f"- generated_chars: {metrics['totals'].get('generated_chars', 0)}",
        f"- generated_chinese_chars: {metrics['totals'].get('generated_chinese_chars', 0)}",
        f"- fail_count: {fail_count}",
        f"- warn_count: {warn_count}",
        "",
        "| stage | status | elapsed(s) | notes |",
        "|---|---:|---:|---|",
    ]
    for stage, item in metrics["stages"].items():
        lines.append(f"| {stage} | {item.get('status_code')} | {item.get('elapsed_seconds')} | {item.get('note', '')} |")
    lines += ["", "## Chapters"]
    for chapter in metrics["chapters"]:
        lines.append(
            f"- ch{chapter.get('sort'):03d} v{chapter.get('volume')} id={chapter.get('id')} chars={chapter.get('content_length')} cn={chapter.get('chinese_length')} first={chapter.get('first_content_latency_seconds')}s elapsed={chapter.get('elapsed_seconds')}s wiki_terms={','.join(chapter.get('world_term_hits') or [])} domain_terms={','.join((chapter.get('world_domain_hits') or [])[:6])} overlap={chapter.get('previous_overlap_ratio', '')}"
        )
    lines += ["", "## Wiki"]
    for snap in metrics["wiki"]:
        status = snap.get("status") if isinstance(snap.get("status"), dict) else {}
        counts = status.get("counts") if isinstance(status.get("counts"), dict) else {}
        lines.append(f"- {snap.get('stage')}: docs={counts.get('documents')} chapters={counts.get('chapter_summaries')} foreshadows={counts.get('foreshadow_states')}")
    (REPORT_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"REPORT_DIR={REPORT_DIR}")
    print(f"NOVEL_ID={raw.get('novel_id')}")
    print(f"FAIL_COUNT={fail_count}")
    print(f"WARN_COUNT={warn_count}")
    print(f"GENERATED_CHARS={metrics['totals'].get('generated_chars', 0)}")
    print(f"GENERATED_CHINESE_CHARS={metrics['totals'].get('generated_chinese_chars', 0)}")


def main() -> int:
    total_chars = 0
    total_chinese = 0
    previous_chapter: Optional[Dict[str, Any]] = None
    previous_titles: Dict[str, int] = {}
    try:
        health = requests.get(f"{MODEL_URL}/health", timeout=10)
        health.encoding = "utf-8"
        raw["model_health"] = health.json()
        if raw["model_health"].get("mode") != "online":
            add_issue("health", "fail", f"model mode={raw['model_health'].get('mode')}")

        template = post_front("template", "/template", {"title": TITLE, "tags": TAGS, "creativeKeywords": KEYWORDS})
        if not isinstance(template, dict):
            raise RuntimeError("template response invalid")
        metrics["stages"]["template"]["note"] = f"chars={len(json.dumps(template, ensure_ascii=False))}"

        topology = template.get("topology") if isinstance(template.get("topology"), dict) else {}
        characters = template.get("characters") if isinstance(template.get("characters"), list) else []
        intro = str(template.get("introduction") or "一部发生在雾港旧档案体系中的群像悬疑小说。")
        planned_chapters = int(metrics.get("planning", {}).get("expected_chapters") or EXPECTED_CHAPTERS)
        create_payload = {
            "title": TITLE,
            "introduction": intro,
            "img": "https://mugenovel.com/default-cover.png",
            "tags": TAGS,
            "characters": characters,
            "creativeKeywords": KEYWORDS,
            "isQr": 1,
            "pf": TEST_PF,
            "zi": TARGET_CHARS,
            "zhang": planned_chapters,
        }
        novel_id = int(post_front("create_novel", "/novel/create", create_payload))
        raw["novel_id"] = novel_id
        novel_info = get_front("novel_info_after_create", f"/novel/novels/{novel_id}")
        if isinstance(novel_info, dict):
            actual_pf = normalize_pf(novel_info.get("pf", TEST_PF))
            actual_words = novel_info.get("zi", TARGET_CHARS)
            actual_chapters = novel_info.get("zhang", planned_chapters)
            metrics["planning"] = {
                **plan_for(actual_pf, actual_words, actual_chapters),
                "source": "novel_info_after_create",
                "novel_info": {
                    "pf": novel_info.get("pf"),
                    "zi": novel_info.get("zi"),
                    "zhang": novel_info.get("zhang"),
                },
            }

        post_front(
            "upload_worldbuilding",
            f"/novelWiki/{novel_id}/documents",
            {"title": "回声雾港世界观设定", "sourceType": "worldbuilding", "sourceStage": "pre_summary", "content": WORLD_BUILDING_MD},
        )
        if topology:
            post_front(
                "persist_topology",
                f"/novelWiki/{novel_id}/topology",
                {"title": TITLE, "sourceStage": "info_recommend", "persist": True, "topology": topology, "infoRecommend": json.dumps(template, ensure_ascii=False)},
            )
        wiki_snapshot("after_worldbuilding", novel_id)

        summary = get_front("summary", f"/getCompletionsSummary?novelId={novel_id}&type=1")
        if not isinstance(summary, list) or not summary:
            raise RuntimeError("summary response invalid")
        post_front("save_summary", "/novel/updateSummaryAndHistory", {"nId": str(novel_id), "version": 1, "type": 1, "updates": normalize_summary_updates(summary)})
        post_front("finalize_summary", f"/novel/finalizeSynopsis?n_id={novel_id}", {})
        wiki_snapshot("after_summary", novel_id)

        outline = get_front("outline", f"/getCompletionsOutline?novelId={novel_id}&type=2")
        if not isinstance(outline, list) or not outline:
            raise RuntimeError("outline response invalid")
        outline_updates = normalize_outline_updates(outline)
        post_front("save_outline", "/novel/updateOutlineAndHistory", {"nId": str(novel_id), "version": 1, "type": 2, "updates": outline_updates})
        inspect_planning(novel_info, outline_updates)
        post_front("finalize_outline", f"/novel/finalizeOutline?n_id={novel_id}", {})
        wiki_snapshot("after_outline", novel_id)

        volumes = sorted({int(item.get("volume") or 1) for item in outline_updates})
        for volume in volumes:
            detail = post_front(f"detail_outline_v{volume}", "/detailOutline", {"novelId": str(novel_id), "volume": volume})
            if not isinstance(detail, list) or not detail:
                raise RuntimeError(f"detail outline invalid for volume {volume}")
            chapters = get_front(f"chapters_v{volume}", f"/novel/chapters/{novel_id}/{volume}")
            if not isinstance(chapters, list) or not chapters:
                add_issue(f"chapters_v{volume}", "fail", "empty chapter list after detail outline")
                continue
            inspect_outline_quality([item for item in chapters if isinstance(item, dict)], volume, previous_titles)
            save_items = [
                {
                    "id": item.get("id"),
                    "doId": item.get("doId"),
                    "sort": item.get("sort"),
                    "title": item.get("title"),
                    "content": item.get("content"),
                    "isDg": item.get("isDg"),
                }
                for item in chapters
                if isinstance(item, dict)
            ]
            post_front(f"save_detail_v{volume}", "/chapter/updateChapters", {"nId": int(novel_id), "volume": volume, "streamList": save_items})
            post_front(f"finalize_detail_v{volume}", "/chapter/finalize", {"nId": int(novel_id), "volume": volume})
            wiki_snapshot(f"after_detail_v{volume}", novel_id)

            finalized = get_front(f"finalized_chapters_v{volume}", f"/novel/chapters/{novel_id}/{volume}")
            if not isinstance(finalized, list):
                finalized = chapters
            volume_first = True
            for chapter in sorted(finalized, key=lambda x: int(x.get("sort") or 0)):
                chapter_id = int(chapter.get("id"))
                sort = int(chapter.get("sort") or 0)
                stage = f"text_chapter_{sort}"
                result = consume_stream(novel_id, chapter_id)
                raw["stages"][stage] = {k: v for k, v in result.items() if k != "content"}
                saved = fetch_saved_chapter(chapter_id)
                saved_text = clean_text(str(saved.get("text") or result["content"]))
                if not saved_text:
                    saved_text = result["content"]
                if '{"content"' in result["content"] and '{"content"' not in saved_text:
                    add_issue(stage, "warn", "前端流式解析内容含 JSON 片段，但后端持久化内容已清洗")
                if len(saved_text) + 200 < len(result["content"]):
                    metrics["stages"].setdefault(stage, {})["note"] = "saved text shorter than streamed text after cleanup"
                chapter_metric = {
                    "id": chapter_id,
                    "sort": sort,
                    "volume": volume,
                    "title": chapter.get("title"),
                    "content_length": len(saved_text),
                    "chinese_length": chinese_len(saved_text),
                    "stream_content_length": len(result["content"]),
                    "stream_chinese_length": chinese_len(result["content"]),
                    "thinking_length": result["thinking_length"],
                    "first_content_latency_seconds": result["first_content_latency_seconds"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "attempt": result.get("attempt", 1),
                    "content": saved_text,
                }
                inspect_chapter_quality(chapter_metric, previous_chapter, volume_first)
                metrics["chapters"].append({k: v for k, v in chapter_metric.items() if k != "content"})
                (REPORT_DIR / f"chapter_{sort:03d}.md").write_text(saved_text, encoding="utf-8")
                finalize_text(chapter_id, chinese_len(saved_text))
                total_chars += len(saved_text)
                total_chinese += chinese_len(saved_text)
                previous_chapter = chapter_metric
                volume_first = False
                wiki_snapshot(f"after_chapter_{sort}", novel_id)

        metrics["totals"]["generated_chars"] = total_chars
        metrics["totals"]["generated_chinese_chars"] = total_chinese
        expected_chapters = int(metrics.get("planning", {}).get("expected_chapters") or EXPECTED_CHAPTERS)
        if len(metrics["chapters"]) != expected_chapters:
            add_issue("total_chapters", "fail", f"generated chapters mismatch: actual={len(metrics['chapters'])}, expected={expected_chapters}")
        if total_chars < TARGET_CHARS:
            add_issue("total_length", "warn", f"generated below target: {total_chars}")
    except Exception as exc:
        raw["fatal_error"] = repr(exc)
        add_issue("full_chain", "fail", repr(exc))
    finally:
        write_reports()
    return 0 if not any(i["severity"] == "fail" for i in issues) else 1


if __name__ == "__main__":
    raise SystemExit(main())
