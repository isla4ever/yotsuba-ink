import { useCallback, useEffect, useMemo, useState } from "react"
import type {
  StoryBibleFactEntry,
  StoryBibleForeshadowEntry,
  StoryBibleSummary,
} from "../contracts/storyBible"
import { getStoryBiblePage } from "../services/storyBibleApi"

export type StoryBiblePageStatus =
  | "idle"
  | "loading"
  | "loading-more"
  | "ready"
  | "error"

type PageState<T> = {
  error: string
  items: T[]
  nextCursor: string | null
  status: StoryBiblePageStatus
  total: number
}

type StoryBibleState = {
  facts: PageState<StoryBibleFactEntry>
  foreshadows: PageState<StoryBibleForeshadowEntry>
  summary: StoryBibleSummary | null
}

const emptyPage = <T,>(status: StoryBiblePageStatus = "idle"): PageState<T> => ({
  error: "",
  items: [],
  nextCursor: null,
  status,
  total: 0,
})

const emptyState = (): StoryBibleState => ({
  facts: emptyPage(),
  foreshadows: emptyPage(),
  summary: null,
})

export function useStoryBible(runId: string, revision: string) {
  const [state, setState] = useState<StoryBibleState>(emptyState)

  useEffect(() => {
    if (!runId) {
      setState(emptyState())
      return undefined
    }
    const controller = new AbortController()
    setState({
      facts: emptyPage("loading"),
      foreshadows: emptyPage("loading"),
      summary: null,
    })
    void Promise.allSettled([
      getStoryBiblePage(runId, "facts", undefined, controller.signal),
      getStoryBiblePage(runId, "foreshadow", undefined, controller.signal),
    ]).then(([factsResult, foreshadowResult]) => {
      if (controller.signal.aborted) return
      const facts =
        factsResult.status === "fulfilled"
          ? pageState(factsResult.value)
          : failedPage<StoryBibleFactEntry>(factsResult.reason)
      const foreshadows =
        foreshadowResult.status === "fulfilled"
          ? pageState(foreshadowResult.value)
          : failedPage<StoryBibleForeshadowEntry>(foreshadowResult.reason)
      setState({
        facts,
        foreshadows,
        summary:
          factsResult.status === "fulfilled"
            ? factsResult.value.summary
            : foreshadowResult.status === "fulfilled"
              ? foreshadowResult.value.summary
              : null,
      })
    })
    return () => controller.abort()
  }, [revision, runId])

  const loadMoreFacts = useCallback(async () => {
    const cursor = state.facts.nextCursor
    if (!runId || !cursor || state.facts.status === "loading-more") return
    setState((current) => ({
      ...current,
      facts: { ...current.facts, error: "", status: "loading-more" },
    }))
    try {
      const page = await getStoryBiblePage(runId, "facts", cursor)
      setState((current) => ({
        ...current,
        facts: appendPage(current.facts, page, (item) => item.fact_id),
        summary: page.summary,
      }))
    } catch (reason) {
      setState((current) => ({
        ...current,
        facts: failedAppend(current.facts, reason),
      }))
    }
  }, [runId, state.facts.nextCursor, state.facts.status])

  const loadMoreForeshadows = useCallback(async () => {
    const cursor = state.foreshadows.nextCursor
    if (!runId || !cursor || state.foreshadows.status === "loading-more") return
    setState((current) => ({
      ...current,
      foreshadows: {
        ...current.foreshadows,
        error: "",
        status: "loading-more",
      },
    }))
    try {
      const page = await getStoryBiblePage(runId, "foreshadow", cursor)
      setState((current) => ({
        ...current,
        foreshadows: appendPage(
          current.foreshadows,
          page,
          (item) => item.evidence_id,
        ),
        summary: page.summary,
      }))
    } catch (reason) {
      setState((current) => ({
        ...current,
        foreshadows: failedAppend(current.foreshadows, reason),
      }))
    }
  }, [runId, state.foreshadows.nextCursor, state.foreshadows.status])

  const error = useMemo(
    () => [state.facts.error, state.foreshadows.error].filter(Boolean).join(" "),
    [state.facts.error, state.foreshadows.error],
  )

  return {
    ...state,
    error,
    loadMoreFacts,
    loadMoreForeshadows,
  }
}

function pageState<T>(page: {
  items: T[]
  next_cursor: string | null
  total: number
}): PageState<T> {
  return {
    error: "",
    items: page.items,
    nextCursor: page.next_cursor,
    status: "ready",
    total: page.total,
  }
}

function appendPage<T>(
  current: PageState<T>,
  page: { items: T[]; next_cursor: string | null; total: number },
  identity: (item: T) => string,
): PageState<T> {
  const seen = new Set(current.items.map(identity))
  const appended = page.items.filter((item) => !seen.has(identity(item)))
  return {
    error: "",
    items: [...current.items, ...appended],
    nextCursor: page.next_cursor,
    status: "ready",
    total: page.total,
  }
}

function failedPage<T>(reason: unknown): PageState<T> {
  return {
    ...emptyPage<T>("error"),
    error: errorMessage(reason),
  }
}

function failedAppend<T>(current: PageState<T>, reason: unknown): PageState<T> {
  return {
    ...current,
    error: errorMessage(reason),
    status: "error",
  }
}

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "故事圣经读取失败"
}
