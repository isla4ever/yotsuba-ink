import { useEffect, useRef, useState } from "react"
import type {
  CollaborationThread,
  CollaborationThreadDetail,
} from "../contracts/authorCollaboration"
import { observeAuthorCollaboration } from "../services/authorCollaborationStream"

type Params = {
  activeThreadId: string
  enabled: boolean
  refreshDetail: (threadId?: string, signal?: AbortSignal) => Promise<CollaborationThreadDetail | null>
  refreshThreads: (signal?: AbortSignal) => Promise<CollaborationThread[]>
  runId: string
}

export function useCollaborationStream({
  activeThreadId,
  enabled,
  refreshDetail,
  refreshThreads,
  runId,
}: Params) {
  const [revision, setRevision] = useState(0)
  const cursorRef = useRef(0)

  useEffect(() => {
    cursorRef.current = 0
  }, [activeThreadId])

  useEffect(() => {
    if (!enabled || !activeThreadId) return undefined
    let reconnectTimer = 0
    const close = observeAuthorCollaboration(runId, activeThreadId, {
      after: cursorRef.current,
      onEvent: (event) => {
        cursorRef.current = Math.max(cursorRef.current, event.sequence)
        void Promise.all([
          refreshDetail(activeThreadId),
          refreshThreads(),
        ]).catch(() => undefined)
      },
      onDisconnect: () => {
        reconnectTimer = window.setTimeout(
          () => setRevision((value) => value + 1),
          1_200,
        )
      },
    })
    return () => {
      close()
      window.clearTimeout(reconnectTimer)
    }
  }, [activeThreadId, enabled, refreshDetail, refreshThreads, runId, revision])
}
