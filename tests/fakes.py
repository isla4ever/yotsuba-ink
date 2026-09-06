from __future__ import annotations

import json
import struct
import zlib
from typing import Any

from novel_workflow.providers.base import GeneratedImage
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterEvidenceRequest,
    ChapterEvidenceResult,
    ChapterSceneGenerationRequest,
    ChapterReviewRequest,
    ChapterReviewResult,
    CoverImageRequest,
    PlainTextProviderResult,
    ProposalGenerationRequest,
    StageGenerationRequest,
    StructuredProviderResult,
)
from novel_workflow.runtime.graph.author_collaboration_requests import (
    CollaborationGenerationRequest,
    CollaborationProviderResult,
)
from novel_workflow.output_contracts.author_collaboration import CollaborationPlan


def fake_png_bytes(width: int = 256, height: int = 384, *, seed: int = 0) -> bytes:
    pixel = bytes((0x31, 0x53, (0x72 + seed) % 256, 0xFF))
    raw = b"".join(b"\x00" + pixel * width for _ in range(height))
    signature = b"\x89PNG\r\n\x1a\n"
    return (
        signature
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def fake_brief_payload() -> dict[str, Any]:
    return {
        "title": "雾港旧声",
        "premise": "修复师追查一段被删除的母带。",
        "promise": "每次取证都会改变她对母亲失踪的理解。",
        "world_rules": ["公开广播会覆盖个人记忆"],
        "theme": "真相的代价",
        "ending_promise": "真相会被公开。",
        "voice": "克制、贴近感官、第三人称有限视角",
        "length_envelope": {
            "word_target_soft": 12000,
        },
    }


def fake_spine_payload(turn_count: int) -> dict[str, Any]:
    progress_types = ("information", "external", "relationship", "information", "internal")
    return {
        "turns": [
            {
                "cause": f"第 {index} 个压力承接上一局面",
                "change": f"第 {index} 个不可逆调查结果形成",
                "progress_type": progress_types[(index - 1) % len(progress_types)],
            }
            for index in range(1, turn_count + 1)
        ],
        "ending": "公开母带并承担记忆损失",
        "open_questions": ["谁签署了删除令？"],
    }


_FAKE_DETAIL_STEPS = (
    ("还原潮位变化", "潮汐站", "校准纸带刻度", "旧表格缺页", "锁定异常潮位时段", "转向泵站检修班"),
    ("访谈退职值班员", "社区活动室", "复述夜班交接", "说法前后矛盾", "确认换岗顺序", "寻找门禁底册"),
    ("复原门禁轨迹", "保安室", "对齐刷卡钟点", "控制器时钟漂移", "圈定空白十七分钟", "检视备用电源"),
    ("核清备用电源状态", "配电间", "测算切换延迟", "保险装置被替换", "找出人为断电窗口", "追索替换经手人"),
    ("厘清维修班轮值", "机修车间", "重排当夜工位", "临时换班无人认领", "锁定缺席的轮值席位", "回看食堂结算时点"),
    ("对齐结算时点", "旧港食堂", "核清夜班消费顺序", "收银时钟慢了九分钟", "修正关键人物离场时刻", "转查摆渡车班次"),
    ("重建摆渡路线", "渡口候船厅", "拼合停靠次序", "末班船临时改道", "确认有人绕开主码头", "勘察防波堤入口"),
    ("勘察隐蔽入口", "防波堤", "测量通行痕迹", "涨潮抹去部分足迹", "确定一条逆潮通路", "核清泵站开闸时段"),
    ("核清开闸时段", "旧泵站", "复算闸门启闭间隔", "机械读数与值守说法不符", "确认提前开启的闸门", "寻找远端操控席位"),
    ("定位远端操控席位", "调度夹层", "排查控制回路", "废弃端口仍有电流", "找到隐藏的操作路径", "追踪信号中继点"),
    ("追踪信号中继", "山腰机房", "测定传输延迟", "雨水造成间歇失真", "分离出人为插入的脉冲", "核清广播盲区"),
    ("测绘广播盲区", "港区天台", "比照各处接收强度", "高墙遮挡造成误差", "找到唯一无声区域", "进入旧仓后巷"),
    ("进入旧仓后巷", "仓区后巷", "确认货门开启方向", "封条新旧层次混杂", "辨明最近一次开启痕迹", "询问夜巡队员"),
    ("询问夜巡队员", "巡防岗亭", "重述当夜巡线", "两人对哨声次数说法不同", "确定一次未被上报的折返", "查验隧道积水线"),
    ("还原隧道通行", "排水隧道", "测算积水退去速度", "墙面水线被重新粉刷", "确认有人等待退潮通过", "转向岸边修船棚"),
    ("核清修船棚动静", "修船棚", "排定工具使用先后", "一台绞盘提前归位", "确定离港前的短暂停留", "追问拖轮值守"),
    ("追问拖轮值守", "拖轮驾驶舱", "重建离泊过程", "雾号掩盖发动声", "确认一艘未登记小艇伴行", "测算外港航向"),
    ("测算外港航向", "海事观测台", "推演潮流偏移", "风向数据存在断点", "收窄小艇可能抵达区域", "前往废弃灯塔"),
    ("搜索灯塔夹层", "废弃灯塔", "核清近期停留痕迹", "木梯腐朽无法直达", "找到从外墙进入的方法", "厘清守塔人口述"),
    ("厘清守塔人口述", "灯塔值守屋", "分开传闻与亲见", "老人把两次风暴混为一谈", "确认真正发生在停电当夜的片段", "回到港务会议室"),
    ("重建港务决策", "港务会议室", "排列争议发言次序", "多人回避最终表态", "识别推动封存的关键压力", "准备责任对质"),
    ("完成责任对质", "旧港礼堂", "迫使各方回应因果链", "相关人员互相推诿", "冻结各自无法回避的责任", "进入终局选择"),
)
_FAKE_DETAIL_PHASES = ("春潮", "夜雾", "寒汛", "晴港", "逆风", "落潮", "晨灯", "雨幕")
_FAKE_DETAIL_FOCUSES = (
    "证言可信度",
    "程序责任",
    "行动风险",
    "关系裂缝",
    "时间偏差",
    "资源约束",
    "公开代价",
    "记忆损失",
)


def _fake_detail_chapter(number: int, cast_ids: list[str]) -> dict[str, Any]:
    if number == 1:
        return {
            "title": "母带残响1",
            "purpose": "取得母带副本",
            "pov": cast_ids[0],
            "cast_ids": cast_ids,
            "scenes": [
                {
                    "place": "档案室",
                    "objective": "从档案室取得并核验母带",
                    "conflict": "管理员拒绝开放保管柜",
                    "turn": "发现删除签名",
                    "result": "从档案室取得母带并登记保管来源",
                },
                {
                    "place": "旧潮道",
                    "objective": "核对母带内容",
                    "conflict": "广播系统拦截",
                    "turn": "同伴承认沉默",
                    "result": "从档案室取得母带并核验内容",
                },
            ],
            "handoff": "追查签名来源",
        }
    if number == 2:
        return {
            "title": "母带残响2",
            "purpose": "公开母带并锁定删除责任",
            "pov": cast_ids[0],
            "cast_ids": cast_ids,
            "scenes": [
                {
                    "place": "档案室",
                    "objective": "公开母带内容并对照删除时点",
                    "conflict": "保管方质疑播放顺序",
                    "turn": "主角证明音轨连续",
                    "result": "在档案室公开母带并说明保管来源",
                },
                {
                    "place": "旧潮道",
                    "objective": "逼近删除流程责任人",
                    "conflict": "负责人试图转移程序责任",
                    "turn": "流程缺口与签名时点重合",
                    "result": "公开母带并说明档案室来源",
                },
            ],
            "handoff": "追问删除命令责任",
        }

    step_index = number - 3
    purpose, place, objective, conflict, result, handoff = _FAKE_DETAIL_STEPS[
        step_index % len(_FAKE_DETAIL_STEPS)
    ]
    phase = _FAKE_DETAIL_PHASES[step_index % len(_FAKE_DETAIL_PHASES)]
    focus = _FAKE_DETAIL_FOCUSES[
        (step_index // len(_FAKE_DETAIL_PHASES)) % len(_FAKE_DETAIL_FOCUSES)
    ]
    chapter_context = f"{phase}阶段围绕{focus}"
    return {
        "title": f"母带残响{number}",
        "purpose": f"{chapter_context}推进{purpose}",
        "pov": cast_ids[0],
        "cast_ids": cast_ids,
        "scenes": [
            {
                "place": place,
                "objective": objective,
                "conflict": conflict,
                "turn": f"{chapter_context}使调查方向改为{result}",
                "result": f"{chapter_context}下{result}",
            },
            {
                "place": f"{place}外廊",
                "objective": f"验证{result}",
                "conflict": f"{conflict}引出新的反证",
                "turn": f"{chapter_context}的局面指向{handoff}",
                "result": f"{result}，{chapter_context}的下一步转向{handoff}",
            },
        ],
        "handoff": f"{chapter_context}结束后{handoff}",
    }


class FakeNarrativeProvider:
    """Offline NarrativeProviderGateway double returning contract-valid payloads."""

    def __init__(self, *, subject_count: int = 3) -> None:
        self.subject_count = subject_count
        self.stage_requests: list[StageGenerationRequest] = []
        self.proposal_requests: list[ProposalGenerationRequest] = []
        self.chapter_requests: list[ChapterSceneGenerationRequest] = []
        self.review_requests: list[ChapterReviewRequest] = []
        self.evidence_requests: list[ChapterEvidenceRequest] = []
        self.cover_requests: list[CoverImageRequest] = []
        self.collaboration_requests: list[CollaborationGenerationRequest] = []

    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult:
        self.stage_requests.append(request)
        if request.stage_id == "brief":
            payload = fake_brief_payload()
        elif request.stage_id == "spine":
            scale = request.context["material"]["scale_plan"]
            payload = fake_spine_payload(int(scale["turn_target"]))
        elif request.stage_id == "cast":
            refs = request.context["material"]["subject_refs"]
            names = ("林岚", "周屿", "苏禾", "陈砚", "顾遥", "沈闻")
            payload = {
                "subjects": [
                    {
                        "name": names[(int(ref["id"].split("-")[-1]) - 1) % len(names)],
                        "kind": (
                            "protagonist"
                            if ref["narrative_role"] == "protagonist"
                            else "historical_record"
                            if ref["narrative_role"] == "historical_record"
                            else "major"
                        ),
                        "function": f"承担需求 {ref['demand_key']}",
                        "background": f"长期从事公共档案修复，曾在旧港事故留下的职业争议中负责第 {index} 类记录。",
                        "conflict_history": f"曾参与旧港事故档案的第 {index} 次修复，签名记录与现存母带相互矛盾。",
                        "present_stakes": f"若第 {index} 类证言失效，将失去职业资格并让旧案的一段记录永久封存。",
                        "temperament": f"受压时先核对第 {index} 类证据，再用克制的坚持逼迫对方表态。",
                        "speech_style": f"句子短，常先复述第 {index} 类可验证事实；没有把握时保持沉默。",
                        "drive": "推动母带真相公开",
                        "change": "从回避风险转向承担证言责任",
                        "debut": "chapter:1",
                        "limits": ["不得代替主角完成最终选择"],
                        "demand_refs": [ref["demand_key"]],
                    }
                    for ref in refs
                    for index in [int(ref["id"].split("-")[-1])]
                ],
            }
        elif request.stage_id == "volumes":
            boundary = request.context["material"]["volume_boundary"]
            cast_ids = [
                item["id"]
                for item in request.context["material"]["character_bible_refs"]
            ]
            payload = {
                "volumes": [{
                    "title": f"雾港{boundary['boundary_key'].split('-')[-1]}卷",
                    "promise": "找到母带来源",
                    "conflict": "档案系统持续删除证据",
                    "climax": "主角公开母带",
                    "climax_turn_ref": next(
                        (
                            turn["id"]
                            for turn in request.context["material"]["volume_spine_turns"]
                            if "climax" in turn.get("milestones", [])
                        ),
                        boundary["turn_refs"][
                            max(0, (len(boundary["turn_refs"]) * 3 + 4) // 5 - 1)
                        ],
                    ),
                    "closure": "旧案真相公开但记忆受损",
                    "cast_ids": cast_ids,
                    "length_hint": "short",
                }]
            }
        elif request.stage_id == "detail":
            scale = request.context["material"]["scale_projection"]
            start = int(scale["chapter_number_start"])
            count = int(scale["chapter_target"])
            cast_ids = [
                item["id"]
                for item in request.context["material"]["selected_dossiers"]
            ]
            generated = {
                f"chapter-{start + offset}": _fake_detail_chapter(
                    start + offset,
                    cast_ids,
                )
                for offset in range(count)
            }
            recovery_source = request.context["material"].get("recovery_source")
            if isinstance(recovery_source, dict):
                payload = {
                    "chapters": [
                        {
                            key: value
                            for key, value in generated[chapter_ref].items()
                            if key in {"purpose", "scenes", "handoff"}
                        }
                        for chapter_ref in recovery_source["editable_chapter_refs"]
                    ]
                }
            else:
                payload = {"chapters": list(generated.values())}
        elif request.stage_id == "cover":
            payload = {"concept": "雾港中的旧录音", "image_prompt": "雾港、旧录音带、克制悬疑", "palette": ["深蓝", "锈红"], "negative_constraints": ["无文字"]}
        else:
            raise AssertionError(request.stage_id)
        return StructuredProviderResult(payload=payload, usage={"total_tokens": 3})

    async def generate_proposal(self, request: ProposalGenerationRequest) -> StructuredProviderResult:
        self.proposal_requests.append(request)
        if request.proposal_type == "spine_review":
            payload = {"verdict": "pass", "findings": []}
        elif request.proposal_type in {"role_demand_review", "cast_review"}:
            payload = {"verdict": "pass", "findings": []}
        elif request.proposal_type == "role_demand":
            spine_turns = request.context["material"]["story_spine"]["turns"]
            turn_refs = [str(turn["id"]) for turn in spine_turns]
            scale_plan = request.context["material"].get("scale_plan") or {}
            recommended = scale_plan.get("cast_recommended_range") or [1, 1]
            hard_max = int(scale_plan.get("cast_hard_max") or recommended[-1])
            desired_count = min(
                hard_max,
                max(int(recommended[0]), self.subject_count),
            )
            relationship_refs = [
                str(turn["id"])
                for turn in spine_turns
                if turn.get("progress_type") == "relationship"
            ] or [turn_refs[0]]
            payload = {
                "proposals": [
                    {
                        "demand_key": f"demand-role-{index}",
                        "subject_mode": "actor",
                        "narrative_role": (
                            "protagonist"
                            if index == 1
                            else "opposition"
                            if index == 2
                            else "relationship"
                        ),
                        "function": f"承担第 {index} 个叙事职责",
                        "required_change": f"从第 {index} 类回避风险转为承担第 {index} 类后果",
                        "irreducibility": "必须独立作出不可逆选择，不能由现有主体或机构程序代替。",
                        "active_turn_refs": (
                            [turn_refs[0], turn_refs[-1]]
                            if index == 1 and len(turn_refs) > 1
                            else [turn_refs[0]]
                            if index == 1
                            else sorted(
                                set(
                                    [turn_refs[(index - 1) % len(turn_refs)], *relationship_refs]
                                    if index == 2
                                    else [
                                        turn_refs[(index - 1) % len(turn_refs)],
                                        relationship_refs[-1],
                                    ]
                                ),
                                key=turn_refs.index,
                            )
                        ),
                    }
                    for index in range(1, desired_count + 1)
                ]
            }
        elif request.proposal_type == "cast_relation":
            subject_ids = [
                str(item["id"])
                for item in request.context["material"].get("subjects", [])
            ]
            payload = {
                "relations": [
                    {
                        "a": "subject-1",
                        "b": subject_id,
                        "type": "互相利用的搭档",
                        "pressure": "违规会连累双方",
                    }
                    for subject_id in subject_ids
                    if subject_id != "subject-1"
                ]
            }
        elif request.proposal_type == "volume_boundary":
            turn_refs = [
                item["id"]
                for item in request.context["material"]["story_spine"]["turns"]
            ]
            volume_target = int(
                request.context["material"]["scale_plan"]["volume_target"]
            )
            chunk_size, remainder = divmod(len(turn_refs), volume_target)
            offset = 0
            proposals = []
            for index in range(1, volume_target + 1):
                size = chunk_size + (1 if index <= remainder else 0)
                proposals.append(
                    {
                        "boundary_key": f"boundary-{index}",
                        "turn_refs": turn_refs[offset : offset + size],
                        "reason": f"第 {index} 个连续转折单元形成局部闭合",
                    }
                )
                offset += size
            payload = {
                "proposals": proposals
            }
        elif request.proposal_type == "detail_layout":
            material = request.context["material"]
            volume = material["volume_contracts"][0]
            payload = {
                "status": "sufficient",
                "diagnosis": "",
                "volumes": [{
                    "volume_ref": volume["id"],
                    "chapters": [
                        {
                            "turn_refs": turn_refs,
                            "dramatic_job": (
                                f"完成{volume['id']}的第{slot['slot_index']}个独立变化"
                            ),
                            "length_hint": "standard",
                        }
                        for slot, turn_refs in zip(
                            material["chapter_slots"],
                            _fake_layout_turn_refs(
                                list(volume["turn_refs"]),
                                int(material["scale_plan"]["chapter_target"]),
                            ),
                            strict=True,
                        )
                    ],
                }],
            }
        else:
            raise AssertionError(request.proposal_type)
        return StructuredProviderResult(payload=payload, usage={"total_tokens": 2})

    async def generate_chapter_scene(
        self,
        request: ChapterSceneGenerationRequest,
    ) -> PlainTextProviderResult:
        self.chapter_requests.append(request)
        target = _chapter_character_target(request.context)
        prefix = f"{request.chapter_id}场景{request.scene_index}正文"
        content = prefix + "文" * max(0, target - len(prefix)) if target else f"{prefix}。"
        return PlainTextProviderResult(content=content, usage={"total_tokens": 4})

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult:
        self.review_requests.append(request)
        return StructuredProviderResult(payload=ChapterReviewResult(role=request.role).model_dump(mode="json"), usage={"total_tokens": 1})

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult:
        self.evidence_requests.append(request)
        claim = "本章完成施工图目标"
        return StructuredProviderResult(payload=ChapterEvidenceResult(claims=[{
            "kind": "fact",
            "claim": claim,
            "span_ids": ["span-0001"],
            "state": {
                "type": "assertion",
                "subject_id": "story",
                "property_key": f"{request.chapter_id}.completion",
                "value": claim,
                "epistemic_status": "fact",
            },
        }]).model_dump(mode="json"), usage={"total_tokens": 1})

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage:
        self.cover_requests.append(request)
        return GeneratedImage(content=fake_png_bytes(seed=request.candidate_index), mime_type="image/png", provider_asset_id=f"asset-{request.candidate_index}", usage={"total_tokens": 1})

    async def generate_collaboration_turn(
        self,
        request: CollaborationGenerationRequest,
    ) -> CollaborationProviderResult:
        self.collaboration_requests.append(request)
        if request.mode == "plan":
            return CollaborationProviderResult(
                content="先冻结当前矛盾，再逐步核对人物代价。",
                plan=CollaborationPlan(
                    goal="让当前局部选择具有可见行动与不可逆代价",
                    findings=["因果成立，但人物代价表达偏抽象"],
                    steps=["明确行动", "绑定后果", "回查上游约束"],
                ),
                usage={"total_tokens": 1},
            )
        if request.mode == "revise":
            return CollaborationProviderResult(
                content="已生成一处精确选区替换，等待作者确认。",
                replacement="主角公开母带来源，并承担修复资格被撤销的后果",
                rationale="把抽象变化落实为可见行动与不可逆代价。",
                usage={"total_tokens": 1},
            )
        return CollaborationProviderResult(
            content="当前因果成立；建议进一步明确选择发生时的职业代价。",
            usage={"total_tokens": 1},
        )


def _chapter_character_target(context: dict[str, Any]) -> int | None:
    manifest = context["material"]["chapter_context_manifest"]
    for snippet in manifest["snippets"]:
        if snippet["purpose"] != "rolling_scene_length_contract":
            continue
        contract = json.loads(snippet["text"])
        return int(contract["target_characters"])
    return None


def _fake_layout_turn_refs(turn_refs: list[str], chapter_count: int) -> list[list[str]]:
    if chapter_count <= len(turn_refs):
        base, remainder = divmod(len(turn_refs), chapter_count)
        result: list[list[str]] = []
        offset = 0
        for index in range(chapter_count):
            size = base + (1 if index < remainder else 0)
            result.append(turn_refs[offset : offset + size])
            offset += size
        return result
    return [
        [turn_refs[min(len(turn_refs) - 1, index * len(turn_refs) // chapter_count)]]
        for index in range(chapter_count)
    ]
