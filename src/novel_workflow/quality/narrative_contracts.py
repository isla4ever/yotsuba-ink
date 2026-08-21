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
_SOURCE_MARKERS = ("来自", "寄来", "寄出", "交出", "提供", "留下", "整理", "发现", "持有", "保管", "夹着", "取得", "拿到")
_TRANSFER_MARKERS = ("转交", "移交", "交给", "递交", "归还", "取回", "拿回", "送检")
_VERIFY_MARKERS = ("核对", "核验", "鉴定", "确认", "证实", "比对", "验证")
_PAYOFF_MARKERS = ("公开", "提交", "证明", "揭示", "定案", "播放", "回收", "指认")
_GENERIC_VICTIMS = ("人质", "年轻人", "陌生人", "受害者", "死者", "被绑架者", "下一个目标")
_JOB_ACTIONS = ("公开", "展示", "提交", "发布", "调查", "核验", "追查", "取得", "发现", "威胁", "否认", "抓捕", "救出", "对质", "审讯")
_JOB_ARENAS = ("发布会", "媒体", "警方", "市政厅", "档案馆", "银行", "仓库", "听证")


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
        *_duplicate_job_findings(detail),
        *_climax_responsibility_findings(spine, cast, detail),
        *clue_findings,
    ]
    return NarrativeContractReport(
        identity_bindings=bindings,
        clues=clues,
        findings=_deduplicate_findings(findings),
    )


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
    patterns = (
        rf"(?P<name>{_PERSON_NAME.pattern})(?:本人)?(?:{action})",
        rf"(?:{role})(?:是|名叫|叫作)?(?P<name>{_PERSON_NAME.pattern})",
        rf"(?P<name>{_PERSON_NAME.pattern})(?:是|作为|担任).{{0,8}}(?:{role})",
    )
    return [
        match.group("name")
        for pattern in patterns
        for match in re.finditer(pattern, text)
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
    mentions: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for source_ref, text in sources:
        if not source_ref.startswith("detail:"):
            continue
        for label in _clue_labels(text):
            mentions[label].append((source_ref, text))
    clues: list[ClueLifecycleProjection] = []
    findings: list[NarrativeContractFinding] = []
    for label, records in sorted(mentions.items()):
        chapter_refs = _ordered_unique(_chapter_ref(ref) for ref, _ in records)
        central = (
            len(chapter_refs) > 1
            or label in higher_text
            or any(label.startswith(prefix) for prefix in _NAMED_CLUE_PREFIXES)
        )
        source_labels = _clue_source_labels(records, names, detail)
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
        if len(source_labels) > 1 and not transfers:
            findings.append(
                NarrativeContractFinding(
                    code="evidence_provenance_conflict",
                    source_refs=chapter_refs,
                    evidence=f"关键线索 {label} 出现多个来源 {source_labels}，但没有转交记录。",
                    required_fix="冻结唯一来源；多份证据必须拆分 clue_id，转交必须有独立场景。",
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


def _clue_labels(text: str) -> list[str]:
    labels: list[str] = []
    for marker in _CLUE_MARKERS:
        if marker not in text:
            continue
        label = marker
        for prefix in _NAMED_CLUE_PREFIXES:
            if f"{prefix}{marker}" in text and not marker.startswith(prefix):
                label = f"{prefix}{marker}"
                break
        labels.append(label)
    return _ordered_unique(labels)


def _clue_source_labels(records, names, detail) -> list[str]:
    labels: list[str] = []
    for source_ref, text in records:
        if not any(marker in text for marker in _SOURCE_MARKERS):
            continue
        labels.extend(name for name in names if name in text)
        for institution in ("警方", "档案馆", "档案室", "银行", "医院", "市政厅"):
            if institution in text:
                labels.append(institution)
        if not labels and ":scene-" in source_ref:
            chapter_ref = _chapter_ref(source_ref)
            scene_number = int(source_ref.rsplit("-", 1)[-1])
            chapter = next(item for item in detail.chapters if item.ref == chapter_ref)
            labels.append(f"place:{chapter.scenes[scene_number - 1].place}")
    return _ordered_unique(labels)


def _duplicate_job_findings(detail: DetailArtifact) -> list[NarrativeContractFinding]:
    findings: list[NarrativeContractFinding] = []
    jobs = [_chapter_job(chapter) for chapter in detail.chapters]
    for left in range(len(jobs)):
        for right in range(left + 2, len(jobs)):
            left_text, left_actions, left_arenas = jobs[left]
            right_text, right_actions, right_arenas = jobs[right]
            similarity = SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()
            repeated_shape = len(left_actions & right_actions) >= 2 and bool(left_arenas & right_arenas)
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
]
