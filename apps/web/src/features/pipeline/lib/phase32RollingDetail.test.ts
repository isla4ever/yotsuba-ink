import { describe, expect, it } from "vitest"
import {
  extractRollingDetailReferenceContext,
  parsePhase32RollingDetail,
  reorderDetailChapters,
  reorderDetailScenes,
  rollingDetailDiagnostics,
} from "./phase32RollingDetail"

describe("Phase 32 Rolling Detail contract", () => {
  it("parses bounded Window chapter blueprints and diagnostics", () => {
    const parsed = parsePhase32RollingDetail(detailPayload())

    expect(parsed.error).toBe("")
    expect(parsed.artifact?.windows[0].chapters).toHaveLength(2)
    expect(rollingDetailDiagnostics(parsed.artifact!)).toEqual({
      chapterCount: 2,
      sceneCount: 2,
      totalLengthHint: 7_000,
      volumeCoverage: [
        { chapterCount: 1, lengthHint: 3_000, volumeRef: "volume-1" },
        { chapterCount: 1, lengthHint: 4_000, volumeRef: "volume-2" },
      ],
      windowCount: 1,
    })
  })

  it("reorders frozen Chapter and Scene refs while rebuilding ordinals", () => {
    const artifact = parsePhase32RollingDetail(detailPayload()).artifact!
    const chapters = reorderDetailChapters(artifact, "window-1", 0, 1)
    expect(
      chapters.windows[0].chapters.map((chapter) => chapter.chapter_ref),
    ).toEqual(["chapter-2", "chapter-1"])
    expect(
      chapters.windows[0].chapters.map((chapter) => chapter.ordinal),
    ).toEqual([1, 2])

    const scenes = reorderDetailScenes(
      [
        artifact.windows[0].chapters[0].scenes[0],
        {
          ...artifact.windows[0].chapters[0].scenes[0],
          scene_ref: "scene-1b",
          ordinal: 2,
        },
      ],
      0,
      1,
    )
    expect(scenes.map((scene) => scene.scene_ref)).toEqual([
      "scene-1b",
      "scene-1",
    ])
    expect(scenes.map((scene) => scene.ordinal)).toEqual([1, 2])
  })

  it("keeps malformed drafts visible while reporting identity drift", () => {
    const payload = detailPayload()
    payload.windows[0].chapters[1].chapter_ref = "chapter-1"
    payload.windows[0].chapters[1].scenes[0].scene_ref = "scene-1"

    const parsed = parsePhase32RollingDetail(payload)
    expect(parsed.artifact).not.toBeNull()
    expect(parsed.error).toContain("重复身份")
  })

  it("extracts readable labels from committed Volume and Cast artifacts", () => {
    const context = extractRollingDetailReferenceContext(
      {
        volumes: [
          {
            volume_ref: "volume-1",
            promise: "找到原始档案",
            cast_subject_refs: ["maya"],
          },
        ],
      },
      { characters: [{ subject_ref: "maya", display_name: "玛雅" }] },
    )
    expect(context.volumes["volume-1"].label).toContain("卷 01")
    expect(context.cast.maya.label).toBe("玛雅")
    expect(context.volumeCast["volume-1"]).toEqual(["maya"])
  })
})

export function detailPayload() {
  return {
    windows: [
      {
        window_ref: "window-1",
        ordinal: 1,
        volume_refs: ["volume-1", "volume-2"],
        entry_state: "主角拿到来源不明的复印件。",
        handoff: "下一窗口进入证人保护与责任追查。",
        next_window_entry_state: "证据进入公共记录。",
        chapters: [
          chapter("chapter-1", 1, "volume-1", "scene-1", 3_000),
          chapter("chapter-2", 2, "volume-2", "scene-2", 4_000),
        ],
      },
    ],
  }
}

function chapter(
  chapterRef: string,
  ordinal: number,
  volumeRef: string,
  sceneRef: string,
  lengthHint: number,
) {
  return {
    chapter_ref: chapterRef,
    ordinal,
    volume_ref: volumeRef,
    title: ordinal === 1 ? "第一份证据" : "公开听证",
    pov_subject_ref: "maya",
    cast_subject_refs: ["maya"],
    dramatic_job: "把纸面异常推进为公开回应。",
    entry_state: "主角掌握异常水印日期。",
    scenes: [
      {
        scene_ref: sceneRef,
        ordinal: 1,
        location: "市档案馆",
        time_context: "闭馆前",
        cast_subject_refs: ["maya"],
        goal: "锁定审批签名。",
        opposition: "记录员拒绝登记。",
        outcome: "异常日期进入正式议程。",
      },
    ],
    conflict: "证据可信度与职业安全冲突。",
    stakes: "公开过程会让主角失去原职。",
    exit_state: "证据进入公共记录。",
    hook: "原始封存单被撤回。",
    handoff: "下一章追查审批人。",
    length_hint: lengthHint,
  }
}
