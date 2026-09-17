/**
 * One reactive store behind every memory surface — the session side panel, the
 * `/memory` workbench and the settings section read the same data, so moving
 * between them never refetches and never disagrees.
 *
 * Refresh policy: while at least one surface is mounted we poll `bootstrap` on
 * a slow interval, paused whenever the window is hidden. Writes refresh
 * immediately. Polling stops as soon as the last surface unmounts.
 */

import { createMemo, createSignal, onCleanup, onMount } from "solid-js"
import { createStore } from "solid-js/store"
import { createSimpleContext } from "@opencode-ai/ui/context"
import { usePlatform } from "@/context/platform"
import { useSettings } from "@/context/settings"
import { createMemoryClient, MemoryError } from "./client"
import type { Bootstrap, Graph, MemoryEvent, Topic, Workspace } from "./types"

const POLL_INTERVAL = 5000

export type MemoryStatus = "loading" | "ready" | "unavailable" | "error"

const emptyGraph: Graph = { nodes: [], edges: [], stats: { topics: 0, entities: 0, relations: 0 } }

export function createMemoryStore() {
  const platform = usePlatform()
  const settings = useSettings()
  const client = createMemoryClient(platform)

  const [bootstrap, setBootstrap] = createSignal<Bootstrap | undefined>()
  const [graph, setGraph] = createSignal<Graph>(emptyGraph)
  const [status, setStatus] = createSignal<MemoryStatus>(client.available ? "loading" : "unavailable")
  const [error, setError] = createSignal<string | undefined>()
  const [graphLoading, setGraphLoading] = createSignal(false)
  const [state, setState] = createStore({ switchingWorkspace: false })
  let workspaceRevision = 0

  const topics = createMemo(() => bootstrap()?.topics ?? [])
  const events = createMemo(() => bootstrap()?.events ?? [])
  const governance = createMemo(
    () => bootstrap()?.governance ?? { preferences: [], knowledge: [], checkpoints: [], receipts: [] },
  )
  const health = createMemo(() => bootstrap()?.health)
  const workspace = createMemo<Workspace>(() => bootstrap()?.workspace ?? "demo")

  const byUpdated = createMemo(() =>
    [...topics()].sort((a, b) => Date.parse(b.updated_at ?? "") - Date.parse(a.updated_at ?? "") || 0),
  )

  const byRecent = createMemo(() =>
    [...events()].sort((a, b) => Date.parse(b.occurred_at ?? "") - Date.parse(a.occurred_at ?? "")),
  )

  const topicById = createMemo(() => new Map(topics().map((topic) => [topic.topic_id, topic])))

  const eventsByTopic = createMemo(() => {
    const map = new Map<string, MemoryEvent[]>()
    for (const event of byRecent()) {
      const list = map.get(event.topic_id)
      if (list) list.push(event)
      else map.set(event.topic_id, [event])
    }
    return map
  })

  const stats = createMemo(() => {
    const data = bootstrap()
    const list = data?.topics ?? []
    return {
      topics: list.length,
      events: data?.stats?.events ?? 0,
      entities: data?.stats?.tags ?? 0,
      incomplete: list.filter((topic) => topic.state === "incomplete").length,
      relations: graph().stats.relations,
    }
  })

  async function loadGraph() {
    if (!client.available || graphLoading()) return
    const revision = workspaceRevision
    setGraphLoading(true)
    try {
      const result = await client.graph()
      if (revision === workspaceRevision) setGraph(result)
    } catch (cause) {
      if (revision === workspaceRevision && cause instanceof MemoryError && cause.code === "unavailable") setStatus("unavailable")
    } finally {
      if (revision === workspaceRevision) setGraphLoading(false)
    }
  }

  async function refresh(options: { graph?: boolean } = {}) {
    if (state.switchingWorkspace) return
    if (!client.available) {
      setStatus("unavailable")
      return
    }
    const revision = workspaceRevision
    try {
      const result = await client.bootstrap()
      if (revision !== workspaceRevision) return
      setBootstrap(result)
      setStatus("ready")
      setError(undefined)
    } catch (cause) {
      if (revision !== workspaceRevision) return
      const memoryError = cause instanceof MemoryError ? cause : undefined
      setStatus(memoryError?.code === "unavailable" ? "unavailable" : "error")
      setError(cause instanceof Error ? cause.message : String(cause))
      return
    }
    if (options.graph) void loadGraph()
  }

  async function switchWorkspace(workspace: Workspace) {
    if (state.switchingWorkspace) return false
    setState("switchingWorkspace", true)
    workspaceRevision += 1
    try {
      const result = await client.switchWorkspace(workspace)
      setBootstrap(result)
      // A workspace switch changes both databases. Discard the old graph before
      // requesting the new one, and ignore any earlier polling responses.
      setGraph(emptyGraph)
      setGraphLoading(true)
      setStatus("ready")
      setError(undefined)
      setGraph(await client.graph())
      return true
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
      return false
    } finally {
      setGraphLoading(false)
      setState("switchingWorkspace", false)
    }
  }

  /** Wrap a mutation so a failure surfaces once and the store always resyncs. */
  async function mutate<T>(run: (client: ReturnType<typeof createMemoryClient>) => Promise<T>): Promise<T | undefined> {
    try {
      const result = await run(client)
      setError(undefined)
      return result
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
      return undefined
    } finally {
      void refresh()
    }
  }

  // Poll only while something is watching. The counter lets the session panel
  // and the workbench share one timer instead of each starting their own.
  let subscribers = 0
  let timer: ReturnType<typeof setInterval> | undefined

  function tick() {
    if (!settings.memory.liveRefresh()) return
    if (typeof document !== "undefined" && document.visibilityState !== "visible") return
    void refresh()
  }

  function subscribe() {
    subscribers += 1
    if (subscribers === 1) {
      timer = setInterval(tick, POLL_INTERVAL)
      if (typeof document !== "undefined") document.addEventListener("visibilitychange", tick)
    }
    return () => {
      subscribers -= 1
      if (subscribers > 0) return
      if (timer) clearInterval(timer)
      timer = undefined
      if (typeof document !== "undefined") document.removeEventListener("visibilitychange", tick)
    }
  }

  onCleanup(() => {
    if (timer) clearInterval(timer)
  })

  return {
    client,
    available: client.available,
    bootstrap,
    graph,
    graphLoading,
    status,
    error,
    topics,
    byUpdated,
    byRecent,
    eventsByTopic,
    topicById,
    governance,
    health,
    workspace,
    switchingWorkspace: () => state.switchingWorkspace,
    switchWorkspace,
    stats,
    refresh,
    loadGraph,
    mutate,
    subscribe,
    setError,
    /** Resolve a topic, tolerating a stale selection after a merge or forget. */
    topic: (id: string | undefined): Topic | undefined => (id ? topicById().get(id) : undefined),
    /** A project is a hint; only a durable user-confirmed binding selects a task. */
    topicForSession: (sessionId: string | undefined, directory: string | undefined): Topic | undefined => {
      const binding = bootstrap()?.bindings?.find(
        (item) => item.session_id === sessionId && (!directory || item.project_ref === directory),
      )
      return binding ? topicById().get(binding.topic_id) : undefined
    },
    eventsForSession: (sessionId: string | undefined, directory: string | undefined): MemoryEvent[] => {
      if (!sessionId && !directory) return []
      return byRecent().filter((event) => {
        const metadata = event.metadata ?? {}
        return (
          Boolean(sessionId) &&
          metadata.opencode_session_id === sessionId &&
          (!directory || metadata.opencode_directory === directory)
        )
      })
    },
  }
}

export type MemoryStore = ReturnType<typeof createMemoryStore>

export const { use: useMemory, provider: MemoryProvider } = createSimpleContext({
  name: "Memory",
  gate: false,
  init: () => createMemoryStore(),
})

/**
 * Load on mount and keep the store polling while the calling surface is alive.
 * Every component that renders memory data must call this — without it the store
 * stays in `loading` until some other surface happens to fetch first.
 */
export function useMemorySurface(options: { graph?: boolean } = {}) {
  const memory = useMemory()
  onMount(() => {
    const unsubscribe = memory.subscribe()
    void memory.refresh({ graph: options.graph })
    onCleanup(unsubscribe)
  })
  return memory
}
