import { describe, expect, it } from "vitest"
import {
  extractShortProseReferenceContext,
  parsePhase32ShortProse,
  shortProseContractError,
  shortProseDiagnostics,
} from "./phase32ShortProse"

describe("phase32 short prose projection", () => {
  it("parses prose and checks frozen plan identity without blocking soft length", () => {
    const context = extractShortProseReferenceContext(
      {
        units: [
          {
            unit_ref: "unit-1",
            ordinal: 1,
            title: "复印件",
            dramatic_job: "确认第一条证据",
            pov_subject_ref: "maya",
            scene_load: "档案室核验",
            handoff: "从水印日期继续",
            soft_character_budget: 3000,
            promise_refs: [],
          },
        ],
      },
      {
        characters: [
          {
            subject_ref: "maya",
            display_name: "玛雅",
            role: "记者",
            voice: "克制",
          },
        ],
      },
      { story_question: "谁修改了档案？", anchors: [] },
    )
    const parsed = parsePhase32ShortProse({
      unit_ref: "unit-1",
      unit_kind: "section",
      title: "复印件",
      pov_subject_ref: "maya",
      content: "她核对了水印。\n\n日期比封存记录晚了三天。",
    })

    expect(parsed.error).toBe("")
    expect(
      shortProseContractError(parsed.artifact, context, "unit-1", "section"),
    ).toBe("")
    expect(shortProseDiagnostics(parsed.artifact!, context)).toMatchObject({
      paragraphCount: 2,
    })
    expect(
      shortProseContractError(
        { ...parsed.artifact!, title: "漂移标题" },
        context,
        "unit-1",
        "section",
      ),
    ).toContain("冻结单元计划")
  })
})
