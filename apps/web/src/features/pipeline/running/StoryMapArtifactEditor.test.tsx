// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { StoryMapDraft } from "../lib/phase32StoryMap"
import { StoryMapArtifactEditor } from "./StoryMapArtifactEditor"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("StoryMapArtifactEditor", () => {
  it("writes field edits and anchor reordering without replacing stable refs", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <StoryMapArtifactEditor
          artifact={storyMap()}
          artifactRef="p32-story-map-candidate-1"
          editable
          revisionLabel="Revision 2"
          onChange={onChange}
        />,
      ),
    )

    act(() =>
      container
        .querySelector<HTMLButtonElement>('button[aria-label="下移锚点 1"]')
        ?.click(),
    )
    expect(
      (onChange.mock.calls.at(-1)?.[0] as StoryMapDraft).anchors.map(
        (anchor) => anchor.anchor_ref,
      ),
    ).toEqual(["anchor-2", "anchor-1"])

    const pressure = findField(container, "压力如何升级")
    act(() => {
      setInputValue(pressure, "公开档案与证人口供同时消失。")
    })
    const edited = onChange.mock.calls.at(-1)?.[0] as StoryMapDraft
    expect(edited.anchors[0].anchor_ref).toBe("anchor-1")
    expect(edited.anchors[0].pressure).toBe("公开档案与证人口供同时消失。")

    act(() => root.unmount())
  })

  it("keeps promise refs readonly and only adds a non-empty open question", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <StoryMapArtifactEditor
          artifact={storyMap()}
          artifactRef="p32-story-map-candidate-1"
          editable
          revisionLabel="Revision 2"
          onChange={onChange}
        />,
      ),
    )

    expect(container.textContent).toContain("promise-truth-cost")
    expect(container.textContent).toContain("不宣称上游承诺已核验")
    act(() => findButton(container, "收束与追问").click())
    const composer = container.querySelector<HTMLInputElement>(
      'input[placeholder="补充一个仍需在下游回答的问题"]',
    )!
    const add = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("添加"),
    )!
    expect(add.disabled).toBe(true)

    act(() => {
      setInputValue(composer, "谁签发了最初的删改指令？")
    })
    expect(add.disabled).toBe(false)
    act(() => add.click())
    expect(
      (onChange.mock.calls.at(-1)?.[0] as StoryMapDraft).open_questions,
    ).toEqual(["谁批准了最初的删改？", "谁签发了最初的删改指令？"])

    act(() => root.unmount())
  })

  it("disables structural editing for a committed artifact", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <StoryMapArtifactEditor
          artifact={storyMap()}
          artifactRef="p32-story-map-committed-1"
          editable={false}
          revisionLabel="Committed Artifact"
          onChange={vi.fn()}
        />,
      ),
    )

    expect(
      container.querySelector<HTMLButtonElement>(
        'button[aria-label="下移锚点 1"]',
      ),
    ).toBeNull()
    expect(container.querySelectorAll("textarea:not([readonly])")).toHaveLength(
      0,
    )
    expect(container.querySelector(".story-map-question-composer")).toBeNull()

    act(() => root.unmount())
  })
})

function findField(container: HTMLElement, label: string) {
  const field = Array.from(container.querySelectorAll("label")).find((node) =>
    node.textContent?.includes(label),
  )
  const textarea = field?.querySelector("textarea")
  if (!textarea) throw new Error(`Missing field: ${label}`)
  return textarea
}

function findButton(container: HTMLElement, label: string) {
  const button = Array.from(container.querySelectorAll("button")).find((node) =>
    node.textContent?.includes(label),
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
}

function storyMap(): StoryMapDraft {
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
