// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { ScreenplayDraft } from "../lib/phase32Screenplay"
import { ScreenplayArtifactEditor } from "./ScreenplayArtifactEditor"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("ScreenplayArtifactEditor", () => {
  it("renders a screenplay reading surface without form controls", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onSelectScene = vi.fn()
    act(() =>
      root.render(
        <ScreenplayArtifactEditor
          activeSceneRef="scene-2"
          artifact={screenplayPayload("scene-1")}
          artifactRef="p32-script-committed-scene-1"
          committedArtifactRefs={{ "scene-1": "p32-script-committed-scene-1" }}
          editable={false}
          onChange={vi.fn()}
          onSelectScene={onSelectScene}
          orderedSceneRefs={["scene-1", "scene-2"]}
          referenceContext={referenceContext()}
          revisionLabel="已接受不可变版本"
          selectedSceneRef="scene-1"
        />,
      ),
    )

    expect(container.querySelectorAll("input, textarea, select")).toHaveLength(
      0,
    )
    expect(container.textContent).toContain("签名页被换过")
    expect(container.textContent).toContain("已接受版本")

    act(() => findButton(container, "调度依据").click())
    expect(container.textContent).toContain("找到被替换的签名页")
    act(() =>
      container
        .querySelectorAll<HTMLButtonElement>(
          ".screenplay-rail-list > button",
        )[1]
        .click(),
    )
    expect(onSelectScene).toHaveBeenCalledWith("scene-2")

    act(() => root.unmount())
  })

  it("edits body blocks while preserving the frozen Scene identity and heading", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <ScreenplayArtifactEditor
          activeSceneRef="scene-1"
          artifact={screenplayPayload("scene-1")}
          artifactRef="p32-script-candidate-scene-1"
          committedArtifactRefs={{}}
          editable
          onChange={onChange}
          onSelectScene={vi.fn()}
          orderedSceneRefs={["scene-1", "scene-2"]}
          referenceContext={referenceContext()}
          revisionLabel="Scene 1 · Revision 4"
          selectedSceneRef="scene-1"
        />,
      ),
    )

    expect(
      container.querySelector('textarea[aria-label="正文块 1 内容"]'),
    ).toBeNull()
    const action = container.querySelector<HTMLTextAreaElement>(
      'textarea[aria-label="正文块 2 内容"]',
    )!
    expect(action.dataset.collaborationFieldPath).toBe("blocks.1.text")
    expect(action.dataset.collaborationUnit).toBe("scene-1")
    act(() => setInputValue(action, "玛雅把水印页贴到窗上，日期在冷光里显现。"))

    const changed = onChange.mock.calls.at(-1)?.[0] as ScreenplayDraft
    expect(changed.scene_ref).toBe("scene-1")
    expect(changed.blocks[0]).toEqual(screenplayPayload("scene-1").blocks[0])
    expect(changed.blocks[1].text).toContain("日期在冷光里显现")

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

function setInputValue(element: HTMLTextAreaElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    Object.getPrototypeOf(element),
    "value",
  )?.set
  setter?.call(element, value)
  element.dispatchEvent(new Event("input", { bubbles: true }))
  element.dispatchEvent(new Event("change", { bubbles: true }))
}

function screenplayPayload(sceneRef: "scene-1" | "scene-2"): ScreenplayDraft {
  const heading =
    sceneRef === "scene-1"
      ? "INT. 市档案馆 - NIGHT"
      : "INT. 市档案馆走廊 - NIGHT"
  return {
    scene_ref: sceneRef,
    blocks: [
      { kind: "scene_heading", text: heading },
      { kind: "action", text: "玛雅在熄灯前翻开档案盒。" },
      { kind: "dialogue", speaker_ref: "maya", text: "签名页被换过。" },
    ],
  }
}

function referenceContext() {
  return {
    cast: {
      maya: {
        displayName: "玛雅",
        ref: "maya",
        role: "档案记者",
        voice: "克制",
      },
      guard: {
        displayName: "周警卫",
        ref: "guard",
        role: "保安",
        voice: "程序化",
      },
    },
    scenes: [
      {
        sceneRef: "scene-1",
        heading: "INT. 市档案馆 - NIGHT",
        locationAndTime: "闭馆前十分钟",
        castSubjectRefs: ["maya"],
        visibleGoal: "找到被替换的签名页。",
        opposition: "保安要求她立即离开。",
        outcome: "她取得带水印的复印件。",
        softPageTarget: 2.5,
      },
      {
        sceneRef: "scene-2",
        heading: "INT. 市档案馆走廊 - NIGHT",
        locationAndTime: "闭馆前五分钟",
        castSubjectRefs: ["maya", "guard"],
        visibleGoal: "把证据带出档案馆。",
        opposition: "保安封锁出口。",
        outcome: "证据公开，玛雅身份暴露。",
        softPageTarget: 2,
      },
    ],
  }
}
