import type { CollaborationStreamEvent } from "../contracts/authorCollaboration"

type Options = {
  after?: number
  onEvent: (event: CollaborationStreamEvent) => void
  onDisconnect?: () => void
}

export function observeAuthorCollaboration(
  runId: string,
  threadId: string,
  { after = 0, onDisconnect, onEvent }: Options,
) {
  const url = `/api/runs/${encodeURIComponent(runId)}/collaboration/threads/${encodeURIComponent(threadId)}/stream?after=${Math.max(0, after)}`
  const stream = new EventSource(url)
  stream.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as CollaborationStreamEvent)
    } catch {
      // Ignore a malformed event; the next thread refresh remains authoritative.
    }
  }
  stream.onerror = () => {
    stream.close()
    onDisconnect?.()
  }
  return () => stream.close()
}
