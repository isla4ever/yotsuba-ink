import { describe, expect, it } from "vitest"
import {
  extractSceneDeckReferenceContext,
  parsePhase32SceneDeck,
  reorderSceneDeckScenes,
  sceneDeckDiagnostics,
} from "./phase32SceneDeck"

describe("phase32SceneDeck", () => {
  it("parses visible scene contracts and derives real Cast coverage", () => {
    const parsed = parsePhase32SceneDeck(sceneDeckPayload())
    expect(parsed.error).toBe("")
    const context = extractSceneDeckReferenceContext(
      beatBoardPayload(),
      castPayload(),
    )
    const diagnostics = sceneDeckDiagnostics(parsed.artifact!, context)

    expect(diagnostics).toMatchObject({
      averagePageTarget: 2,
      sceneCount: 2,
      totalPageTarget: 4,
      unknownCastRefs: [],
    })
    expect(diagnostics.castCoverage).toEqual([
      { count: 2, ref: "maya" },
      { count: 1, ref: "guard" },
    ])
    expect(context.beats[0]).toMatchObject({
      beatRef: "beat-1",
      decision: "主角复制未授权记录。",
    })
  })

  it("rejects invalid page targets and duplicate Cast references", () => {
    const payload = sceneDeckPayload()
    payload.scenes[0].soft_page_target = 0
    payload.scenes[1].cast_subject_refs = ["maya", "maya"]
    expect(parsePhase32SceneDeck(payload).error).toContain("无效引用")
  })

  it("reorders scenes without changing stable identity", () => {
    const scenes = sceneDeckPayload().scenes
    expect(
      reorderSceneDeckScenes(scenes, 0, 1).map((scene) => scene.scene_ref),
    ).toEqual(["scene-2", "scene-1"])
    expect(reorderSceneDeckScenes(scenes, 0, -1)).toBe(scenes)
  })
})

function sceneDeckPayload() {
  return {
    scenes: [
      {
        scene_ref: "scene-1",
        heading: "INT. 市档案馆 - NIGHT",
        location_and_time: "闭馆前十分钟",
        cast_subject_refs: ["maya"],
        visible_goal: "找到被替换的签名页。",
        opposition: "保安要求她立即离开。",
        outcome: "她取得带水印的复印件。",
        soft_page_target: 2.5,
      },
      {
        scene_ref: "scene-2",
        heading: "INT. 市档案馆走廊 - NIGHT",
        location_and_time: "闭馆前五分钟",
        cast_subject_refs: ["maya", "guard"],
        visible_goal: "把复印件同步到公开记录。",
        opposition: "保安封锁出口并检查随身物品。",
        outcome: "证据公开，主角也暴露为调查对象。",
        soft_page_target: 1.5,
      },
    ],
  }
}

function beatBoardPayload() {
  return {
    beats: [
      {
        beat_ref: "beat-1",
        dramatic_job: "迫使主角越权查档。",
        character_decision: "主角复制未授权记录。",
        outcome: "她留下可追查的证据。",
      },
    ],
  }
}

function castPayload() {
  return {
    characters: [
      { subject_ref: "maya", display_name: "玛雅", role: "档案记者" },
      { subject_ref: "guard", display_name: "周警卫", role: "档案馆保安" },
    ],
  }
}
