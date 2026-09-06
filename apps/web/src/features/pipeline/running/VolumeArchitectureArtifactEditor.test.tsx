// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { VolumeArchitectureDraft } from "../lib/phase32Volumes"
import { VolumeArchitectureArtifactEditor } from "./VolumeArchitectureArtifactEditor"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("VolumeArchitectureArtifactEditor", () => {
  it("selects and reorders stable Volumes with contiguous ordinals", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <VolumeArchitectureArtifactEditor
          artifact={volumeArchitecture()}
          artifactRef="p32-volumes-candidate-1"
          editable
          onChange={onChange}
          referenceContext={referenceContext()}
          revisionLabel="Revision 3"
        />,
      ),
    )

    const volumeTwo = Array.from(
      container.querySelectorAll<HTMLButtonElement>(
        ".phase32-volumes-rail-list > button",
      ),
    )[1]
    act(() => volumeTwo.click())
    expect(container.textContent).toContain("公开自己的违规取证")
    expect(container.textContent).toContain("Part 02 · 公共听证")

    act(() =>
      container
        .querySelector<HTMLButtonElement>('button[aria-label="上移 Volume 2"]')
        ?.click(),
    )
    const reordered = onChange.mock.calls.at(-1)?.[0] as VolumeArchitectureDraft
    expect(reordered.volumes.map((volume) => volume.volume_ref)).toEqual([
      "volume-2",
      "volume-1",
    ])
    expect(reordered.volumes.map((volume) => volume.ordinal)).toEqual([1, 2])
    expect(reordered.volumes[0].part_ref).toBe("part-2")

    act(() => root.unmount())
  })

  it("edits literary fields and soft length without exposing frozen refs", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <VolumeArchitectureArtifactEditor
          artifact={volumeArchitecture()}
          artifactRef="p32-volumes-candidate-1"
          editable
          onChange={onChange}
          referenceContext={referenceContext()}
          revisionLabel="Revision 3"
        />,
      ),
    )

    const promise = findField(container, "本卷向读者承诺什么")
    act(() => setInputValue(promise, "找到一条任何人都能独立核验的证据链。"))
    const edited = onChange.mock.calls.at(-1)?.[0] as VolumeArchitectureDraft
    expect(edited.volumes[0].promise).toContain("独立核验")
    expect(edited.volumes[0].volume_ref).toBe("volume-1")
    expect(edited.volumes[0].cast_subject_refs).toEqual(["maya"])

    const length = container.querySelector<HTMLInputElement>(
      'input[aria-label="卷册软篇幅"]',
    )!
    act(() => setInputValue(length, "42000"))
    expect(
      (onChange.mock.calls.at(-1)?.[0] as VolumeArchitectureDraft).volumes[0]
        .length_hint,
    ).toBe(42_000)
    expect(container.textContent).toContain(
      "卷册标识、Part 归属与人物范围保持冻结",
    )

    act(() => root.unmount())
  })

  it("keeps a committed aggregate readonly", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <VolumeArchitectureArtifactEditor
          artifact={volumeArchitecture()}
          artifactRef="p32-volumes-committed-1"
          editable={false}
          onChange={vi.fn()}
          referenceContext={referenceContext()}
          revisionLabel="Committed Artifact"
        />,
      ),
    )

    expect(
      container.querySelector<HTMLButtonElement>(
        'button[aria-label="下移 Volume 1"]',
      ),
    ).toBeNull()
    expect(container.querySelectorAll("textarea:not([readonly])")).toHaveLength(
      0,
    )
    expect(
      container.querySelector<HTMLInputElement>(
        'input[aria-label="卷册软篇幅"]',
      ),
    ).toBeNull()
    expect(container.textContent).toContain("软篇幅")

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

function referenceContext() {
  return {
    parts: {
      "part-1": { ref: "part-1", label: "Part 01 · 内部调查" },
      "part-2": { ref: "part-2", label: "Part 02 · 公共听证" },
    },
    cast: {
      maya: { ref: "maya", label: "玛雅" },
    },
  }
}

function volumeArchitecture(): VolumeArchitectureDraft {
  return {
    volumes: [
      {
        volume_ref: "volume-1",
        ordinal: 1,
        part_ref: "part-1",
        promise: "找到第一份原始档案。",
        conflict: "机构试图销毁备份。",
        climax: "主角在听证会上提交证据。",
        closure: "调查进入公众视野。",
        cast_subject_refs: ["maya"],
        length_hint: 40_000,
      },
      {
        volume_ref: "volume-2",
        ordinal: 2,
        part_ref: "part-2",
        promise: "把证据推进为可公开核验的签名链。",
        conflict: "证人安全与公开时限冲突。",
        climax: "主角公开自己的违规取证。",
        closure: "事实进入公共记录。",
        cast_subject_refs: ["maya"],
        length_hint: 55_000,
      },
    ],
  }
}
