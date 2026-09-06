// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { SceneDeckDraft } from "../lib/phase32SceneDeck"
import { SceneDeckArtifactEditor } from "./SceneDeckArtifactEditor"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("SceneDeckArtifactEditor", () => {
  it("navigates scenes and keeps reading mode free of form fields", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <SceneDeckArtifactEditor
          artifact={sceneDeckPayload()}
          artifactRef="p32-scene-deck-committed-1"
          editable={false}
          onChange={vi.fn()}
          referenceContext={referenceContext()}
          revisionLabel="已确认版本"
        />,
      ),
    )

    expect(container.querySelectorAll("input, textarea, select")).toHaveLength(
      0,
    )
    const secondScene = container.querySelectorAll<HTMLButtonElement>(
      ".scene-deck-rail-list > button",
    )[1]
    act(() => secondScene.click())
    expect(container.textContent).toContain("封锁出口")

    act(() => findButton(container, "制作信息").click())
    expect(container.textContent).toContain("周警卫")
    expect(container.textContent).toContain("市档案馆走廊")

    act(() => root.unmount())
  })

  it("edits only the selected scene and preserves identity while reordering", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <SceneDeckArtifactEditor
          artifact={sceneDeckPayload()}
          artifactRef="p32-scene-deck-candidate-1"
          editable
          onChange={onChange}
          referenceContext={referenceContext()}
          revisionLabel="Revision 5"
        />,
      ),
    )

    const opposition = container.querySelector<HTMLTextAreaElement>(
      'textarea[aria-label="台面对抗"]',
    )!
    act(() => setInputValue(opposition, "保安切断主灯并锁住封存柜。"))
    let changed = onChange.mock.calls.at(-1)?.[0] as SceneDeckDraft
    expect(changed.scenes[0].opposition).toContain("切断主灯")
    expect(changed.scenes[0].scene_ref).toBe("scene-1")
    expect(changed.scenes[1]).toEqual(sceneDeckPayload().scenes[1])

    act(() =>
      container
        .querySelector<HTMLButtonElement>('button[aria-label="下移场景 1"]')
        ?.click(),
    )
    changed = (onChange.mock.calls.at(-1)?.[0] as SceneDeckDraft)
    expect(changed.scenes.map((scene) => scene.scene_ref)).toEqual([
      "scene-2",
      "scene-1",
    ])

    act(() => root.unmount())
  })
})

function findButton(container: HTMLElement, label: string) {
  const button = Array.from(container.querySelectorAll("button")).find((item) =>
    item.textContent?.includes(label),
  )
  if (!button) throw new Error(`Missing button: ${label}`)
  return button
}

function setInputValue(
  element: HTMLInputElement | HTMLTextAreaElement,
  value: string,
) {
  const setter = Object.getOwnPropertyDescriptor(
    Object.getPrototypeOf(element),
    "value",
  )?.set
  setter?.call(element, value)
  element.dispatchEvent(new Event("input", { bubbles: true }))
  element.dispatchEvent(new Event("change", { bubbles: true }))
}

function referenceContext() {
  return {
    beats: [
      {
        beatRef: "beat-1",
        decision: "主角复制未授权记录。",
        dramaticJob: "迫使主角越权查档。",
        outcome: "她留下可追查的证据。",
      },
    ],
    cast: {
      maya: { label: "玛雅", ref: "maya", role: "档案记者" },
      guard: { label: "周警卫", ref: "guard", role: "档案馆保安" },
    },
  }
}

function sceneDeckPayload(): SceneDeckDraft {
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
