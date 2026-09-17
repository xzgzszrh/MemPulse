/**
 * Typed access to the local MemPulse service.
 *
 * The renderer has exactly one way in: the desktop preload bridge
 * (`platform.memory.request`), which forwards to the main-process MemoryBridge
 * over JSON-lines IPC. Everything else — filesystem, process control, network
 * ports — stays out of the renderer. When the bridge is absent (browser dev,
 * web build) we say so plainly instead of probing a port.
 *
 * Method names and parameter shapes mirror `MemPulse/src/mempulse/desktop.py`.
 */

import type { Platform } from "@/context/platform"
import type {
  Bootstrap,
  Checkpoint,
  ForgetReceipt,
  Graph,
  MemoryEvent,
  MemoryOperation,
  MemoryOperationKind,
  RestorePack,
  Route,
  SearchResult,
  Workspace,
} from "./types"

export type MemoryErrorCode = "unavailable" | "failed"

export class MemoryError extends Error {
  readonly code: MemoryErrorCode

  constructor(code: MemoryErrorCode, message: string) {
    super(message)
    this.name = "MemoryError"
    this.code = code
  }
}

/**
 * Browser preview only: with no preload bridge, a DEV build talks to the
 * MemPulse dev shim (`MemPulse/scripts/desktop_dev.py`, loopback port 51984),
 * which serves the same dispatcher. Production web builds still report the
 * service as unavailable — nothing outside the desktop app probes a port.
 */
const DEV_SHIM = "http://127.0.0.1:51984/api/desktop"

function devShim(): Platform["memory"] | undefined {
  if (!import.meta.env.DEV) return undefined
  return {
    async request<T = unknown>(input: { method: string; params?: Record<string, unknown> }): Promise<T> {
      const response = await fetch(DEV_SHIM, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ method: input.method, params: input.params ?? {} }),
      })
      const payload = (await response.json()) as { ok?: boolean; data?: T; error?: string }
      if (!response.ok || !payload.ok) throw new Error(payload.error || `memory dev shim returned ${response.status}`)
      return payload.data as T
    },
  }
}

export function createMemoryClient(platform: Platform) {
  const bridge = platform.memory ?? devShim()

  const request = async <T>(method: string, params: Record<string, unknown> = {}): Promise<T> => {
    // Surfaces switch on the error code, not this text; it exists so a stray
    // log or unhandled rejection still reads as English.
    if (!bridge) throw new MemoryError("unavailable", "Memory service is not available in this build")
    try {
      return await bridge.request<T>({ method, params })
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      throw new MemoryError("failed", message)
    }
  }

  const propose = (kind: MemoryOperationKind, payload: Record<string, unknown>) =>
    request<MemoryOperation>("propose_operation", { kind, payload, origin: "ui" })
  const confirm = (operation: MemoryOperation) =>
    request<MemoryOperation>("confirm_operation", { operation_id: operation.id, fingerprint: operation.fingerprint })
  // Called by an explicit UI confirmation button; model tools only propose.
  const commit = async <T>(kind: MemoryOperationKind, payload: Record<string, unknown>) => {
    const operation = await confirm(await propose(kind, payload))
    if (operation.status !== "applied") throw new Error(operation.error || "Memory operation was not applied")
    return operation.result as T
  }

  return {
    available: Boolean(bridge),
    propose,
    confirm,
    commit,
    pending: () => request<{ operations: MemoryOperation[] }>("pending_operations"),
    inbox: (sessionId: string) => request<{ events: MemoryEvent[] }>("capture_inbox", { session_id: sessionId }),
    reject: (operationId: string) => request<MemoryOperation>("reject_operation", { operation_id: operationId }),

    /** Topics, recent events, governance records, health and stats in one round trip. */
    bootstrap: () => request<Bootstrap>("bootstrap"),

    graph: () => request<Graph>("graph"),

    switchWorkspace: (workspace: Workspace) => request<Bootstrap>("switch_workspace", { workspace }),

    search: (query: string, limit = 30) => request<SearchResult>("search", { query, limit }),

    resolve: (query: string) => request<Route>("resolve", { query }),

    restore: (topicId: string) => request<RestorePack>("restore", { topic_id: topicId }),

    /** Snapshots the topic's current restore contract under a new revision. */
    checkpoint: (topicId: string) => commit<Checkpoint>("checkpoint", { topic_id: topicId }),

    forgetEvent: (eventId: string) => commit<ForgetReceipt>("forget", { target_type: "event", target_id: eventId }),

    forgetTopic: (topicId: string) => commit<ForgetReceipt>("forget", { target_type: "topic", target_id: topicId }),

    /** Field paths must begin with `metadata.`; the backend rejects anything else. */
    forgetField: (eventId: string, fieldPath: string) =>
      commit<ForgetReceipt>("forget_field", { event_id: eventId, field_path: fieldPath }),

    moveEvent: (eventId: string, topicId: string) =>
      commit<{ previous_topic?: string }>("move", { event_id: eventId, topic_id: topicId }),

    mergeTopics: (sourceId: string, targetId: string) =>
      commit<{ status?: string }>("merge", { source_id: sourceId, target_id: targetId }),

    splitTopic: (topicId: string, eventIds: string[], title: string) =>
      commit<{ topic_id?: string }>("split", { topic_id: topicId, event_ids: eventIds, title }),

    reindex: () => request<unknown>("reindex", {}),

    worker: () => request<unknown>("worker", {}),
  }
}

export type MemoryClient = ReturnType<typeof createMemoryClient>
