import { describe, expect, it } from "vitest"
import {
  bookArchitectureDiagnostics,
  parsePhase32BookArchitecture,
  reorderBookParts,
} from "./phase32BookArchitecture"

describe("Phase 32 Book Architecture contract", () => {
  it("parses the aggregate and projects promise distribution without claiming verification", () => {
    const parsed = parsePhase32BookArchitecture(bookArchitecturePayload())

    expect(parsed.error).toBe("")
    expect(parsed.artifact?.parts.map((part) => part.part_ref)).toEqual([
      "part-1",
      "part-2",
    ])
    expect(bookArchitectureDiagnostics(parsed.artifact!)).toEqual({
      endingConditionCount: 2,
      partCount: 2,
      promiseLifecycle: [
        { promiseRef: "promise-truth", partRefs: ["part-1", "part-2"] },
        { promiseRef: "promise-cost", partRefs: ["part-2"] },
      ],
      turningPointCount: 3,
      unresolvedObligationCount: 1,
    })
  })

  it("reorders Parts while retaining refs and rebuilding contiguous ordinals", () => {
    const parts = parsePhase32BookArchitecture(bookArchitecturePayload())
      .artifact!.parts
    const reordered = reorderBookParts(parts, 0, 1)

    expect(reordered.map((part) => part.part_ref)).toEqual(["part-2", "part-1"])
    expect(reordered.map((part) => part.ordinal)).toEqual([1, 2])
  })

  it("keeps a readable draft while reporting duplicate refs and ordinal drift", () => {
    const payload = bookArchitecturePayload()
    payload.parts[1].part_ref = "part-1"
    payload.parts[1].ordinal = 4

    const parsed = parsePhase32BookArchitecture(payload)
    expect(parsed.artifact).not.toBeNull()
    expect(parsed.error).toContain("重复 Part")
  })

  it("rejects incomplete Part payloads", () => {
    const payload = bookArchitecturePayload() as Record<string, unknown>
    payload.parts = [{ part_ref: "part-1" }]

    expect(parsePhase32BookArchitecture(payload).artifact).toBeNull()
  })
})

function bookArchitecturePayload() {
  return {
    book_promise: "一场关于城市记忆与公开代价的长期调查。",
    ending_conditions: ["证据链公开。", "主角承担公开真相的长期后果。"],
    parts: [
      {
        part_ref: "part-1",
        ordinal: 1,
        entry_state: "主角只相信公开档案。",
        dramatic_question: "她能否证明档案正在被系统性删改？",
        promise_refs: ["promise-truth"],
        turning_point_refs: ["turn-erasure"],
        exit_state: "第一份原始证据进入公众视野。",
        unresolved_obligations: ["找到签发删改命令的人。"],
      },
      {
        part_ref: "part-2",
        ordinal: 2,
        entry_state: "调查从机构内部转向公共听证。",
        dramatic_question: "她愿意为公开全部证据付出什么？",
        promise_refs: ["promise-truth", "promise-cost"],
        turning_point_refs: ["turn-hearing", "turn-choice"],
        exit_state: "事实被承认，但主角失去原职。",
        unresolved_obligations: [],
      },
    ],
  }
}
