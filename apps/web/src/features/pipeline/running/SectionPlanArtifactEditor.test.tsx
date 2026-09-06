// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { SectionPlanDraft } from "../lib/phase32SectionPlan"
import { SectionPlanArtifactEditor } from "./SectionPlanArtifactEditor"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("SectionPlanArtifactEditor", () => {
  it("navigates units and keeps reading mode free of form controls", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <SectionPlanArtifactEditor
          artifact={sectionPlanPayload()}
          artifactRef="p32-section-plan-committed-1"
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
    const secondUnit = container.querySelectorAll<HTMLButtonElement>(
      ".section-plan-rail-list > button",
    )[1]
    act(() => secondUnit.click())
    expect(container.textContent).toContain("公开记录")

    act(() => findButton(container, "场景负载").click())
    expect(container.textContent).toContain("听证准备、证人犹豫")

    act(() => findButton(container, "状态交接").click())
    expect(container.textContent).toContain("证据进入公共记录")

    act(() => root.unmount())
  })

  it("edits only the selected unit and preserves its stable identity", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onChange = vi.fn()
    act(() =>
      root.render(
        <SectionPlanArtifactEditor
          artifact={sectionPlanPayload()}
          artifactRef="p32-section-plan-candidate-1"
          editable
          onChange={onChange}
          referenceContext={referenceContext()}
          revisionLabel="Revision 2"
        />,
      ),
    )

    const title = container.querySelector<HTMLInputElement>(
      'input[aria-label="单元标题"]',
    )!
    act(() => setInputValue(title, "签名页的最后一分钟"))
    let changed = onChange.mock.calls.at(-1)?.[0] as SectionPlanDraft
    expect(changed.units[0].title).toContain("最后一分钟")
    expect(changed.units[0].unit_ref).toBe("unit-1")
    expect(changed.units[1]).toEqual(sectionPlanPayload().units[1])

    const budget = container.querySelector<HTMLInputElement>(
      'input[aria-label="单元软字数"]',
    )!
    act(() => setInputValue(budget, "3600"))
    changed = (onChange.mock.calls.at(-1)?.[0] as SectionPlanDraft)
    expect(changed.units[0].soft_character_budget).toBe(3_600)

    const pov = container.querySelector<HTMLSelectElement>(
      'select[aria-label="单元 POV"]',
    )!
    act(() => setInputValue(pov, "liang"))
    changed = (onChange.mock.calls.at(-1)?.[0] as SectionPlanDraft)
    expect(changed.units[0].pov_subject_ref).toBe("liang")

    act(() =>
      container
        .querySelector<HTMLButtonElement>('button[aria-label="下移单元 1"]')
        ?.click(),
    )
    changed = (onChange.mock.calls.at(-1)?.[0] as SectionPlanDraft)
    expect(changed.units.map((unit) => unit.unit_ref)).toEqual([
      "unit-2",
      "unit-1",
    ])
    expect(changed.units.map((unit) => unit.ordinal)).toEqual([1, 2])

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
  element: HTMLInputElement | HTMLSelectElement,
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
    cast: {
      maya: { ref: "maya", label: "玛雅" },
      liang: { ref: "liang", label: "梁策" },
    },
    promises: {
      "promise-truth-cost": {
        ref: "promise-truth-cost",
        anchorRefs: ["anchor-1"],
        labels: ["让主角获得第一条可核验证据。"],
      },
      "promise-public-record": {
        ref: "promise-public-record",
        anchorRefs: ["anchor-2"],
        labels: ["迫使机构公开回应。"],
      },
    },
  }
}

function sectionPlanPayload(): SectionPlanDraft {
  return {
    units: [
      {
        unit_ref: "unit-1",
        ordinal: 1,
        title: "封存前的签名",
        dramatic_job: "让主角获得第一条可独立核验的签名证据。",
        pov_subject_ref: "maya",
        scene_load: "档案室核验与走廊拦截。",
        handoff: "签名日期与封存命令发生冲突。",
        soft_character_budget: 3_000,
        promise_refs: ["promise-truth-cost"],
      },
      {
        unit_ref: "unit-2",
        ordinal: 2,
        title: "公开记录",
        dramatic_job: "迫使机构对签名链作出公开回应。",
        pov_subject_ref: "liang",
        scene_load: "听证准备、证人犹豫与公开质询。",
        handoff: "证据进入公共记录，主角承担职业代价。",
        soft_character_budget: 4_000,
        promise_refs: ["promise-truth-cost", "promise-public-record"],
      },
    ],
  }
}
