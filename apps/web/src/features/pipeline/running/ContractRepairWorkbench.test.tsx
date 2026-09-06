// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Phase32RunEnvelope } from "../contracts/run"
import { ContractRepairWorkbench } from "./ContractRepairWorkbench"

const repair = vi.hoisted(() => ({
  flow: null as unknown as Record<string, unknown>,
}))

vi.mock("../state/useContractRepair", () => ({
  useContractRepair: () => repair.flow,
}))

vi.mock("./RollingDetailArtifactEditor", () => ({
  RollingDetailArtifactEditor: (props: {
    allowCastScopeEditing?: boolean
    onChange: (value: Record<string, unknown>) => void
  }) => (
    <div>
      Rolling Detail Repair Editor
      <span>{props.allowCastScopeEditing ? "Cast Scope Enabled" : ""}</span>
      <button onClick={() => props.onChange(detailPayload())} type="button">
        修改隔离稿
      </button>
    </div>
  ),
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("ContractRepairWorkbench", () => {
  beforeEach(() => {
    repair.flow = {
      begin: vi.fn(),
      cancel: vi.fn(),
      change: vi.fn(),
      error: "",
      hasChanges: false,
      payload: null,
      phase: "ready",
      quarantine: quarantineFixture(),
      submit: vi.fn(),
    }
  })

  it("shows the stable finding and only loads an eligible quarantine", () => {
    const { container, root } = renderWorkbench()

    expect(container.textContent).toContain("滚动细纲未进入候选库")
    expect(container.textContent).toContain("chapter-01 人物范围无效")
    expect(container.textContent).toContain("隔离修复不会增加该计数")
    expect(container.textContent).not.toContain('"windows"')
    act(() => findButton(container, "载入隔离稿").click())
    expect(repair.flow.begin).toHaveBeenCalledOnce()

    act(() => root.unmount())
  })

  it("keeps contract errors visible and never exposes an accept action", () => {
    repair.flow = {
      ...repair.flow,
      error: "Contract repair source or Run authority is stale",
      hasChanges: true,
      payload: detailPayload(),
      phase: "editing",
    }
    const { container, root } = renderWorkbench()

    expect(container.textContent).toContain("Run authority is stale")
    expect(container.textContent).toContain("Cast Scope Enabled")
    expect(container.textContent).toContain("只产生候选，不自动接受")
    expect(container.textContent).not.toContain("确认当前细纲")
    act(() => findButton(container, "重新校验并恢复候选").click())
    expect(repair.flow.submit).toHaveBeenCalledOnce()

    act(() => root.unmount())
  })
})

function renderWorkbench() {
  const container = document.createElement("div")
  const root = createRoot(container)
  act(() =>
    root.render(
      <ContractRepairWorkbench
        onRestored={vi.fn()}
        referenceContext={{ cast: {}, volumes: {}, volumeCast: {} }}
        run={failedRun()}
      />,
    ),
  )
  return { container, root }
}

function findButton(container: HTMLElement, label: string) {
  const button = Array.from(container.querySelectorAll("button")).find((item) =>
    item.textContent?.includes(label),
  )
  if (!button) throw new Error(`Missing button: ${label}`)
  return button
}

function quarantineFixture() {
  return {
    run_id: "contract-run",
    creation_route_id: "long_novel",
    stage_id: "rolling_detail",
    definition_digest: "a".repeat(64),
    domain_revision: 7,
    provider_receipt_ref: `p32-provider-operation-${"b".repeat(64)}`,
    provider_request_signature: "c".repeat(64),
    source_payload_digest: "d".repeat(64),
    source_payload: detailPayload(),
    eligible: true,
    findings: [
      {
        code: "stage_reference_contract_invalid",
        message: "chapter-01 人物范围无效",
      },
    ],
  }
}

function detailPayload() {
  return {
    windows: [
      {
        window_ref: "window-1",
        ordinal: 1,
        volume_refs: ["volume-1"],
        entry_state: "进入",
        handoff: "交接",
        next_window_entry_state: "下一窗口",
        chapters: [
          {
            chapter_ref: "chapter-1",
            ordinal: 1,
            volume_ref: "volume-1",
            title: "第一章",
            pov_subject_ref: "maya",
            cast_subject_refs: ["maya"],
            dramatic_job: "推进证据链",
            entry_state: "只有复印件",
            conflict: "核验受阻",
            stakes: "证据失效",
            exit_state: "水印确认",
            hook: "日期异常",
            handoff: "追查封存日期",
            length_hint: 3_000,
            scenes: [
              {
                scene_ref: "scene-1",
                ordinal: 1,
                location: "档案馆",
                time_context: "闭馆前",
                cast_subject_refs: ["maya"],
                goal: "核对水印",
                opposition: "被催离",
                outcome: "确认来源",
              },
            ],
          },
        ],
      },
    ],
  }
}

function failedRun() {
  return {
    definition: { run_id: "contract-run" },
    read_model: {
      failure: {
        message: "Provider 返回未通过人物引用合同",
      },
      provider_usage: { provider_operations: 9 },
    },
  } as unknown as Phase32RunEnvelope
}
