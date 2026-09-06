import { useCallback, useEffect, useMemo, useState } from "react"
import type {
  StoryBibleEntry,
  StoryBibleSection,
  StoryBibleSummary,
} from "../contracts/storyBible"
import { getStoryBiblePage } from "../services/storyBibleApi"

export type StoryBiblePageStatus = "idle" | "loading" | "refreshing" | "loading-more" | "ready" | "error"

type StoryBiblePageState = {
  error: string
  items: StoryBibleEntry[]
  nextCursor: string | null
  status: StoryBiblePageStatus
  summary: StoryBibleSummary | null
  total: number
}

type StoryBibleState = {
  pages: Record<StoryBibleSection, StoryBiblePageState>
  runId: string
}

const SECTIONS: StoryBibleSection[] = [
  "overview",
  "cast",
  "structure",
  "units",
  "continuity",
]

export function useStoryBible(
  runId: string,
  section: StoryBibleSection,
  authorityRevision: string,
) {
  const [state, setState] = useState<StoryBibleState>(() => emptyState(runId))
  const current = state.runId === runId ? state.pages[section] : emptyPage()

  useEffect(() => {
    if (!runId) {
      setState(emptyState(""))
      return undefined
    }
    const controller = new AbortController()
    setState((previous) => {
      const base = previous.runId === runId ? previous : emptyState(runId)
      const existing = base.pages[section]
      return updatePage(base, section, {
        ...existing,
        error: "",
        status: existing.items.length ? "refreshing" : "loading",
      })
    })
    void getStoryBiblePage(runId, section, undefined, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) return
        setState((previous) =>
          previous.runId === runId
            ? updatePage(previous, section, pageState(page))
            : previous,
        )
      })
      .catch((reason) => {
        if (controller.signal.aborted) return
        setState((previous) => {
          if (previous.runId !== runId) return previous
          const existing = previous.pages[section]
          return updatePage(previous, section, {
            ...existing,
            error: errorMessage(reason),
            status: "error",
          })
        })
      })
    return () => controller.abort()
  }, [authorityRevision, runId, section])

  const loadMore = useCallback(async () => {
    const snapshot = state.runId === runId ? state.pages[section] : emptyPage()
    if (!runId || !snapshot.nextCursor || snapshot.status === "loading-more")
      return
    setState((previous) =>
      updatePage(previous, section, {
        ...previous.pages[section],
        error: "",
        status: "loading-more",
      }),
    )
    try {
      const page = await getStoryBiblePage(runId, section, snapshot.nextCursor)
      setState((previous) =>
        previous.runId === runId
          ? updatePage(
              previous,
              section,
              appendPage(previous.pages[section], page),
            )
          : previous,
      )
    } catch (reason) {
      setState((previous) =>
        updatePage(previous, section, {
          ...previous.pages[section],
          error: errorMessage(reason),
          status: "error",
        }),
      )
    }
  }, [runId, section, state])

  const summary = useMemo(
    () =>
      current.summary ??
      SECTIONS.map((item) => state.pages[item].summary).find(Boolean) ??
      null,
    [current.summary, state.pages],
  )

  return {
    ...current,
    loadMore,
    refreshing: current.status === "refreshing",
    summary,
  }
}

function emptyPage(): StoryBiblePageState {
  return {
    error: "",
    items: [],
    nextCursor: null,
    status: "idle",
    summary: null,
    total: 0,
  }
}

function emptyState(runId: string): StoryBibleState {
  return {
    runId,
    pages: Object.fromEntries(
      SECTIONS.map((section) => [section, emptyPage()]),
    ) as Record<StoryBibleSection, StoryBiblePageState>,
  }
}

function updatePage(
  state: StoryBibleState,
  section: StoryBibleSection,
  page: StoryBiblePageState,
) {
  return { ...state, pages: { ...state.pages, [section]: page } }
}

function pageState(page: {
  items: StoryBibleEntry[]
  next_cursor: string | null
  summary: StoryBibleSummary
  total: number
}): StoryBiblePageState {
  return {
    error: "",
    items: page.items,
    nextCursor: page.next_cursor,
    status: "ready",
    summary: page.summary,
    total: page.total,
  }
}

function appendPage(
  current: StoryBiblePageState,
  page: {
    items: StoryBibleEntry[]
    next_cursor: string | null
    summary: StoryBibleSummary
    total: number
  },
): StoryBiblePageState {
  const seen = new Set(current.items.map((item) => item.entry_ref))
  return {
    error: "",
    items: [
      ...current.items,
      ...page.items.filter((item) => !seen.has(item.entry_ref)),
    ],
    nextCursor: page.next_cursor,
    status: "ready",
    summary: page.summary,
    total: page.total,
  }
}

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "故事圣经读取失败"
}
