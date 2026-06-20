import ast
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

import requests


BASE_URL = "http://127.0.0.1:54862"
REPORT_DIR = Path("reports/multi_title_quality_eval")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


BOOKS: List[Dict[str, Any]] = [
    {
        "title": "雾港焚潮手记",
        "categories": ["都市", "悬疑", "推理", "海港都市", "冷峻", "危机感", "档案", "旧照片"],
        "grouped_tags": {
            "题材": ["都市", "悬疑", "推理"],
            "时代背景": ["当代"],
            "世界设定": ["现实世界", "海上孤城"],
            "风格": ["冷峻", "电影感"],
            "情绪基调": ["紧张", "危机感", "神秘"],
            "场景方向": ["海港都市", "废弃档案馆", "雨夜都市"],
            "人物关系": ["搭档", "彼此试探", "权力博弈"],
            "剧情驱动": ["旧案重启", "证据链推进", "真相反转"],
            "核心元素": ["档案", "旧照片", "录音带", "废弃码头"],
            "篇幅": ["长篇"],
        },
    },
    {
        "title": "太虚剑冢录",
        "categories": ["仙侠", "东方玄幻", "架空古代", "宗门禁地", "宿命", "剑印", "秘境"],
        "grouped_tags": {
            "题材": ["仙侠", "东方玄幻"],
            "时代背景": ["架空古代"],
            "世界设定": ["架空世界"],
            "风格": ["史诗感", "冷峻"],
            "情绪基调": ["宿命", "压抑"],
            "场景方向": ["宗门禁地", "山门古道", "秘境遗址"],
            "人物关系": ["师徒", "宿敌", "同盟"],
            "剧情驱动": ["禁忌传承", "旧约重启", "真相反转"],
            "核心元素": ["剑印", "残卷", "古阵"],
            "篇幅": ["长篇"],
        },
    },
    {
        "title": "群星坠落协议",
        "categories": ["科幻", "星际", "近未来", "星际文明", "巨构城市", "冷峻", "危机感", "人工智能", "记忆芯片"],
        "grouped_tags": {
            "题材": ["科幻", "星际"],
            "时代背景": ["近未来"],
            "世界设定": ["星际文明", "巨构城市"],
            "风格": ["冷峻", "电影感"],
            "情绪基调": ["危机感", "失控感"],
            "场景方向": ["巨构城市", "轨道空间站", "星港中枢"],
            "人物关系": ["搭档", "互相利用", "权力博弈"],
            "剧情驱动": ["协议失效", "记忆篡改", "权限争夺"],
            "核心元素": ["人工智能", "记忆芯片", "失控终端"],
            "篇幅": ["长篇"],
        },
    },
    {
        "title": "栀子雨季未署名",
        "categories": ["青春", "校园", "言情", "治愈", "高校校园", "温柔", "细腻", "旧信件"],
        "grouped_tags": {
            "题材": ["青春", "校园", "言情"],
            "时代背景": ["当代"],
            "世界设定": ["现实世界"],
            "风格": ["细腻", "温柔", "治愈"],
            "情绪基调": ["温柔", "希望"],
            "场景方向": ["高校校园", "旧教学楼", "雨夜操场"],
            "人物关系": ["青梅竹马", "单向暗恋", "彼此试探"],
            "剧情驱动": ["关系失衡", "成长分岔", "旧误会重启"],
            "核心元素": ["旧信件", "社团档案", "雨季"],
            "篇幅": ["中篇"],
        },
    },
    {
        "title": "长安雪尽旧臣心",
        "categories": ["历史", "古代", "权谋", "皇城", "冷峻", "宿命", "密诏", "旧臣"],
        "grouped_tags": {
            "题材": ["历史", "古代", "权谋"],
            "时代背景": ["古代"],
            "世界设定": ["架空王朝"],
            "风格": ["冷峻", "克制"],
            "情绪基调": ["宿命", "克制拉扯"],
            "场景方向": ["皇城", "朝堂外苑", "深宫旧署"],
            "人物关系": ["权力博弈", "同盟", "背叛"],
            "剧情驱动": ["旧案翻案", "清洗重排", "权势倾轧"],
            "核心元素": ["密诏", "边报", "旧卷宗"],
            "篇幅": ["长篇"],
        },
    },
]


GENRE_RULES = {
    "noir": {
        "if_any": ["悬疑", "推理", "海港都市", "档案"],
        "forbidden": [],
    },
    "xianxia": {
        "if_any": ["仙侠", "玄幻", "秘境", "宗门"],
        "forbidden": ["海港都市", "旧档案馆", "记忆芯片", "人工智能"],
    },
    "sci": {
        "if_any": ["科幻", "星际", "近未来", "人工智能", "记忆芯片"],
        "forbidden": ["海港都市", "旧档案馆", "旧案重启", "关键档案", "码头", "海风", "缆绳"],
    },
    "youth": {
        "if_any": ["青春", "校园", "言情", "治愈"],
        "forbidden": ["海港都市", "旧档案馆", "记忆芯片", "权势倾轧"],
    },
    "history": {
        "if_any": ["历史", "古代", "权谋", "皇城"],
        "forbidden": ["海港都市", "记忆芯片", "人工智能", "轨道空间站"],
    },
}


def detect_mode(categories: List[str]) -> str:
    text = "、".join(categories)
    for mode, rule in GENRE_RULES.items():
        if any(token in text for token in rule["if_any"]):
            return mode
    return "noir"


def grouped_tags_for_prompt(grouped: Dict[str, List[str]]) -> str:
    lines = []
    ordered_keys = ["篇幅", "风格", "时代背景", "世界设定", "题材", "情绪基调", "场景方向", "人物关系", "剧情驱动", "核心元素"]
    for key in ordered_keys:
        values = grouped.get(key, [])
        if values:
            lines.append(f"{key}：{'、'.join(values)}")
    return "\n".join(lines)


def post_prompt(prompt: str, timeout: int = 240) -> Dict[str, Any]:
    payload = {"model": "local", "messages": [{"role": "user", "content": prompt}], "stream": False}
    started = time.time()
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, timeout=timeout)
    elapsed = round(time.time() - started, 2)
    response.raise_for_status()
    obj = response.json()
    content = obj["choices"][0]["message"]["content"]
    return {"status": response.status_code, "elapsed": elapsed, "content": content}


def parse_literal(text: str) -> Any:
    source = str(text or "").strip()
    try:
        return ast.literal_eval(source)
    except Exception:
        return None


def build_info_prompt(book: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "角色：",
            "你是一位资深小说策划编辑，擅长把作品标题与标签体系扩写成可直接进入创作流程的基础设定文档。",
            "请根据小说标题、标签明细和标签大类，输出一份信息密度高、可直接用于后续梗概、大纲和正文创作的小说信息。",
            "",
            "输入：",
            "小说标题：",
            book["title"],
            "",
            "标签明细：",
            str(book["categories"]),
            "",
            "标签大类与标签对应关系：",
            grouped_tags_for_prompt(book["grouped_tags"]),
            "",
            "输出：",
            "只输出以下三个板块，且标题必须严格保持原样、顺序不得打乱，不要输出 JSON、markdown 代码块、解释或多余前后缀：",
            "人物信息：",
            "- 姓名：身份/性格核心/目标/与主线关系",
            "",
            "故事背景：",
            "第 1 段……",
            "",
            "简介：",
            "第 1 段……",
        ]
    )


def build_summary_prompt(book: Dict[str, Any], info_text: str) -> str:
    characters = extract_section(info_text, "人物信息", ["故事背景", "简介"])
    background = extract_section(info_text, "故事背景", ["简介"])
    intro = extract_section(info_text, "简介", [])
    return "\n".join(
        [
            "角色：",
            "你是一位资深网文策划编辑，请把小说底稿整理成一份可直接进入分卷规划与正文创作的全书梗概。",
            "",
            "固定输出：",
            "[{'主要人物和他们的行为': {...}, '内容': '...'}]",
            "",
            "输入底稿：",
            f"小说标题：{book['title']}",
            f"分类：{book['categories']}",
            "底稿核心人物设定：",
            characters,
            "故事背景：",
            background,
            "小说简介：",
            intro,
        ]
    )


def build_outline_prompt(book: Dict[str, Any], info_text: str, summary_text: str) -> str:
    characters = extract_section(info_text, "人物信息", ["故事背景", "简介"])
    background = extract_section(info_text, "故事背景", ["简介"])
    intro = extract_section(info_text, "简介", [])
    summary_obj = parse_literal(summary_text) or []
    summary_item = summary_obj[0] if isinstance(summary_obj, list) and summary_obj else {}
    summary_char_map = summary_item.get("主要人物和他们的行为", {})
    summary_content = str(summary_item.get("内容", ""))
    return "\n".join(
        [
            "角色：",
            "你是一位擅长长篇网文结构设计的策划编辑，请根据小说底稿与全书梗概，生成 4 卷递进清晰的分卷大纲。",
            "",
            "只允许输出如下结构的列表字符串：",
            "[",
            "  {'主要人物和他们的行为': {...}, '故事情节': {'开始': '...', '发展': '...', '高潮': '...', '结局': '...'}},",
            "  ...",
            "]",
            "",
            "输入信息：",
            f"小说标题：{book['title']}",
            f"分类：{book['categories']}",
            "底稿核心人物设定：",
            characters,
            "当前梗概锁定的人物职责：",
            "\n".join(f"{k}：{v}" for k, v in summary_char_map.items()) or "暂无",
            "故事背景：",
            background,
            "小说简介：",
            intro,
            "全书梗概：",
            summary_content,
        ]
    )


def build_detail_prompt(book: Dict[str, Any], info_text: str, summary_text: str, outline_text: str, chapter_count: int = 4) -> str:
    characters = extract_section(info_text, "人物信息", ["故事背景", "简介"])
    background = extract_section(info_text, "故事背景", ["简介"])
    intro = extract_section(info_text, "简介", [])
    outline_obj = parse_literal(outline_text) or []
    first_volume = outline_obj[0] if isinstance(outline_obj, list) and outline_obj else {}
    outline_char_map = first_volume.get("主要人物和他们的行为", {})
    story = first_volume.get("故事情节", {})
    volume_summary = " ".join(str(story.get(key, "")) for key in ["开始", "发展", "高潮", "结局"]).strip()
    return "\n".join(
        [
            "角色：",
            "你是一位长篇网文章节策划，请把当前分卷内容拆成递进明确、可直接用于正文创作的章节细纲。",
            "",
            "固定输出：",
            "[{'章节标题': str, '细纲内容': str}, ...]",
            f"共 {chapter_count} 章，按列表顺序递进。",
            "",
            "输入信息：",
            f"标题：{book['title']}",
            f"分类：{book['categories']}",
            "底稿核心人物设定：",
            characters,
            "当前分卷人物推进重点：",
            "\n".join(f"{k}：{v}" for k, v in outline_char_map.items()) or "暂无",
            "故事背景：",
            background,
            "小说简介：",
            intro,
            "当前分卷梗概：",
            volume_summary,
        ]
    )


def build_text_prompt(book: Dict[str, Any], info_text: str, summary_text: str, detail_text: str) -> str:
    background = extract_section(info_text, "故事背景", ["简介"])
    intro = extract_section(info_text, "简介", [])
    characters = extract_section(info_text, "人物信息", ["故事背景", "简介"])
    summary_obj = parse_literal(summary_text) or []
    summary_item = summary_obj[0] if isinstance(summary_obj, list) and summary_obj else {}
    summary_content = str(summary_item.get("内容", ""))
    summary_char_map = summary_item.get("主要人物和他们的行为", {})
    detail_obj = parse_literal(detail_text) or []
    first_chapter = detail_obj[0] if isinstance(detail_obj, list) and detail_obj else {}
    chapter_outline = str(first_chapter.get("细纲内容", ""))
    return "\n".join(
        [
            "角色：",
            "你是一位擅长模仿网文风格的小说写作助手。请根据小说全局信息与第 1 章细纲，创作完整开篇正文。",
            "",
            "输入：",
            "1. 小说基础信息：标题、分类、简介、本卷梗概、主要人物和他们的行为。",
            "2. 小说章节信息：总章节数与当前章节位置。",
            "3. 开篇细纲：第 1 章的关键场景、事件、对话与情感变化。",
            "",
            "输出要求：",
            "- 只输出正文，不输出解释、标签或代码块。",
            "- 字数建议 1800-2600 字，最多不超过 3000 字。",
            "",
            "**小说标题**:",
            book["title"],
            "",
            "**分类**:",
            str(book["categories"]),
            "",
            "**故事背景**:",
            background,
            "",
            "**小说简介**:",
            intro,
            "",
            "**本卷梗概**:",
            summary_content,
            "",
            "**底稿核心人物设定**:",
            characters,
            "",
            "**当前阶段人物推进重点**:",
            "\n".join(f"{k}：{v}" for k, v in summary_char_map.items()) or "暂无",
            "",
            "**小说章节信息**:",
            "本小说共有 120 章，当前是开篇第 1 章。",
            "",
            "**第 1 章细纲**:",
            chapter_outline,
        ]
    )


def extract_section(text: str, label: str, stop_labels: List[str]) -> str:
    source = str(text or "")
    start = re.search(rf"{re.escape(label)}\s*[:：]", source)
    if not start:
        return ""
    tail = source[start.end():]
    end = len(tail)
    for stop in stop_labels:
        match = re.search(rf"\n\s*{re.escape(stop)}\s*[:：]", tail)
        if match and match.start() < end:
            end = match.start()
    return tail[:end].strip()


def extract_person_names(info_text: str) -> List[str]:
    names: List[str] = []
    section = extract_section(info_text, "人物信息", ["故事背景", "简介"])
    for line in section.splitlines():
        match = re.match(r"\s*-?\s*([\u4e00-\u9fff]{2,4})\s*[:：]", line.strip())
        if match:
            names.append(match.group(1))
    return names


def text_flags(mode: str, text: str) -> List[str]:
    issues: List[str] = []
    for token in GENRE_RULES[mode]["forbidden"]:
        if token in text:
            issues.append(f"contains_forbidden:{token}")
    return issues


def similarity_flags(outline_obj: Any) -> List[str]:
    issues: List[str] = []
    if not isinstance(outline_obj, list) or len(outline_obj) != 4:
        return ["outline_not_4_items"]
    stage_texts: Dict[str, List[str]] = {"开始": [], "发展": [], "高潮": [], "结局": []}
    for item in outline_obj:
        story = item.get("故事情节", {}) if isinstance(item, dict) else {}
        for key in stage_texts:
            stage_texts[key].append(str(story.get(key, "")))
    for key, values in stage_texts.items():
        unique = len(set(v.strip() for v in values if v.strip()))
        if unique < 4:
            issues.append(f"outline_stage_overlap:{key}:{unique}/4")
    return issues


def evaluate_book(book: Dict[str, Any]) -> Dict[str, Any]:
    mode = detect_mode(book["categories"])
    result: Dict[str, Any] = {"title": book["title"], "mode": mode, "stages": {}}

    info = post_prompt(build_info_prompt(book), timeout=180)
    info_names = extract_person_names(info["content"])
    result["stages"]["info"] = {
        **info,
        "name_count": len(info_names),
        "issues": text_flags(mode, info["content"]),
        "names": info_names,
    }

    summary = post_prompt(build_summary_prompt(book, info["content"]), timeout=240)
    summary_obj = parse_literal(summary["content"])
    summary_issues = text_flags(mode, summary["content"])
    if not isinstance(summary_obj, list) or not summary_obj:
        summary_issues.append("summary_parse_failed")
    else:
        content = str(summary_obj[0].get("内容", ""))
        if len(content) < 900:
            summary_issues.append("summary_content_short")
    result["stages"]["summary"] = {**summary, "issues": summary_issues}

    outline = post_prompt(build_outline_prompt(book, info["content"], summary["content"]), timeout=300)
    outline_obj = parse_literal(outline["content"])
    outline_issues = text_flags(mode, outline["content"]) + similarity_flags(outline_obj)
    result["stages"]["outline"] = {**outline, "issues": outline_issues}

    detail = post_prompt(build_detail_prompt(book, info["content"], summary["content"], outline["content"]), timeout=240)
    detail_obj = parse_literal(detail["content"])
    detail_issues = text_flags(mode, detail["content"])
    if not isinstance(detail_obj, list) or len(detail_obj) < 4:
        detail_issues.append("detail_parse_failed_or_too_short")
    else:
        titles = [str(item.get("章节标题", "")).strip() for item in detail_obj if isinstance(item, dict)]
        if len(set(titles)) != len(titles):
            detail_issues.append("detail_titles_repeated")
    result["stages"]["detail"] = {**detail, "issues": detail_issues}

    text = post_prompt(build_text_prompt(book, info["content"], summary["content"], detail["content"]), timeout=420)
    text_issues = text_flags(mode, text["content"])
    if len(text["content"]) < 1100:
        text_issues.append("text_too_short")
    if "只输出正文" in text["content"] or "第 1 章细纲" in text["content"]:
        text_issues.append("text_meta_leak")
    result["stages"]["text"] = {**text, "issues": text_issues}

    return result


def build_markdown_report(results: List[Dict[str, Any]]) -> str:
    lines = ["# 5 本跨题材整链质量回归", ""]
    for item in results:
        lines.append(f"## {item['title']} [{item['mode']}]")
        for stage_name in ["info", "summary", "outline", "detail", "text"]:
            stage = item["stages"][stage_name]
            issues = stage.get("issues", [])
            issue_text = "无" if not issues else "；".join(issues)
            lines.append(f"- {stage_name}: status={stage['status']} elapsed={stage['elapsed']}s issues={issue_text}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    results = []
    for book in BOOKS:
        results.append(evaluate_book(book))
    ts = int(time.time())
    data = {"generated_at": ts, "base_url": BASE_URL, "results": results}
    (REPORT_DIR / "multi_title_quality_eval_5.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "multi_title_quality_eval_5.md").write_text(build_markdown_report(results), encoding="utf-8")
    print(json.dumps({"ok": True, "report_dir": str(REPORT_DIR), "books": len(results)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
