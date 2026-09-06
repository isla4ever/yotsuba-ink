import { useCallback, useEffect, useRef, useState } from "react"
import type { Phase32RunEnvelope, Phase32RunEvent } from "../contracts/run"
import { getRun, streamRunEvents } from "../services/runApi"
import { consumeRunEventStream } from "../services/runStream"

export type RunConnectionState = "idle" | "connecting" | "live" | "reconnecting" | "closed" | "error"

const quietStatuses = new Set([
  "awaiting_decision",
  "image_deferred",
  "completed",
  "failed",
  "cancelled",
])
const quietEvents = new Set([
  "decision.required",
  "stage.failed",
  "unit.failed",
  "evidence.recovery_required",
  "writeback.failed",
  "export.ready",
  "image.deferred",
])

export function useActiveRun(runId: string | null) {
  const [envelope, setEnvelope] = useState<Phase32RunEnvelope | null>(null)
  const [events, setEvents] = useState<Phase32RunEvent[]>([])
  const [connection, setConnection] = useState<RunConnectionState>("idle")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [streamRevision, setStreamRevision] = useState(0)
  const envelopeRef = useRef<Phase32RunEnvelope | null>(null)

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      if (!runId) return null
      const loaded = await getRun(runId, signal)
      envelopeRef.current = loaded
      setEnvelope(loaded)
      setError("")
      return loaded
    },
    [runId],
  )

  useEffect(() => {
    envelopeRef.current = null
    setEnvelope(null)
    setEvents([])
    setError("")
    setConnection(runId ? "connecting" : "idle")
    if (!runId) {
      setLoading(false)
      return undefined
    }

    const controller = new AbortController()
    let refreshTimer: ReturnType<typeof setTimeout> | null = null
    let reconnectAttempt = 0
    let lastSequence = 0
    let terminal = false

    const scheduleRefresh = () => {
      if (refreshTimer) return
      refreshTimer = setTimeout(() => {
        refreshTimer = null
        void refresh(controller.signal).catch(() => undefined)
      }, 160)
    }

    const connect = async () => {
      setLoading(true)
      try {
        const initial = await refresh(controller.signal)
        terminal = Boolean(
          initial && quietStatuses.has(initial.read_model.status),
        )
        setLoading(false)

        while (!controller.signal.aborted) {
          setConnection(reconnectAttempt === 0 ? "connecting" : "reconnecting")
          try {
            const response = await streamRunEvents(
              runId,
              controller.signal,
              lastSequence,
            )
            setConnection("live")
            await consumeRunEventStream({
              response,
              signal: controller.signal,
              onEvents: (batch) => {
                lastSequence = Math.max(
                  lastSequence,
                  ...batch.map((event) => event.sequence),
                )
                if (batch.some((event) => quietEvents.has(event.type)))
                  terminal = true
                setEvents((current) => {
                  const bySequence = new Map(
                    current.map((event) => [event.sequence, event]),
                  )
                  batch.forEach((event) =>
                    bySequence.set(event.sequence, event),
                  )
                  return [...bySequence.values()]
                    .sort((left, right) => left.sequence - right.sequence)
                    .slice(-1000)
                })
                scheduleRefresh()
              },
            })
            const latest = await refresh(controller.signal)
            if (
              terminal ||
              quietStatuses.has(latest?.read_model.status ?? "")
            ) {
              setConnection("closed")
              return
            }
          } catch (reason) {
            if (controller.signal.aborted) return
            setError(
              reason instanceof Error ? reason.message : "Run 事件连接失败",
            )
          }

          reconnectAttempt += 1
          setConnection("reconnecting")
          await waitForReconnect(
            Math.min(1000 * 2 ** (reconnectAttempt - 1), 8000),
            controller.signal,
          )
        }
      } catch (reason) {
        if (controller.signal.aborted) return
        setLoading(false)
        setConnection("error")
        setError(reason instanceof Error ? reason.message : "Run 状态读取失败")
      }
    }

    void connect()
    return () => {
      controller.abort()
      if (refreshTimer) clearTimeout(refreshTimer)
    }
  }, [refresh, runId, streamRevision])

  const reconnect = useCallback(() => {
    setStreamRevision((value) => value + 1)
  }, [])

  return { connection, envelope, error, events, loading, reconnect, refresh }
}

function waitForReconnect(delay: number, signal: AbortSignal) {
  return new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, delay)
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer)
        resolve()
      },
      { once: true },
    )
  })
}
