from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterBibleArtifact,
    DetailArtifact,
    StoryBriefArtifact,
    StorySpineArtifact,
    VolumeArchitectureArtifact,
)
from novel_workflow.quality.custody_contracts import (
    CUSTODY_ENTRY_MARKERS,
    CUSTODY_PLACE_MARKERS,
    CUSTODY_RELEASE_MARKERS,
    CUSTODY_STATE_MARKERS,
)


class NarrativeContractFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    source_refs: list[str] = Field(default_factory=list, max_length=24)
    evidence: str = Field(min_length=1, max_length=2000)
    required_fix: str = Field(min_length=1, max_length=2000)


class IdentityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(min_length=1, max_length=120)
    property_key: str = Field(min_length=1, max_length=120)
    target_label: str = Field(min_length=1, max_length=120)
    target_subject_id: str = Field(default="", max_length=120)
    source_ref: str = Field(min_length=1, max_length=180)


class ClueLifecycleProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clue_id: str = Field(pattern=r"^clue-[a-f0-9]{16}$")
    label: str = Field(min_length=1, max_length=80)
    mention_refs: list[str] = Field(min_length=1, max_length=2000)
    source_labels: list[str] = Field(default_factory=list, max_length=24)
    transfer_refs: list[str] = Field(default_factory=list, max_length=200)
    verification_refs: list[str] = Field(default_factory=list, max_length=200)
    payoff_refs: list[str] = Field(default_factory=list, max_length=200)
    central: bool = False


class NarrativeContractReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_bindings: list[IdentityBinding] = Field(default_factory=list)
    clues: list[ClueLifecycleProjection] = Field(default_factory=list)
    findings: list[NarrativeContractFinding] = Field(default_factory=list)


_PERSON_NAME = re.compile(
    r"[赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭鲁韦昌马苗凤花方俞任袁柳唐罗薛雷贺倪汤滕殷毕郝邬安常乐于傅皮卞齐康伍余元顾孟黄萧尹姚邵汪祁毛禹狄米贝明臧计伏成戴宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程邢裴陆荣翁荀羊惠甄曲封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘厉祖武符刘景詹束龙叶司韶郜黎薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎慕连茹习艾鱼容向古易戈廖庾终步都耿满弘匡国文寇广禄阙东欧利师巩聂晁勾敖融冷辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公]"
    r"[\u4e00-\u9fff]{1,2}"
)
_RELATIVE_LABELS = ("父亲", "母亲", "叔叔", "姑姑", "哥哥", "姐姐", "妻子", "丈夫", "儿子", "女儿")
_EMPLOYMENT_ROLES = ("助理", "秘书", "下属", "雇员")
_CAUSAL_PERSON_MARKERS = (
    "绑架", "杀害", "遇害", "失踪", "作案", "复仇", "寄出", "交出", "提供",
)
_CLUE_MARKERS = (
    "转账复印件", "笔迹比对报告", "匿名信", "原始协议", "交易原件", "备用钥匙",
    "登记簿", "复印件", "信件", "信封", "卷宗", "日记", "记录", "名单",
    "账目", "协议", "原件", "报告", "口供", "证词", "便签", "照片", "相机", "纽扣",
    "胸针", "钥匙", "手稿", "录像", "录音", "母带",
)
_NAMED_CLUE_PREFIXES = ("匿名", "深蓝", "银色", "老式", "第七页", "原始", "转账", "笔迹", "交易", "备用")
_SOURCE_MARKERS = (
    "来自", "寄来", "寄出", "交出", "提供", "留下", "整理", "持有", "保管",
    "夹着", "取得", "拿到", "找到", "发现", "获得", "获取", "调取", "生成",
)
_SOURCE_GIVER_MARKERS = (
    "寄来", "寄出", "交出", "提供", "留下", "生成",
)
_SOURCE_ACQUISITION_MARKERS = (
    "取得", "拿到", "找到", "发现", "获得", "获取", "调取", "取出", "夹着",
)
_DIRECT_SOURCE_ACQUISITION_MARKERS = ("找到", "发现", "调取", "取出", "夹着")
_TRANSFER_MARKERS = (
    "转交", "移交", "交给", "递交", "归还", "取回", "拿回", "送检",
)
_VERIFY_MARKERS = (
    "核对", "核验", "鉴定", "确认", "证实", "比对", "验证", "打开", "解锁",
)
_PAYOFF_MARKERS = (
    "公开", "提交", "证明", "揭示", "定案", "播放", "回收", "指认", "出示",
    "打开", "解锁",
)
_GENERIC_VICTIMS = ("人质", "年轻人", "陌生人", "受害者", "死者", "被绑架者", "下一个目标")
_JOB_ACTIONS = ("公开", "展示", "提交", "发布", "调查", "核验", "追查", "取得", "发现", "威胁", "否认", "抓捕", "救出", "对质", "审讯")
_JOB_ARENAS = ("发布会", "媒体", "警方", "市政厅", "档案馆", "银行", "仓库", "听证")
_DRAMATIC_ENDPOINT_PATTERNS = {
    "evidence_submission": re.compile(
        r"(?:(?:提交|递交|出示)[^，。；：！？]{0,24}(?:证据|记录|数据|文件|材料)"
        r"|(?:证据|记录|数据|文件|材料)[^，。；：！？]{0,16}(?:提交|递交|出示))"
    ),
    "authority_refusal": re.compile(
        r"(?:(?:上级|负责人|部门|郑明远)[^，。；：！？]{0,20}拒绝|拒绝(?:重启|调查|接受))"
    ),
    "public_decision": re.compile(
        r"(?:决定|计划|打算|准备)[^，。；：！？]{0,20}(?:公开|发布|公之于众)"
    ),
}
_SUBMISSION_INTENT_PREFIX = re.compile(
    r"(?:决定|准备|计划|打算|拟|意图|需要|需|将要|即将|试图|尝试|希望|承诺|同意)"
    r"[^，。；：！？]{0,10}$"
)
_CLUE_PREFIX_BOUNDARIES = (
    "发现", "找到", "取得", "拿到", "获得", "获取", "取出", "截获", "提交", "公开", "展示", "出示",
    "核对", "核验", "验证", "比对", "销毁", "解密", "调取", "整理", "保管", "转交",
    "移交", "交给", "递交", "归还", "取回", "拿回", "送检", "提供", "留下", "保存",
    "携带", "带走", "带着", "手握", "一份", "最后一份",
    "持有", "内有", "装有", "夹有", "藏有", "登记", "询问", "翻阅", "翻开", "阅读",
    "研读", "抢夺", "抢回", "保护", "保住", "传递", "记得", "利用", "收起", "根据",
    "播放", "出现在", "同时",
)
_GENERIC_CLUE_MODIFIERS = (
    "关键", "相关", "部分", "一份", "最后一份", "一本", "一册", "这本", "该本", "一叠",
    "一页", "几页", "几份", "未公开", "加密", "完整", "放弃",
)
_GENERIC_CLUE_MARKERS = (
    "复印件", "信件", "信封", "卷宗", "日记", "记录", "名单", "账目", "协议",
    "原件", "报告", "口供", "证词", "便签", "照片", "相机", "纽扣", "胸针",
    "钥匙", "手稿", "录像", "录音",
)
_SOURCE_INSTITUTIONS = (
    "数字孪生系统", "警方", "档案馆", "档案室", "银行", "医院", "市政厅",
)
_NON_PERSON_NAME_SUFFIXES = ("室", "馆", "厅", "局", "院", "站", "所", "区", "市", "部", "组", "会", "中心")
_SINGLE_MENTION_NON_CENTRAL_MARKERS = ("记录", "名单")
_CLUE_VERB_OBJECTS = {
    "日记": ("位置", "下落"),
    "记录": ("来源", "过程", "结果", "时间", "位置", "内容", "系统"),
}
_UNRESOLVED_HISTORICAL_STATUS_MARKERS = (
    "失踪", "下落不明", "生死未卜", "可能仍", "或许仍", "继续寻找",
)
_TERMINAL_HISTORICAL_STATUS_MARKERS = (
    "已死亡", "已经死亡", "确认死亡", "已牺牲", "不在人世", "遗体", "尸体",
)
_EPISTEMIC_STATUS_PREFIXES = (
    "可能", "或许", "也许", "未必", "疑似", "似乎", "恐怕", "大概",
    "认为", "觉得", "怀疑", "猜测", "担心", "传闻",
)
_GENERIC_STORED_LOCATIONS = frozenset(
    {"隐蔽", "隐蔽处", "暗处", "隐秘处", "秘密处", "某处", "别处"}
)
def build_narrative_contract_report(
    *,
    brief: StoryBriefArtifact,
    spine: StorySpineArtifact,
    cast: CharacterBibleArtifact,
    detail: DetailArtifact,
    volumes: VolumeArchitectureArtifact | None = None,
) -> NarrativeContractReport:
    names = {subject.name: subject.id for subject in cast.subjects}
    sources = _artifact_text_sources(brief, spine, cast, detail, volumes)
    bindings, identity_findings = _identity_contracts(sources, names)
    debut_findings = _debut_contracts(cast, detail)
    clues, clue_findings = _clue_contracts(sources, detail, names, brief, spine, volumes)
    findings = [
        *identity_findings,
        *debut_findings,
        *_historical_record_status_findings(brief, spine, cast, detail, volumes),
        *_duplicate_job_findings(detail),
        *_custody_handoff_findings(cast, detail),
        *_climax_responsibility_findings(spine, cast, detail),
        *clue_findings,
    ]
    return NarrativeContractReport(
        identity_bindings=bindings,
        clues=clues,
        findings=_deduplicate_findings(findings),
    )


def _historical_record_status_findings(brief, spine, cast, detail, volumes):
    higher_text = " ".join(
        [
            brief.premise,
            brief.promise,
            brief.ending_promise,
            *(f"{turn.cause} {turn.change}" for turn in spine.turns),
            spine.ending,
            *spine.open_questions,
            *(
                " ".join([volume.promise, volume.conflict, volume.climax, volume.closure])
                for volume in (volumes.volumes if volumes else [])
            ),
        ]
    )
    findings: list[NarrativeContractFinding] = []
    for subject in cast.subjects:
        if subject.kind != "historical_record":
            continue
        subject_context = " ".join(
            [subject.name, subject.function, subject.conflict_history, subject.change]
        )
        if not _subject_marker_nearby(
            f"{higher_text} {subject_context}",
            subject.name,
            _UNRESOLVED_HISTORICAL_STATUS_MARKERS,
        ):
            continue
        for chapter in detail.chapters:
            chapter_text = " ".join(
                [
                    chapter.purpose,
                    *(
                        f"{scene.objective} {scene.conflict} {scene.turn} {scene.result}"
                        for scene in chapter.scenes
                    ),
                    chapter.handoff,
                ]
            )
            terminal = _asserted_historical_terminal_marker(
                chapter_text,
                subject_name=subject.name,
            )
            if terminal:
                findings.append(
                    NarrativeContractFinding(
                        code="historical_status_overreach",
                        source_refs=[chapter.ref, subject.id],
                        evidence=(
                            f"{chapter.ref} uses '{terminal}' to resolve {subject.name}, "
                            "but the frozen planning chain keeps that status unresolved."
                        ),
                        required_fix=(
                            "Keep the historical subject's survival or death unresolved until "
                            "the frozen Spine resolves it; do not create a terminal fact in Detail."
                        ),
                    )
                )
    return findings


def _asserted_historical_terminal_marker(text: str, *, subject_name: str) -> str:
    """Return only an asserted terminal status, not a character's uncertainty."""

    for marker in _TERMINAL_HISTORICAL_STATUS_MARKERS:
        for match in re.finditer(re.escape(marker), text):
            clause_start = max(
                (text.rfind(delimiter, 0, match.start()) for delimiter in "，。；：！？、"),
                default=-1,
            )
            clause = text[clause_start + 1 : match.start()]
            if subject_name not in clause[-48:]:
                continue
            local_prefix = clause[-24:]
            if any(prefix in local_prefix for prefix in _EPISTEMIC_STATUS_PREFIXES):
                continue
            return marker
    return ""


def _subject_marker_nearby(text: str, subject_name: str, markers) -> bool:
    for match in re.finditer(re.escape(subject_name), text):
        window = text[max(0, match.start() - 64) : match.end() + 64]
        if any(marker in window for marker in markers):
            return True
    return False


def build_cast_identity_findings(
    *,
    spine: StorySpineArtifact,
    cast: CharacterBibleArtifact,
) -> list[NarrativeContractFinding]:
    names = {subject.name: subject.id for subject in cast.subjects}
    sources = [
        *((f"spine:{turn.id}", f"{turn.cause} {turn.change}") for turn in spine.turns),
        *((
            f"cast:{subject.id}",
            " ".join(
                [subject.name, subject.function, subject.background, subject.conflict_history,
                 subject.present_stakes, subject.drive, subject.change, *subject.limits]
            ),
        ) for subject in cast.subjects),
    ]
    _, findings = _identity_contracts(sources, names)
    return _deduplicate_findings(findings)


def _artifact_text_sources(brief, spine, cast, detail, volumes) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = [
        ("brief:premise", brief.premise),
        ("brief:promise", brief.promise),
        ("brief:ending", brief.ending_promise),
        *[(f"brief:world-rule-{index}", text) for index, text in enumerate(brief.world_rules, 1)],
    ]
    values.extend(
        (f"spine:{turn.id}", f"{turn.cause} {turn.change}") for turn in spine.turns
    )
    for subject in cast.subjects:
        values.append(
            (
                f"cast:{subject.id}",
                " ".join(
                    [subject.name, subject.function, subject.background, subject.conflict_history,
                     subject.present_stakes, subject.drive, subject.change, *subject.limits]
                ),
            )
        )
    if volumes is not None:
        values.extend(
            (f"volumes:{volume.id}", " ".join([volume.promise, volume.conflict, volume.climax, volume.closure]))
            for volume in volumes.volumes
        )
    for chapter in detail.chapters:
        values.append((f"detail:{chapter.ref}:purpose", chapter.purpose))
        for index, scene in enumerate(chapter.scenes, 1):
            values.append(
                (
                    f"detail:{chapter.ref}:scene-{index}",
                    " ".join([scene.place, scene.objective, scene.conflict, scene.turn, scene.result]),
                )
            )
        values.append((f"detail:{chapter.ref}:handoff", chapter.handoff))
    return values


def _identity_contracts(
    sources: Iterable[tuple[str, str]],
    names: dict[str, str],
) -> tuple[list[IdentityBinding], list[NarrativeContractFinding]]:
    bindings: list[IdentityBinding] = []
    findings: list[NarrativeContractFinding] = []
    for source_ref, text in sources:
        known_in_text = [name for name in names if name in text]
        if source_ref.startswith("detail:"):
            for person in sorted(set(_causal_person_names(text)) - names.keys()):
                if person:
                    findings.append(
                        NarrativeContractFinding(
                            code="unregistered_causal_subject",
                            source_refs=[source_ref],
                            evidence=f"具名因果主体 {person} 未绑定 Cast subject_id：{text[:240]}",
                            required_fix="在 Cast 注册持续影响因果的人物，或移除其主线责任。",
                        )
                    )
        for subject_name in known_in_text:
            subject_id = names[subject_name]
            for target in _employment_targets(text):
                if target == subject_name:
                    continue
                bindings.append(
                    IdentityBinding(
                        subject_id=subject_id,
                        property_key="affiliation.employer",
                        target_label=target,
                        target_subject_id=names.get(target, ""),
                        source_ref=source_ref,
                    )
                )
            for relation, target in _relative_targets(text, subject_name):
                bindings.append(
                    IdentityBinding(
                        subject_id=subject_id,
                        property_key=f"family.{relation}",
                        target_label=target,
                        target_subject_id=names.get(target, ""),
                        source_ref=source_ref,
                    )
                )
    grouped: dict[tuple[str, str], list[IdentityBinding]] = defaultdict(list)
    for binding in bindings:
        grouped[(binding.subject_id, binding.property_key)].append(binding)
        if not binding.target_subject_id:
            findings.append(
                NarrativeContractFinding(
                    code="unbound_identity_target",
                    source_refs=[binding.source_ref],
                    evidence=f"{binding.subject_id}.{binding.property_key} 指向未注册人物 {binding.target_label}",
                    required_fix="把具名雇主或亲属绑定到唯一 Cast subject_id（历史人物使用 historical_record）。",
                )
            )
    for (subject_id, property_key), group in grouped.items():
        targets = sorted({item.target_label for item in group})
        if len(targets) > 1:
            findings.append(
                NarrativeContractFinding(
                    code="subject_identity_conflict",
                    source_refs=sorted({item.source_ref for item in group}),
                    evidence=f"{subject_id}.{property_key} 同时指向 {targets}",
                    required_fix="冻结唯一身份关系；若关系发生变化，必须在 Spine/Detail 中写明转变事件。",
                )
            )
    return bindings, findings


def _causal_person_names(text: str) -> list[str]:
    action = "|".join(_CAUSAL_PERSON_MARKERS)
    role = "凶手|嫌疑人|举报者|人质|受害者|助理|秘书"
    name = rf"(?<![不只未可])(?P<name>{_PERSON_NAME.pattern})"
    patterns = (
        rf"{name}(?:本人)?(?:{action})",
        rf"(?:{role})(?:是|名叫|叫作)?{name}",
        rf"{name}(?:是|作为|担任).{{0,8}}(?:{role})",
    )
    return [
        name
        for pattern in patterns
        for match in re.finditer(pattern, text)
        if (name := match.group("name"))
        and not name.endswith(_NON_PERSON_NAME_SUFFIXES)
    ]


def _employment_targets(text: str) -> list[str]:
    role = "|".join(_EMPLOYMENT_ROLES)
    return [
        match.group("target")
        for match in re.finditer(
            rf"(?P<target>{_PERSON_NAME.pattern})(?:的|所带的)(?:私人|贴身|前任)?(?:{role})",
            text,
        )
    ]


def _relative_targets(text: str, subject_name: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for relation in _RELATIVE_LABELS:
        for pattern in (
            rf"(?P<target>{_PERSON_NAME.pattern})是{re.escape(subject_name)}的{relation}",
            rf"{re.escape(subject_name)}.{0,8}(?:称|确认|承认)(?P<target>{_PERSON_NAME.pattern})是(?:他|她)?的{relation}",
        ):
            result.extend((relation, match.group("target")) for match in re.finditer(pattern, text))
    return result


def _debut_contracts(cast: CharacterBibleArtifact, detail: DetailArtifact) -> list[NarrativeContractFinding]:
    first_appearance = {
        subject.id: next(
            (index for index, chapter in enumerate(detail.chapters, 1) if subject.id in chapter.cast_ids),
            None,
        )
        for subject in cast.subjects
        if subject.kind != "historical_record"
    }
    findings: list[NarrativeContractFinding] = []
    for subject in cast.subjects:
        if subject.kind == "historical_record":
            continue
        expected_end = int(subject.debut.split(":", 1)[1].split("-")[-1])
        actual = first_appearance[subject.id]
        if actual is None or actual > expected_end:
            findings.append(
                NarrativeContractFinding(
                    code="subject_debut_unfulfilled",
                    source_refs=[f"cast:{subject.id}", f"detail:chapter-{actual or 'missing'}"],
                    evidence=f"{subject.name} 的冻结 debut={subject.debut}，首次现场出场={actual or 'missing'}",
                    required_fix="在 debut 窗口内安排可见行动并写入 cast_ids，或修正 Cast 的出场窗口。",
                )
            )
    return findings


def _clue_contracts(sources, detail, names, brief, spine, volumes):
    higher_text = " ".join(
        [brief.premise, brief.promise, brief.ending_promise, *brief.world_rules,
         *(f"{turn.cause} {turn.change}" for turn in spine.turns),
         *(" ".join([volume.promise, volume.conflict, volume.climax, volume.closure]) for volume in (volumes.volumes if volumes else []))]
    )
    upstream_labels = set(_clue_labels(higher_text, names))
    upstream_specific_by_marker: dict[str, set[str]] = defaultdict(set)
    for label in upstream_labels:
        marker = _clue_marker_for_label(label)
        if marker and not _is_generic_clue_label(label):
            upstream_specific_by_marker[marker].add(label)
    detail_label_records: list[tuple[str, str, list[str]]] = []
    chapter_specific_by_marker: dict[tuple[str, str], set[str]] = defaultdict(set)
    for source_ref, text in sources:
        if not source_ref.startswith("detail:"):
            continue
        labels = _clue_labels(text, names)
        detail_label_records.append((source_ref, text, labels))
        chapter_ref = _chapter_ref(source_ref)
        for label in labels:
            marker = _clue_marker_for_label(label)
            if marker and not _is_generic_clue_label(label):
                chapter_specific_by_marker[(chapter_ref, marker)].add(label)

    mentions: dict[str, list[tuple[str, str]]] = defaultdict(list)
    recent_specific_by_marker: dict[str, list[str]] = defaultdict(list)
    for source_ref, text, labels in detail_label_records:
        chapter_ref = _chapter_ref(source_ref)
        for label in labels:
            marker = _clue_marker_for_label(label)
            upstream_matches = upstream_specific_by_marker.get(marker, set())
            canonical_label = _canonical_clue_label(
                label,
                marker=marker,
                chapter_matches=chapter_specific_by_marker.get(
                    (chapter_ref, marker),
                    set(),
                ),
                upstream_matches=upstream_matches,
                recent_matches=recent_specific_by_marker.get(marker, []),
            )
            mentions[canonical_label].append((source_ref, text))
            if marker and not _is_generic_clue_label(canonical_label):
                recent = recent_specific_by_marker[marker]
                if canonical_label in recent:
                    recent.remove(canonical_label)
                recent.append(canonical_label)
    clues: list[ClueLifecycleProjection] = []
    findings: list[NarrativeContractFinding] = []
    for label, records in sorted(mentions.items()):
        chapter_refs = _ordered_unique(_chapter_ref(ref) for ref, _ in records)
        marker = _clue_marker_for_label(label)
        central = (
            not _is_generic_clue_label(label)
            and (
                len(chapter_refs) > 1
                or (
                    label in upstream_labels
                    and marker not in _SINGLE_MENTION_NON_CENTRAL_MARKERS
                )
            )
        )
        source_labels = _clue_source_labels(records, names, detail, label)
        transfers = _refs_with_markers(records, _TRANSFER_MARKERS)
        verification = _refs_with_markers(records, _VERIFY_MARKERS)
        payoff = _refs_with_markers(records, _PAYOFF_MARKERS)
        clue = ClueLifecycleProjection(
            clue_id=f"clue-{hashlib.sha256(label.encode('utf-8')).hexdigest()[:16]}",
            label=label,
            mention_refs=chapter_refs,
            source_labels=source_labels,
            transfer_refs=transfers,
            verification_refs=verification,
            payoff_refs=payoff,
            central=central,
        )
        clues.append(clue)
        if not central:
            continue
        if not source_labels:
            findings.append(
                NarrativeContractFinding(
                    code="clue_source_missing",
                    source_refs=chapter_refs,
                    evidence=f"关键线索 {label} 没有冻结创建、持有或取得来源。",
                    required_fix="在首次投放场景写明来源主体或保管地点。",
                )
            )
        location_sources = [
            source
            for source in source_labels
            if source.startswith("place:") or source in _SOURCE_INSTITUTIONS
        ]
        if len(source_labels) > 1 and (
            len(location_sources) > 1 or not transfers
        ):
            transfer_note = (
                f"；后续转交 {transfers} 只改变持有人，不能解释独立来源地点"
                if transfers
                else "，但没有转交记录"
            )
            findings.append(
                NarrativeContractFinding(
                    code="evidence_provenance_conflict",
                    source_refs=chapter_refs,
                    evidence=(
                        f"关键线索 {label} 出现多个来源 {source_labels}{transfer_note}。"
                    ),
                    required_fix=(
                        "冻结唯一创建或保管来源；多份证据必须拆分 clue_id，"
                        "后续转交只能改变持有人，不能改写原始来源。"
                    ),
                )
            )
        if not verification or not payoff:
            missing = [name for name, refs in (("verified", verification), ("paid_off", payoff)) if not refs]
            findings.append(
                NarrativeContractFinding(
                    code="clue_lifecycle_incomplete",
                    source_refs=chapter_refs,
                    evidence=f"关键线索 {label} 缺少生命周期：{', '.join(missing)}",
                    required_fix="在 Detail 中绑定核验/转义与最终证明或明确回收章节。",
                )
            )
    mystery = any(entry in higher_text for entry in ("悬疑", "旧案", "真相", "谜", "失踪", "死亡"))
    if mystery and not any(clue.central for clue in clues):
        findings.append(
            NarrativeContractFinding(
                code="mystery_clue_chain_missing",
                source_refs=["brief", "spine", "detail"],
                evidence="悬疑承诺没有投影出可追踪的具名线索链。",
                required_fix="在 Detail 冻结至少一条来源、核验和回收完整的关键线索。",
            )
        )
    return clues, findings


def _clue_labels(text: str, names: dict[str, str] | None = None) -> list[str]:
    labels: list[str] = []
    for marker in _CLUE_MARKERS:
        for match in re.finditer(re.escape(marker), text):
            if not _is_realized_clue_mention(text, match.start()):
                continue
            if any(
                text[match.end() :].startswith(item)
                for item in _CLUE_VERB_OBJECTS.get(marker, ())
            ):
                continue
            labels.append(
                _qualified_clue_label(
                    text,
                    marker,
                    match.start(),
                    set(names or {}),
                )
            )
    return _ordered_unique(labels)


def _is_realized_clue_mention(text: str, marker_start: int) -> bool:
    prefix = text[max(0, marker_start - 28) : marker_start]
    clause = re.split(r"[，。；：！？、]", prefix)[-1]
    return not bool(
        re.search(
            r"(?:拒绝|不肯|未能|无法|尚未|没有|并无|缺乏|缺少|无)"
            r"[^，。；：！？、]{0,12}$",
            clause,
        )
        or re.search(
            r"(?:要求|希望|寻求|寻找|需要|需)"
            r"[^，。；：！？、]{0,12}(?:提供|出具|取得|找到|拿到|获取|签署)?"
            r"[^，。；：！？、]{0,4}$",
            clause,
        )
        or re.search(
            r"(?:可能|或许|疑似|似乎)[^，。；：！？、]{0,10}"
            r"(?:存有|留有|存在|留下)[^，。；：！？、]{0,8}$",
            clause,
        )
    )


def _qualified_clue_label(
    text: str,
    marker: str,
    marker_start: int,
    names: set[str],
) -> str:
    prefix = text[max(0, marker_start - 16) : marker_start]
    segment = re.split(r"[，。；：！？、\s（）()《》]", prefix)[-1]
    named_owner = next(
        (
            name
            for name in sorted(names, key=len, reverse=True)
            if segment.endswith(f"{name}的")
        ),
        "",
    )
    if named_owner:
        return f"{named_owner}{marker}"
    if "的" in segment:
        segment = segment.rsplit("的", 1)[-1]
    for boundary in _CLUE_PREFIX_BOUNDARIES:
        if boundary in segment:
            segment = segment.rsplit(boundary, 1)[-1]
    segment = segment.strip()
    if segment in names:
        return f"{segment}{marker}"
    if segment in _RELATIVE_LABELS:
        return marker
    for _ in range(3):
        previous = segment
        segment = re.sub(r"^(?:将|把|用|向|从|在|以|对)", "", segment)
        for name in sorted(names, key=len, reverse=True):
            if segment.startswith(name):
                segment = segment[len(name) :]
                break
        if segment == previous:
            break
    for modifier in _GENERIC_CLUE_MODIFIERS:
        if segment.startswith(modifier):
            segment = segment[len(modifier) :]
    if "与" in segment:
        segment = segment.rsplit("与", 1)[-1]
    if "和" in segment:
        segment = segment.rsplit("和", 1)[-1]
    if (
        not 2 <= len(segment) <= 10
        or segment in names
        or _PERSON_NAME.fullmatch(segment)
        or segment in {"这份", "该份", "这项", "该项"}
    ):
        for named_prefix in _NAMED_CLUE_PREFIXES:
            if prefix.endswith(named_prefix) and not marker.startswith(named_prefix):
                return f"{named_prefix}{marker}"
        return marker
    return f"{segment}{marker}"


def _canonical_clue_label(
    label: str,
    *,
    marker: str,
    chapter_matches: set[str],
    upstream_matches: set[str],
    recent_matches: list[str],
) -> str:
    if not marker:
        return label
    qualifier = label[: -len(marker)]
    expanded = {
        candidate
        for candidate in chapter_matches
        if candidate != label
        and (candidate_qualifier := candidate[: -len(marker)]).startswith(qualifier)
        and len(candidate_qualifier) > len(qualifier)
    }
    if len(expanded) == 1:
        return next(iter(expanded))
    if _is_generic_clue_label(label) and len(upstream_matches) == 1:
        return next(iter(upstream_matches))
    for candidate in reversed(recent_matches):
        if candidate == label or not candidate.endswith(marker):
            continue
        candidate_qualifier = candidate[: -len(marker)]
        if candidate_qualifier.startswith(qualifier) and len(candidate_qualifier) > len(qualifier):
            return candidate
    return label


def _is_generic_clue_label(label: str) -> bool:
    return label in _GENERIC_CLUE_MARKERS


def _clue_marker_for_label(label: str) -> str:
    return next(
        (
            marker
            for marker in sorted(_GENERIC_CLUE_MARKERS, key=len, reverse=True)
            if label.endswith(marker)
        ),
        "",
    )


def _clue_source_labels(records, names, detail, label: str) -> list[str]:
    labels: list[str] = []
    for _, text in records:
        labels.extend(_stored_clue_source_labels(text, label, names))

    # Provenance must be executed by a scene. Objectives and conflicts can name
    # an intended acquisition, but only turn/result establishes that it happened.
    for chapter_ref in _ordered_unique(_chapter_ref(ref) for ref, _ in records):
        chapter = next(item for item in detail.chapters if item.ref == chapter_ref)
        for scene_index, scene in enumerate(chapter.scenes, start=1):
            scene_text = "，".join([scene.place, scene.turn, scene.result])
            labels.extend(
                _source_labels_for_clue(
                    f"detail:{chapter_ref}:scene-{scene_index}",
                    scene_text,
                    label,
                    names,
                    detail,
                )
            )
    return _ordered_unique(labels)


def _stored_clue_source_labels(text: str, label: str, names: dict[str, str]) -> list[str]:
    marker = _clue_marker_for_label(label)
    queries = _ordered_unique(
        query for query in (label, marker) if query and query in text
    )
    if not queries:
        return []
    labels: list[str] = []
    for query in queries:
        for match in re.finditer(re.escape(query), text):
            tail = text[match.end() : match.end() + 48]
            stored = re.match(
                r".{0,3}(?:藏在|存放在|保存在|保管在)([^，。；：！？、\s]{1,28})",
                tail,
            )
            if stored is None:
                continue
            location = re.sub(
                r"(?:里面|之中|其中|里|内|中|处)$",
                "",
                stored.group(1).strip(),
            )
            if not location or location in _GENERIC_STORED_LOCATIONS:
                continue
            owner = next((name for name in names if name in location), "")
            if owner:
                labels.append(owner)
                continue
            institution = next(
                (item for item in _SOURCE_INSTITUTIONS if item in location),
                "",
            )
            labels.append(institution or f"place:{location}")
    return _ordered_unique(labels)


def _source_labels_for_clue(source_ref, text, label, names, detail) -> list[str]:
    labels = _source_labels_in_text(source_ref, text, label, names, detail)
    marker = _clue_marker_for_label(label)
    if labels or not marker or marker == label:
        return labels
    return _source_labels_in_text(source_ref, text, marker, names, detail)


def _source_labels_in_text(source_ref, text, marker, names, detail) -> list[str]:
    labels: list[str] = []
    for match in re.finditer(re.escape(marker), text):
        if not _is_realized_clue_mention(text, match.start()):
            continue
        if any(
            text[match.end() :].startswith(item)
            for item in _CLUE_VERB_OBJECTS.get(marker, ())
        ):
            continue
        snippet = text[max(0, match.start() - 36) : match.end() + 36]
        acquisition_actions = (
            _DIRECT_SOURCE_ACQUISITION_MARKERS
            if any(item in text for item in _TRANSFER_MARKERS)
            else _SOURCE_ACQUISITION_MARKERS
        )
        acquisition_targets_clue = _source_action_targets_clue(
            text,
            clue_start=match.start(),
            actions=acquisition_actions,
        )
        giver_targets_clue = _source_action_targets_clue(
            text,
            clue_start=match.start(),
            actions=_SOURCE_GIVER_MARKERS,
        )
        comes_from_source = re.search(
            rf"{re.escape(marker)}.{{0,8}}来自",
            snippet,
        )
        container_inherits_source = (
            ":scene-" in source_ref
            and _container_clue_inherits_scene_source(text, match.start())
        )
        if not (
            acquisition_targets_clue
            or giver_targets_clue
            or comes_from_source
            or container_inherits_source
        ):
            continue
        institutions = [
            institution
            for institution in _SOURCE_INSTITUTIONS
            if institution in snippet
        ]
        if institutions:
            labels.extend(institutions)
            continue
        giver_action = "|".join(_SOURCE_GIVER_MARKERS)
        found_name = False
        for name in names:
            if re.search(
                rf"{re.escape(name)}.{{0,8}}(?:{giver_action}).{{0,18}}{re.escape(marker)}",
                snippet,
            ) or re.search(
                rf"{re.escape(marker)}.{{0,8}}来自{re.escape(name)}",
                snippet,
            ):
                labels.append(name)
                found_name = True
        if found_name:
            continue
        if (
            ":scene-" in source_ref
            and (
                acquisition_targets_clue
                or container_inherits_source
            )
        ):
            chapter_ref = _chapter_ref(source_ref)
            scene_number = int(source_ref.rsplit("-", 1)[-1])
            chapter = next(item for item in detail.chapters if item.ref == chapter_ref)
            place = chapter.scenes[scene_number - 1].place
            institution = next(
                (item for item in _SOURCE_INSTITUTIONS if item in place),
                "",
            )
            labels.append(institution or f"place:{place}")
    return labels


def _container_clue_inherits_scene_source(text: str, marker_start: int) -> bool:
    """A fact inside an acquired document inherits that document's scene source."""

    suffix = text[marker_start : marker_start + 16]
    if not re.search(r"(?:名单|记录|日记|报告|卷宗|协议)(?:中|内|上)", suffix):
        return False
    prefix = text[:marker_start]
    action_positions = [
        match.start()
        for action in _SOURCE_ACQUISITION_MARKERS
        for match in re.finditer(re.escape(action), prefix)
    ]
    if not action_positions:
        return False
    nearest_action = max(action_positions)
    acquired_text = prefix[nearest_action:]
    return any(marker in acquired_text for marker in _CLUE_MARKERS)


def _source_action_targets_clue(
    text: str,
    *,
    clue_start: int,
    actions: tuple[str, ...],
) -> bool:
    clause_start = max(
        (text.rfind(delimiter, 0, clue_start) for delimiter in "，。；：！？、"),
        default=-1,
    )
    prefix = text[clause_start + 1 : clue_start]
    container_match = re.search(r"(?:内有|装有|夹有|藏有)[^，。；：！？、]{0,18}$", prefix)
    if container_match and clause_start >= 0:
        previous_clause_start = max(
            (
                text.rfind(delimiter, 0, clause_start)
                for delimiter in "，。；：！？、"
            ),
            default=-1,
        )
        previous_clause = text[previous_clause_start + 1 : clause_start]
        if any(action in previous_clause for action in actions):
            return True
    action_matches = [
        match
        for action in actions
        for match in re.finditer(re.escape(action), prefix)
    ]
    if not action_matches:
        return False
    closest_action = max(action_matches, key=lambda item: item.end())
    between = prefix[closest_action.end() :]
    if len(between) > 18:
        return False
    intervening_actions = (
        *_VERIFY_MARKERS,
        *_TRANSFER_MARKERS,
        *_PAYOFF_MARKERS,
        "并", "且", "随后", "然后", "同时", "转而",
    )
    return not any(marker in between for marker in intervening_actions)


def _duplicate_job_findings(detail: DetailArtifact) -> list[NarrativeContractFinding]:
    findings: list[NarrativeContractFinding] = []
    jobs = [_chapter_job(chapter) for chapter in detail.chapters]
    for left, right in zip(range(len(jobs) - 1), range(1, len(jobs)), strict=True):
        left_chapter = detail.chapters[left]
        right_chapter = detail.chapters[right]
        purpose_similarity = SequenceMatcher(
            None,
            _normalized_text(left_chapter.purpose),
            _normalized_text(right_chapter.purpose),
            autojunk=False,
        ).ratio()
        result_similarity = SequenceMatcher(
            None,
            _normalized_text(left_chapter.scenes[-1].result),
            _normalized_text(right_chapter.scenes[-1].result),
            autojunk=False,
        ).ratio()
        left_endpoints = dramatic_endpoints_for_chapter(left_chapter)
        right_endpoints = dramatic_endpoints_for_chapter(right_chapter)
        repeated_endpoints = sorted(left_endpoints & right_endpoints)
        if (
            left_chapter.turn_refs == right_chapter.turn_refs
            and (
                (purpose_similarity >= 0.72 and result_similarity >= 0.62)
                or len(repeated_endpoints) >= 2
            )
        ):
            findings.append(
                NarrativeContractFinding(
                    code="detail_duplicate_job",
                    source_refs=[left_chapter.ref, right_chapter.ref],
                    evidence=(
                        "相邻章节重复同一转折、目的与结果"
                        f"（purpose={purpose_similarity:.2f}, result={result_similarity:.2f}, "
                        f"endpoints={repeated_endpoints}）。"
                    ),
                    required_fix="合并重复发现，或让后章产生新的行动、知识、关系或风险状态。",
                )
            )
    for left in range(len(jobs)):
        for right in range(left + 2, len(jobs)):
            left_text, left_actions, left_arenas = jobs[left]
            right_text, right_actions, right_arenas = jobs[right]
            similarity = SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()
            repeated_shape = (
                similarity >= 0.45
                and len(left_actions & right_actions) >= 2
                and bool(left_arenas & right_arenas)
            )
            if similarity < 0.76 and not repeated_shape:
                continue
            findings.append(
                NarrativeContractFinding(
                    code="detail_duplicate_job",
                    source_refs=[detail.chapters[left].ref, detail.chapters[right].ref],
                    evidence=f"非相邻章节重复戏剧任务（similarity={similarity:.2f}，actions={sorted(left_actions & right_actions)}，arenas={sorted(left_arenas & right_arenas)}）。",
                    required_fix="合并重复章节，或让后章产生不同的行动、知识、关系或风险结果。",
                )
            )
    return findings


def dramatic_endpoints_for_chapter(chapter: object) -> set[str]:
    text = " ".join(
        [
            str(getattr(chapter, "purpose", "")),
            *(
                f"{scene.turn} {scene.result}"
                for scene in getattr(chapter, "scenes", [])
            ),
            str(getattr(chapter, "handoff", "")),
        ]
    )
    return dramatic_endpoints_for_text(text)


def dramatic_endpoints_for_text(text: str) -> set[str]:
    endpoints = {
        endpoint
        for endpoint, pattern in _DRAMATIC_ENDPOINT_PATTERNS.items()
        if endpoint != "evidence_submission" and pattern.search(text)
    }
    submission_pattern = _DRAMATIC_ENDPOINT_PATTERNS["evidence_submission"]
    for match in submission_pattern.finditer(text):
        action = re.search(r"提交|递交|出示", match.group(0))
        if action is None:
            continue
        action_start = match.start() + action.start()
        clause_prefix = re.split(r"[，。；：！？]", text[:action_start])[-1]
        if not _SUBMISSION_INTENT_PREFIX.search(clause_prefix):
            endpoints.add("evidence_submission")
            break
    return endpoints


def _custody_handoff_findings(
    cast: CharacterBibleArtifact,
    detail: DetailArtifact,
) -> list[NarrativeContractFinding]:
    """Reject unexplained free-to-custody jumps across chapter boundaries."""

    protagonists = [
        subject.name for subject in cast.subjects if subject.kind == "protagonist"
    ]
    if not protagonists:
        return []
    findings: list[NarrativeContractFinding] = []
    custody_state = "unknown"
    previous_ref = ""
    for chapter in detail.chapters:
        opening_text = " ".join(
            [
                chapter.purpose,
                chapter.scenes[0].place,
                chapter.scenes[0].objective,
                chapter.scenes[0].conflict,
            ]
        )
        execution_text = " ".join(
            f"{scene.turn} {scene.result}" for scene in chapter.scenes
        )
        chapter_text = f"{opening_text} {execution_text} {chapter.handoff}"
        starts_in_custody = any(
            marker in opening_text
            for marker in (*CUSTODY_PLACE_MARKERS, *CUSTODY_STATE_MARKERS)
        )
        executes_custody_entry = any(
            marker in execution_text for marker in CUSTODY_ENTRY_MARKERS
        )
        if (
            custody_state == "free"
            and starts_in_custody
            and not executes_custody_entry
        ):
            findings.append(
                NarrativeContractFinding(
                    code="custody_handoff_conflict",
                    source_refs=[previous_ref, chapter.ref],
                    evidence=(
                        f"{previous_ref} leaves the protagonist free, but {chapter.ref} "
                        "opens in custody without an on-page re-arrest or boundary handoff."
                    ),
                    required_fix=(
                        "Keep the protagonist free, or execute and explain the new arrest "
                        "before the custody scene; do not reset custody between chapters."
                    ),
                )
            )

        transitions: list[tuple[int, str]] = []
        for marker in CUSTODY_ENTRY_MARKERS:
            transitions.extend((match.start(), "detained") for match in re.finditer(marker, chapter_text))
        for marker in CUSTODY_RELEASE_MARKERS:
            transitions.extend((match.start(), "free") for match in re.finditer(marker, chapter_text))
        if transitions:
            custody_state = max(transitions, key=lambda item: item[0])[1]
        elif starts_in_custody or any(
            marker in chapter.handoff
            for marker in (*CUSTODY_PLACE_MARKERS, *CUSTODY_STATE_MARKERS)
        ):
            custody_state = "detained"
        previous_ref = chapter.ref
    return findings


def _normalized_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold())


def _chapter_job(chapter) -> tuple[str, set[str], set[str]]:
    text = " ".join(
        [chapter.purpose, *(f"{scene.objective} {scene.turn} {scene.result}" for scene in chapter.scenes), chapter.handoff]
    )
    normalized = re.sub(r"[\W_]+", "", text.casefold())
    return (
        normalized,
        {marker for marker in _JOB_ACTIONS if marker in text},
        {marker for marker in _JOB_ARENAS if marker in text},
    )


def _climax_responsibility_findings(spine, cast, detail):
    climax_turn = next(turn.id for turn in spine.turns if "climax" in turn.milestones)
    climax_chapters = [chapter for chapter in detail.chapters if climax_turn in chapter.turn_refs]
    names = {subject.name: subject.id for subject in cast.subjects}
    findings: list[NarrativeContractFinding] = []
    for chapter in climax_chapters:
        text = " ".join(
            [chapter.purpose, *(f"{scene.objective} {scene.conflict} {scene.turn} {scene.result}" for scene in chapter.scenes), chapter.handoff]
        )
        for marker in _GENERIC_VICTIMS:
            if marker not in text:
                continue
            sentence = next((item for item in re.split(r"[。！？!?]", text) if marker in item), text)
            bound_victim = any(
                re.search(
                    rf"(?:{re.escape(name)}.{{0,6}}{re.escape(marker)}|{re.escape(marker)}.{{0,6}}{re.escape(name)})",
                    sentence,
                )
                for name in names
            )
            if not bound_victim:
                findings.append(
                    NarrativeContractFinding(
                        code="unbound_climax_victim",
                        source_refs=[chapter.ref, climax_turn],
                        evidence=f"高潮使用未绑定受害责任的‘{marker}’：{sentence[:240]}",
                        required_fix="把高潮受害者注册为主体并在前文建立因果责任，或删除临时人质装置。",
                    )
                )
    return findings


def _refs_with_markers(records, markers) -> list[str]:
    return _ordered_unique(
        _chapter_ref(source_ref)
        for source_ref, text in records
        if any(marker in text for marker in markers)
    )


def _chapter_ref(source_ref: str) -> str:
    match = re.search(r"chapter-[1-9][0-9]*", source_ref)
    return match.group(0) if match else source_ref


def _ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _deduplicate_findings(findings):
    result: list[NarrativeContractFinding] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    for finding in findings:
        key = (finding.code, tuple(finding.source_refs), finding.evidence)
        if key not in seen:
            seen.add(key)
            result.append(finding)
    return result


__all__ = [
    "ClueLifecycleProjection",
    "IdentityBinding",
    "NarrativeContractFinding",
    "NarrativeContractReport",
    "build_cast_identity_findings",
    "build_narrative_contract_report",
    "dramatic_endpoints_for_chapter",
    "dramatic_endpoints_for_text",
]
