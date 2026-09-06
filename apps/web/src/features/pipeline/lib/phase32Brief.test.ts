import { describe, expect, it } from "vitest"
import { parsePhase32Brief, splitBriefRules } from "./phase32Brief"

describe("Phase 32 Brief projection", () => {
  it("keeps screenplay and novel contracts distinct", () => {
    const screenplay = parsePhase32Brief("screenplay_sample", {
      title: "失序档案",
      sample_type: "调查悬疑样片",
      target_minutes: 12,
      premise: "主角必须在封存前恢复证据链。",
      audience_promise: "观众持续判断谁改写了证词。",
      visible_conflict: "听证开始前，主角与档案主管争夺原件。",
      ending_effect: "证词被公开，但主角失去内部权限。",
      tone: "冷峻、克制",
    })
    const novel = parsePhase32Brief("short_novel", {
      title: "失序档案",
      premise: "一份被删除的证词改变调查方向。",
      audience_promise: "读者会追问证词为何被删除。",
      theme_question: "真相是否值得承担公开代价？",
      world_rules: ["所有档案修改都有签名链。"],
      ending_direction: "主角公开证词并失去职位。",
      narrative_voice: "克制的限知视角",
      target_characters: 20_000,
    })

    expect(screenplay.artifact?.kind).toBe("screenplay")
    expect(novel.artifact?.kind).toBe("novel")
  })

  it("rejects incomplete payloads and normalizes world rules", () => {
    expect(
      parsePhase32Brief("short_novel", { premise: "不完整" }).artifact,
    ).toBeNull()
    expect(splitBriefRules("规则一\n\n 规则二 ")).toEqual(["规则一", "规则二"])
  })

  it("keeps a structurally valid form mounted while author text is temporarily empty", () => {
    const result = parsePhase32Brief("short_novel", {
      title: "失序档案",
      premise: "",
      audience_promise: "读者承诺",
      theme_question: "主题问题",
      world_rules: [],
      ending_direction: "结局方向",
      narrative_voice: "叙事声音",
      target_characters: 20_000,
    })

    expect(result.artifact?.kind).toBe("novel")
    expect(result.error).toContain("不能留空")
  })
})
