from __future__ import annotations

from novel_workflow.output_contracts.artifacts_vnext import DetailArtifact
from novel_workflow.runtime.graph.context_compiler import _chapter_subjects


def test_text_context_includes_named_historical_subject_without_staging_it() -> None:
    cast = {
        "subjects": [
            {
                "id": "subject-1",
                "name": "林澈",
                "kind": "protagonist",
                "function": "修复晶片",
                "background": "公共记忆修复师，长期负责异常晶片的校验与归档。",
                "conflict_history": "她曾在事故档案中见过林泽的求救声纹，却未能保存原件。",
                "present_stakes": "若校验失败，她会失去修复资格并中断事故追查。",
                "temperament": "受压时先固定日志，再决定是否公开异常。",
                "speech_style": "短句，先报事实，避免情绪判断。",
                "drive": "查明真相",
                "change": "承担职业代价",
                "debut": "chapter:1",
                "limits": ["不得隐瞒证据"],
                "demand_refs": ["demand-1"],
            },
            {
                "id": "subject-2",
                "name": "林泽",
                "kind": "historical_record",
                "function": "十年前事故相关者",
                "background": "十年前事故中的设备维护员，只留下求救录音和维修签名。",
                "conflict_history": "他的声纹与被删除的事故日志直接对应。",
                "present_stakes": "若声纹失去可信度，事故责任将无法追认。",
                "temperament": "生前谨慎，遇到异常会先留下双重记录。",
                "speech_style": "录音中用词简短准确，重复关键设备编号。",
                "drive": "无",
                "change": "责任由物证确认",
                "debut": "chapter:1",
                "limits": ["不得拥有当下行动或POV"],
                "demand_refs": ["demand-2"],
            },
            {
                "id": "subject-3",
                "name": "沈墨",
                "kind": "major",
                "function": "后续证据提供者",
                "background": "事故档案保管员，曾私下复制过一份未校准记录。",
                "conflict_history": "她掌握的副本会推翻现有事故结论。",
                "present_stakes": "若交出副本，她会失去工作并承担违规责任。",
                "temperament": "受压时反复确认交换条件，决定后不再撤回。",
                "speech_style": "措辞正式，常用条件句，不主动解释情绪。",
                "drive": "保全记忆",
                "change": "承担遗忘代价",
                "debut": "chapter:2",
                "limits": ["不得提前出场"],
                "demand_refs": ["demand-3"],
            },
        ],
        "relations": [],
    }
    detail = DetailArtifact.model_validate(
        {
            "chapters": [
                {
                    "ref": "chapter-1",
                    "volume_ref": "volume-1",
                    "title": "异常哈希",
                    "target_characters": 2500,
                    "turn_refs": ["turn-1"],
                    "purpose": "林澈修复异常晶片",
                    "pov": "subject-1",
                    "cast_ids": ["subject-1"],
                    "scenes": [
                        {
                            "place": "修复间",
                            "objective": "执行校验",
                            "conflict": "哈希异常",
                            "turn": "尝试修复",
                            "result": "听见林泽的求救声",
                        },
                        {
                            "place": "修复间",
                            "objective": "固定日志",
                            "conflict": "内容归零",
                            "turn": "记录时间戳",
                            "result": "留下调查入口",
                        },
                    ],
                    "handoff": "林澈下一步追查来源",
                }
            ]
        }
    )

    subjects = _chapter_subjects(cast, detail.chapters[0])

    assert [subject["id"] for subject in subjects] == ["subject-1", "subject-2"]
    assert subjects[1]["kind"] == "historical_record"
