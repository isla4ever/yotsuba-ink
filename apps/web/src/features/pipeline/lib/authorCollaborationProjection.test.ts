import { describe, expect, it } from "vitest"
import { defaultCollaborationUnit } from "./authorCollaborationProjection"

describe("defaultCollaborationUnit", () => {
  it("projects the first Section Plan unit from the Phase 32 units contract", () => {
    expect(
      defaultCollaborationUnit(
        "section_plan",
        JSON.stringify({
          units: [
            {
              unit_ref: "unit-1",
              title: "第一节",
            },
          ],
        }),
      ),
    ).toEqual({ label: "第一节", unitRef: "unit-1" })
  })

  it("projects the first Rolling Detail chapter from its bounded window", () => {
    expect(
      defaultCollaborationUnit(
        "rolling_detail",
        JSON.stringify({
          windows: [
            {
              window_ref: "window-1",
              chapters: [
                {
                  chapter_ref: "chapter-1",
                  title: "第一份证据",
                },
              ],
            },
          ],
        }),
      ),
    ).toEqual({ label: "第一份证据", unitRef: "chapter-1" })
  })
})
