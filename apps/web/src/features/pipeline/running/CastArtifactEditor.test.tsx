// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { CharacterBibleDraft } from "../lib/phase32Cast"
import { CastArtifactEditor } from "./CastArtifactEditor"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("CastArtifactEditor", () => {
  it("selects a character and edits literary fields without changing subject refs", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <CastArtifactEditor
          artifact={castArtifact()}
          artifactRef="p32-character-bible-candidate-1"
          editable
          onChange={onChange}
          revisionLabel="Revision 3"
          routeId="short_novel"
        />,
      ),
    )

    const secondCharacter = Array.from(
      container.querySelectorAll<HTMLButtonElement>(
        ".phase32-cast-rail-list > button",
      ),
    )[1]
    act(() => secondCharacter.click())
    const desire = findField(container, "可观察欲望")
    act(() => setInputValue(desire, "在证据公开前保住最后一份原件。"))
    const edited = onChange.mock.calls.at(-1)?.[0] as CharacterBibleDraft
    expect(edited.characters.map((item) => item.subject_ref)).toEqual([
      "maya",
      "lin",
    ])
    expect(edited.characters[1].desire).toContain("最后一份原件")

    act(() => root.unmount())
  })

  it("adds a directed relationship only between registered subjects", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <CastArtifactEditor
          artifact={{ ...castArtifact(), relationships: [] }}
          artifactRef="p32-character-bible-candidate-1"
          editable
          onChange={onChange}
          revisionLabel="Revision 3"
          routeId="screenplay_sample"
        />,
      ),
    )

    act(() => findButton(container, "关系账本").click())
    const select = container.querySelector<HTMLSelectElement>(
      'select[aria-label="选择新关系目标人物"]',
    )!
    act(() => setInputValue(select, "lin"))
    const add = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("新增有向关系"),
    )!
    act(() => add.click())
    const edited = onChange.mock.calls.at(-1)?.[0] as CharacterBibleDraft
    expect(edited.relationships).toHaveLength(1)
    expect(edited.relationships[0]).toMatchObject({
      from_subject_ref: "maya",
      to_subject_ref: "lin",
    })

    act(() => root.unmount())
  })

  it("keeps committed character and relationship content readonly", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <CastArtifactEditor
          artifact={castArtifact()}
          artifactRef="p32-character-bible-committed-1"
          editable={false}
          onChange={vi.fn()}
          revisionLabel="Committed Artifact"
          routeId="long_novel"
        />,
      ),
    )

    expect(container.querySelectorAll("textarea:not([readonly])")).toHaveLength(
      0,
    )
    expect(container.querySelectorAll("input:not([readonly])")).toHaveLength(0)
    expect(container.textContent).not.toContain("新增有向关系")
    expect(container.querySelector('button[aria-label^="删除关系"]')).toBeNull()

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
  element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
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

function castArtifact(): CharacterBibleDraft {
  return {
    characters: [
      {
        subject_ref: "maya",
        display_name: "玛雅",
        role: "档案记者",
        desire: "查清被删去的真相",
        stakes: "失去职业与家人的信任",
        constraints: ["不能公开未经核实的证据"],
        voice: "短句，先核对事实再表达",
        arc_scope: "从旁观者变成承担后果的人",
      },
      {
        subject_ref: "lin",
        display_name: "林岚",
        role: "档案馆员",
        desire: "保住最后一份原始记录",
        stakes: "过去的沉默会被公开",
        constraints: ["无法带走原件"],
        voice: "谨慎，用程序语言保护自己",
        arc_scope: "从阻拦者变成有限证人",
      },
    ],
    relationships: [
      {
        from_subject_ref: "maya",
        to_subject_ref: "lin",
        pressure: "两人对公开证据的时机意见相反。",
        change_trigger: "玛雅提出能保护证人的公开方案。",
      },
    ],
  }
}
