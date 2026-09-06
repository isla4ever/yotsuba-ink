import { describe, expect, it } from "vitest"
import {
  extractLongChapterContext,
  longChapterContractError,
  longChapterDiagnostics,
  parsePhase32LongChapter,
} from "./phase32LongChapter"

describe("phase32 long chapter projection", () => {
  it("projects the frozen chapter context and keeps length diagnostic soft", () => {
    const context = extractLongChapterContext(
      {
        windows: [
          {
            window_ref: "window-1",
            ordinal: 1,
            chapters: [
              {
                chapter_ref: "chapter-1",
                ordinal: 1,
                volume_ref: "volume-1",
                title: "第一份证据",
                pov_subject_ref: "maya",
                cast_subject_refs: ["maya"],
                dramatic_job: "确认复印件来自封存卷宗。",
                entry_state: "只有一份来历不明的复印件。",
                conflict: "原件被临时封存。",
                stakes: "证据链可能失效。",
                exit_state: "水印日期被确认异常。",
                hook: "审批签名指向内部人员。",
                handoff: "下一章追查异常封存日期。",
                length_hint: 3200,
                scenes: [
                  {
                    scene_ref: "scene-1",
                    location: "档案室",
                    time_context: "深夜",
                    goal: "核对水印",
                    opposition: "值班员催促离开",
                    outcome: "确认日期矛盾",
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        volumes: [
          {
            volume_ref: "volume-1",
            ordinal: 1,
            part_ref: "part-1",
            promise: "追出签名链",
            conflict: "机构阻止公开核验",
          },
        ],
      },
      {
        book_promise: "公共记忆最终由谁书写？",
        parts: [
          {
            part_ref: "part-1",
            ordinal: 1,
            dramatic_question: "她能否公开证据？",
            entry_state: "证据无法核验",
            exit_state: "证据进入公共记录",
          },
        ],
      },
      {
        characters: [
          {
            subject_ref: "maya",
            display_name: "玛雅",
            role: "档案记者",
            voice: "克制、具体",
          },
        ],
      },
    )
    const parsed = parsePhase32LongChapter({
      chapter_ref: "chapter-1",
      volume_ref: "volume-1",
      title: "第一份证据",
      pov_subject_ref: "maya",
      content: "她把复印件贴近台灯。\n\n水印日期晚了三天。",
    })

    expect(parsed.error).toBe("")
    expect(
      longChapterContractError(parsed.artifact, context, "chapter-1"),
    ).toBe("")
    expect(
      longChapterDiagnostics(parsed.artifact!, context.chapters[0]),
    ).toMatchObject({
      paragraphCount: 2,
    })
    expect(
      longChapterContractError(
        { ...parsed.artifact!, pov_subject_ref: "ghost" },
        context,
        "chapter-1",
      ),
    ).toContain("POV")
    expect(
      longChapterContractError(
        { ...parsed.artifact!, title: "漂移标题" },
        context,
        "chapter-1",
      ),
    ).toContain("冻结细纲")
  })
})
