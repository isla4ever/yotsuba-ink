from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from novel_workflow.output_contracts.artifacts_vnext import ContextManifest


_QUANTIFIED_FACT = re.compile(
    r"百分之(?:[零〇一二两三四五六七八九十百千万]+|\d+(?:\.\d+)?)"
    r"|第[零〇一二两三四五六七八九十百千万\d]+(?:章|卷|场|幕|枚|批|号|条|项|份|组|层|级)"
    r"|\d+(?:\.\d+)?(?:%|％|年|月|日|时|分|秒|枚|次|号|条|项|份|组|层|级|厘米|毫米|米|公斤|克|元|块)?"
)

_FACT_AUTHORITY_REFS = {
    "detail.chapter",
    "cast.subjects",
    "brief.world_rules",
    "previous.handoff",
    "previous.ending_excerpt",
    "previous.staged_beats",
    "story.current_state",
    "current_chapter.previous_scene",
    "scene.execution",
}

_SENTENCE_BOUNDARIES = "。！？!?\n"
_REPAIR_CONTEXT_CHARS = 180
_MAX_REPAIR_SEGMENT_CHARS = 600

_PERSON_NAME = re.compile(
    r"[赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦许何吕施张孔曹严华金魏陶姜谢"
    r"邹喻范彭鲁马方任袁唐罗薛雷贺倪汤滕殷毕郝安常乐于傅齐康伍余顾孟黄"
    r"萧尹姚邵汪毛戴宋庞熊纪舒项董梁杜阮蓝季贾江童颜郭梅林钟徐邱骆高夏"
    r"蔡田樊胡凌霍卢莫房应丁宣邓洪左石崔吉龚程邢裴陆荣翁惠曲封靳段巫焦"
    r"车侯全班仲宁栾甘厉祖武符刘景詹龙叶黎白怀蒲容向易廖耿满文寇广师聂"
    r"冷辛简饶曾沙鞠关查游权益公][\u4e00-\u9fff]{1,2}"
)
_PERSON_INTRODUCTION_PATTERNS = (
    re.compile(rf"(?:名叫|叫作|自称|署名为)(?P<name>{_PERSON_NAME.pattern})"),
    re.compile(rf"(?P<name>{_PERSON_NAME.pattern})(?:说|问|答|喊|承认|表示)(?:道|着)?"),
)
_RELATIVE_LABELS = (
    "父亲", "母亲", "父母", "哥哥", "姐姐", "弟弟", "妹妹", "妻子", "丈夫",
    "儿子", "女儿", "叔叔", "姑姑", "舅舅", "姨妈", "祖父", "祖母",
)
_DURABLE_PERSON_PATTERNS = (
    re.compile(
        rf"(?:^|[。！？!?；;，,])(?P<name>{_PERSON_NAME.pattern})"
        r"(?=从|把|拿|接|交|递|调|出|签|曾|此前|过去|原本|是|的)"
    ),
    re.compile(
        rf"(?:从|给|交给|递给|是)(?P<name>{_PERSON_NAME.pattern})"
        r"(?=手中|处|那里|的|[。！？!?；;，,])"
    ),
    re.compile(
        rf"(?P<name>{_PERSON_NAME.pattern})(?=的(?:{'|'.join(_RELATIVE_LABELS)}))"
    ),
)
_ACCESS_MARKERS = (
    "主控权限", "管理员权限", "访问权限", "调查权限", "门禁权限", "权限",
    "备用钥匙", "主钥匙", "钥匙", "门禁卡", "通行证", "密钥", "密码",
)
_DOCUMENT_MARKERS = (
    "笔迹比对报告", "尸检报告", "审计报告", "调查报告", "原始协议", "保密协议",
    "交易协议", "口供记录", "书面口供", "口供", "人事档案", "医疗档案",
    "调查档案", "卷宗", "档案", "报告", "协议", "证词", "登记簿", "名单",
    "录音", "录像", "照片", "母带", "复印件", "原件",
)
_DURABLE_STATE_VERBS = (
    "获得", "拿到", "接过", "持有", "保管", "交给", "转交", "递给", "归还",
    "找到", "发现", "调取", "出示", "签署", "提供", "藏起", "销毁", "丢失",
    "恢复", "核验", "确认", "证明", "显示", "记载", "记录",
)
_SOURCE_INSTITUTIONS = (
    "警方", "档案馆", "档案室", "银行", "医院", "市政厅", "检察院", "法院",
)
_CAREER_ROLES = (
    "警察", "刑警", "法医", "医生", "律师", "记者", "档案员", "调查员", "修复师",
    "工程师", "教授", "教师", "会计", "秘书", "助理", "经理", "主管", "官员",
)
_CAREER_HISTORY = re.compile(
    rf"(?P<name>{_PERSON_NAME.pattern}).{{0,8}}(?:曾是|曾任|曾担任|曾经担任|此前是|"
    rf"过去是|原本是|从前是).{{0,8}}(?P<role>{'|'.join(_CAREER_ROLES)})"
)


@dataclass(frozen=True, slots=True)
class QuantifiedFactRepairWindow:
    start: int
    end: int
    masked_segment: str
    left_context: str
    right_context: str

    @property
    def source_characters(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class PersistentFactViolation:
    code: str
    category: str
    evidence: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "category": self.category,
            "evidence": self.evidence,
        }


def introduced_quantified_fact_tokens(
    content: str,
    manifest: ContextManifest,
) -> tuple[str, ...]:
    """Return quantified claims that are absent from frozen story context."""

    allowed_text = "\n".join(
        snippet.text
        for snippet in manifest.snippets
        if snippet.ref in _FACT_AUTHORITY_REFS
    )
    allowed = set(_QUANTIFIED_FACT.findall(allowed_text))
    return tuple(
        dict.fromkeys(
            token for token in _QUANTIFIED_FACT.findall(content) if token not in allowed
        )
    )


def introduced_persistent_fact_violations(
    content: str,
    manifest: ContextManifest,
) -> tuple[PersistentFactViolation, ...]:
    """Find explicit durable facts that are absent from every frozen authority atom.

    This gate intentionally targets only high-confidence, state-bearing prose. It does
    not classify sensory detail, momentary action, or literary inference as Canon.
    """

    authority = _authority_segments(manifest)
    cast_names = _registered_cast_names(manifest)
    findings: list[PersistentFactViolation] = []
    for sentence in _sentences(content):
        explicit_names = _explicit_person_names(sentence)
        durable_markers_present = (
            _contains_any(sentence, _RELATIVE_LABELS)
            or _contains_any(sentence, _ACCESS_MARKERS)
            or _contains_any(sentence, _DOCUMENT_MARKERS)
            or bool(_CAREER_HISTORY.search(sentence))
        )
        names = tuple(
            dict.fromkeys(
                (
                    *explicit_names,
                    *(name for name in cast_names if name in sentence),
                    *(_durable_person_names(sentence) if durable_markers_present else ()),
                )
            )
        )
        for name in names:
            if name not in cast_names:
                findings.append(
                    PersistentFactViolation(
                        code="unregistered_scene_subject",
                        category="character",
                        evidence=_evidence_excerpt(sentence, name),
                    )
                )

        relations = tuple(label for label in _RELATIVE_LABELS if label in sentence)
        if relations and len(names) >= 2:
            for relation in relations:
                if not _authority_contains_signature(authority, (*names, relation)):
                    findings.append(
                        PersistentFactViolation(
                            code="unfrozen_family_relation",
                            category="relationship",
                            evidence=_evidence_excerpt(sentence, relation),
                        )
                    )

        access_items = _present_markers(sentence, _ACCESS_MARKERS)
        if access_items and _contains_any(sentence, _DURABLE_STATE_VERBS):
            for item in access_items:
                item_names = _fact_subject_names(sentence, item, names)
                if not _authority_contains_signature(authority, (*item_names, item)):
                    findings.append(
                        PersistentFactViolation(
                            code="unfrozen_access_or_key",
                            category="access",
                            evidence=_evidence_excerpt(sentence, item),
                        )
                    )

        documents = _present_markers(sentence, _DOCUMENT_MARKERS)
        if documents and _contains_any(sentence, _DURABLE_STATE_VERBS):
            for item in documents:
                item_names = _fact_subject_names(sentence, item, names)
                if not _authority_contains_signature(authority, (*item_names, item)):
                    findings.append(
                        PersistentFactViolation(
                            code="unfrozen_document_or_evidence",
                            category="document",
                            evidence=_evidence_excerpt(sentence, item),
                        )
                    )

        for item in (*access_items, *documents):
            clause = _marker_clause(sentence, item)
            if not _contains_any(clause, ("交给", "转交", "递给", "接过", "从")):
                continue
            sources = tuple(
                source for source in (*names, *_SOURCE_INSTITUTIONS) if source in clause
            )
            if sources and not _authority_contains_signature(authority, (*sources, item)):
                findings.append(
                    PersistentFactViolation(
                        code="unfrozen_evidence_custody",
                        category="provenance",
                        evidence=_evidence_excerpt(sentence, item),
                    )
                )

        for match in _CAREER_HISTORY.finditer(sentence):
            name = match.group("name")
            role = match.group("role")
            if not _authority_contains_signature(authority, (name, role)):
                findings.append(
                    PersistentFactViolation(
                        code="unfrozen_career_history",
                        category="history",
                        evidence=_evidence_excerpt(sentence, role),
                    )
                )
    return tuple(
        PersistentFactViolation(*values)
        for values in dict.fromkeys((item.code, item.category, item.evidence) for item in findings)
    )


def quantified_fact_repair_window(
    content: str,
    rejected_tokens: tuple[str, ...],
) -> QuantifiedFactRepairWindow:
    """Isolate and mask the smallest sentence range containing every violation."""

    tokens = tuple(dict.fromkeys(token for token in rejected_tokens if token))
    positions = [
        (index, index + len(token))
        for token in tokens
        for index in _all_occurrences(content, token)
    ]
    if not positions:
        raise ValueError("Scene fact repair requires rejected tokens in the source")
    first = min(start for start, _ in positions)
    last = max(end for _, end in positions)
    start = _sentence_start(content, first)
    end = _sentence_end(content, last)
    if end - start > _MAX_REPAIR_SEGMENT_CHARS:
        raise ValueError("Scene fact repair scope exceeds the bounded segment limit")
    segment = content[start:end]
    for token in tokens:
        segment = segment.replace(token, "[未授权量化事实]")
    if any(token in segment for token in tokens):
        raise ValueError("Scene fact repair failed to mask every rejected token")
    return QuantifiedFactRepairWindow(
        start=start,
        end=end,
        masked_segment=segment,
        left_context=content[max(0, start - _REPAIR_CONTEXT_CHARS) : start],
        right_context=content[end : end + _REPAIR_CONTEXT_CHARS],
    )


def apply_quantified_fact_repair(
    content: str,
    window: QuantifiedFactRepairWindow,
    replacement: str,
) -> str:
    replacement = replacement.strip()
    if not replacement:
        raise ValueError("Scene fact repair returned an empty replacement")
    return f"{content[:window.start]}{replacement}{content[window.end:]}"


def _all_occurrences(content: str, token: str) -> tuple[int, ...]:
    positions: list[int] = []
    cursor = 0
    while True:
        index = content.find(token, cursor)
        if index < 0:
            return tuple(positions)
        positions.append(index)
        cursor = index + len(token)


def _sentence_start(content: str, index: int) -> int:
    boundary = max(content.rfind(mark, 0, index) for mark in _SENTENCE_BOUNDARIES)
    return boundary + 1


def _sentence_end(content: str, index: int) -> int:
    boundaries = [
        position
        for mark in _SENTENCE_BOUNDARIES
        for position in [content.find(mark, index)]
        if position >= 0
    ]
    return min(boundaries) + 1 if boundaries else len(content)


def _authority_segments(manifest: ContextManifest) -> tuple[str, ...]:
    segments: list[str] = []
    for snippet in manifest.snippets:
        if snippet.ref not in _FACT_AUTHORITY_REFS:
            continue
        try:
            payload = json.loads(snippet.text)
        except (TypeError, json.JSONDecodeError):
            segments.extend(_sentences(snippet.text))
            continue
        segments.extend(_payload_segments(payload))
    return tuple(segment for segment in segments if segment)


def _payload_segments(value: Any) -> list[str]:
    if isinstance(value, dict):
        direct = [str(item) for item in value.values() if isinstance(item, (str, int, float))]
        nested = [
            segment
            for item in value.values()
            if isinstance(item, (dict, list))
            for segment in _payload_segments(item)
        ]
        return ([" ".join(direct)] if direct else []) + nested
    if isinstance(value, list):
        return [segment for item in value for segment in _payload_segments(item)]
    return [str(value)] if isinstance(value, (str, int, float)) else []


def _registered_cast_names(manifest: ContextManifest) -> tuple[str, ...]:
    snippet = next((item for item in manifest.snippets if item.ref == "cast.subjects"), None)
    if snippet is None:
        return ()
    try:
        payload = json.loads(snippet.text)
    except (TypeError, json.JSONDecodeError):
        return tuple(dict.fromkeys(_PERSON_NAME.findall(snippet.text)))
    names: list[str] = []
    for item in _walk_dicts(payload):
        name = item.get("name")
        if isinstance(name, str) and name.strip() and name.strip() not in names:
            names.append(name.strip())
    return tuple(names)


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _explicit_person_names(sentence: str) -> tuple[str, ...]:
    return tuple(
        match.group("name")
        for pattern in _PERSON_INTRODUCTION_PATTERNS
        for match in pattern.finditer(sentence)
    )


def _durable_person_names(sentence: str) -> tuple[str, ...]:
    return tuple(
        match.group("name")
        for pattern in _DURABLE_PERSON_PATTERNS
        for match in pattern.finditer(sentence)
    )


def _sentences(content: str) -> tuple[str, ...]:
    return tuple(
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？!?])|\n+", content)
        if sentence.strip()
    )


def _present_markers(content: str, markers: tuple[str, ...]) -> tuple[str, ...]:
    present: list[str] = []
    for marker in markers:
        if marker not in content:
            continue
        if any(marker in selected for selected in present):
            continue
        present.append(marker)
    return tuple(present)


def _fact_subject_names(
    sentence: str,
    marker: str,
    names: tuple[str, ...],
) -> tuple[str, ...]:
    clause = _marker_clause(sentence, marker)
    local = tuple(name for name in names if name in clause)
    return local or names[:1]


def _marker_clause(sentence: str, marker: str) -> str:
    return next(
        (clause for clause in re.split(r"[，,；;]", sentence) if marker in clause),
        sentence,
    )


def _contains_any(content: str, markers: tuple[str, ...]) -> bool:
    return any(marker in content for marker in markers)


def _authority_contains_signature(
    authority: tuple[str, ...],
    tokens: tuple[str, ...],
) -> bool:
    required = tuple(dict.fromkeys(token for token in tokens if token))
    return bool(required) and any(all(token in segment for token in required) for segment in authority)


def _evidence_excerpt(sentence: str, marker: str) -> str:
    text = sentence.strip()
    if len(text) <= 220:
        return text
    index = max(0, text.find(marker))
    start = max(0, index - 90)
    return text[start : start + 220]


__all__ = [
    "PersistentFactViolation",
    "QuantifiedFactRepairWindow",
    "apply_quantified_fact_repair",
    "introduced_persistent_fact_violations",
    "introduced_quantified_fact_tokens",
    "quantified_fact_repair_window",
]
