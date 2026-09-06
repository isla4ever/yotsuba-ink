import type { Phase32RunEvent } from "../contracts/run"

export async function consumeRunEventStream({
  onEvents,
  response,
  signal,
}: {
  onEvents: (events: Phase32RunEvent[]) => void | Promise<void>
  response: Response
  signal?: AbortSignal
}) {
  if (!response.ok) throw new Error(`SSE 连接失败：${response.status}`)
  if (!response.body) throw new Error("SSE 响应没有可读取的数据流")

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  const abort = () => {
    void reader.cancel()
  }
  signal?.addEventListener("abort", abort, { once: true })

  try {
    while (true) {
      if (signal?.aborted)
        throw new DOMException("Run stream aborted", "AbortError")
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      const parsed = drainSseEvents(buffer)
      buffer = parsed.remainder
      if (parsed.events.length) await onEvents(parsed.events)
      if (done) return
    }
  } finally {
    signal?.removeEventListener("abort", abort)
  }
}

function drainSseEvents(buffer: string) {
  const events: Phase32RunEvent[] = []
  const chunks = buffer.replace(/\r\n/g, "\n").split("\n\n")
  const remainder = chunks.pop() ?? ""
  for (const chunk of chunks) {
    const data = chunk
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n")
    if (!data || data === "[DONE]") continue
    events.push(parseRunEvent(data))
  }
  return { events, remainder }
}

function parseRunEvent(data: string): Phase32RunEvent {
  const value: unknown = JSON.parse(data)
  if (!isRunEvent(value)) throw new Error("SSE 事件不符合 Phase 32 事件合同")
  return value
}

function isRunEvent(value: unknown): value is Phase32RunEvent {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false
  const event = value as Record<string, unknown>
  return (
    typeof event.event_id === "string" &&
    Number.isInteger(event.sequence) &&
    typeof event.occurred_at === "string" &&
    typeof event.run_id === "string" &&
    typeof event.thread_id === "string" &&
    ["screenplay_sample", "short_novel", "long_novel"].includes(
      String(event.creation_route_id),
    ) &&
    typeof event.route_revision === "string" &&
    typeof event.route_manifest_digest === "string" &&
    typeof event.definition_digest === "string" &&
    typeof event.type === "string" &&
    typeof event.stage_id === "string" &&
    typeof event.unit_ref === "string" &&
    (event.artifact_kind === null || typeof event.artifact_kind === "string") &&
    typeof event.node_id === "string" &&
    typeof event.status === "string" &&
    (event.payload === null ||
      (typeof event.payload === "object" && !Array.isArray(event.payload))) &&
    typeof event.payload_ref === "string" &&
    typeof event.checkpoint_id === "string"
  )
}
