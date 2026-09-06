import { describe, expect, it } from "vitest"
import {
  parsePhase32StoryMap,
  splitStoryMapLines,
  storyMapDiagnostics,
} from "./phase32StoryMap"

describe("Phase 32 Story Map contract", () => {
  it("parses ordered anchors and derives bounded diagnostics", () => {
    const parsed = parsePhase32StoryMap(storyMapPayload())

    expect(parsed.error).toBe("")
    expect(parsed.artifact?.anchors.map((anchor) => anchor.anchor_ref)).toEqual(
      ["anchor-1", "anchor-2"],
    )
    expect(storyMapDiagnostics(parsed.artifact!)).toEqual({
      anchorCount: 2,
      anchorsWithoutPromise: ["anchor-2"],
      openQuestionCount: 1,
      promiseRefs: ["promise-truth-cost"],
    })
  })

  it("keeps a structurally readable draft while reporting invalid refs", () => {
    const payload = storyMapPayload()
    payload.anchors[1].anchor_ref = "anchor-1"

    const parsed = parsePhase32StoryMap(payload)
    expect(parsed.artifact).not.toBeNull()
    expect(parsed.error).toContain("重复锚点")
  })

  it("rejects incomplete anchor payloads", () => {
    const payload = storyMapPayload() as Record<string, unknown>
    payload.anchors = [{ anchor_ref: "anchor-1" }]

    expect(parsePhase32StoryMap(payload).artifact).toBeNull()
  })

  it("normalizes author-entered open questions without blank units", () => {
    expect(splitStoryMapLines("第一问\n\n 第二问 ")).toEqual([
      "第一问",
      "第二问",
    ])
  })
})

function storyMapPayload() {
  return {
    opening_state: "主角只相信公开档案。",
    story_question: "谁在修改城市记忆？",
    anchors: [
      {
        anchor_ref: "anchor-1",
        dramatic_job: "建立档案被篡改的压力。",
        pressure: "关键记录在公开前消失。",
        choice_or_revelation: "主角决定追查签名链。",
        consequence_or_open_effect: "她被卷入机构内部调查。",
        promise_refs: ["promise-truth-cost"],
      },
      {
        anchor_ref: "anchor-2",
        dramatic_job: "迫使主角公开选择。",
        pressure: "证人撤回唯一证词。",
        choice_or_revelation: "主角公开未验证的签名记录。",
        consequence_or_open_effect: "调查转向她本人。",
        promise_refs: [],
      },
    ],
    ending_state: "真相公开，但主角失去原职。",
    open_questions: ["谁批准了最初的删改？"],
  }
}
