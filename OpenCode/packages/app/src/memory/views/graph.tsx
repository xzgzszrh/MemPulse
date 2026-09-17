import { createMemo, createSignal, For, Match, Show, Switch } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { useLanguage } from "@/context/language"
import { GraphCanvas, createGraphController } from "../components/graph-canvas"
import { GraphSnapshot } from "../components/graph-snapshot"
import { GraphToolbar } from "../components/graph-toolbar"
import { EmptyState } from "../components/empty-state"
import { StateChip } from "../components/topic-row"
import { Card, Section } from "../components/section"
import { summarize } from "../format"
import { tagKindLabelKey } from "../labels"
import type { GraphNode } from "../types"
import { useMemory } from "../store"

/**
 * The graph section has two modes on purpose.
 *
 * The home page shows the *snapshot*: the layout is computed once and painted
 * once, with no animation loop, no listeners and no per-frame cost — opening the
 * app stays cheap. The interactive canvas only runs once you ask for it, and it
 * is the same physics and the same painting, so the still is a faithful preview
 * rather than a different picture.
 */
export function GraphSection() {
  const [live, setLive] = createSignal(false)

  return (
    <Switch>
      <Match when={!live()}>
        <GraphPreview onOpen={() => setLive(true)} />
      </Match>
      <Match when={live()}>
        <GraphDetail onClose={() => setLive(false)} />
      </Match>
    </Switch>
  )
}

function GraphPreview(props: { onOpen: () => void }) {
  const memory = useMemory()
  const language = useLanguage()
  const graph = createMemo(() => memory.graph())

  return (
    <div class="flex h-full min-h-0 flex-col gap-3">
      <div class="flex shrink-0 items-center gap-3">
        <span class="text-12-regular text-v2-text-text-faint">
          {language.t("memory.graph.summary", {
            topics: graph().stats.topics,
            entities: graph().stats.entities,
            relations: graph().stats.relations,
          })}
        </span>
        <ButtonV2 size="small" variant="outline" class="ml-auto" onClick={props.onOpen}>
          {language.t("memory.graph.openLive")}
          <Icon name="arrow-right" size="small" />
        </ButtonV2>
      </div>

      <div class="relative min-h-0 flex-1 overflow-hidden rounded-[10px] border border-v2-border-border-base bg-v2-background-bg-base shadow-[var(--v2-elevation-raised)]">
        <Show
          when={graph().nodes.length > 0}
          fallback={
            <EmptyState
              icon="dot-grid"
              title={language.t("memory.graph.empty")}
              description={language.t("memory.graph.empty.description")}
            />
          }
        >
          <GraphSnapshot data={graph()} class="absolute inset-0" />
          {/* A transparent hit target: the whole picture opens the live view. */}
          <button
            type="button"
            aria-label={language.t("memory.graph.openLive")}
            onClick={props.onOpen}
            class="absolute inset-0 cursor-pointer bg-transparent transition-colors hover:bg-v2-overlay-simple-overlay-hover focus-visible:outline-none focus-visible:[box-shadow:inset_0_0_0_1px_var(--v2-border-border-focus)]"
          />
        </Show>
      </div>
    </div>
  )
}

function GraphDetail(props: { onClose: () => void }) {
  const memory = useMemory()
  const language = useLanguage()

  const [query, setQuery] = createSignal("")
  const [hiddenKinds, setHiddenKinds] = createSignal<Set<string>>(new Set())
  const [selected, setSelected] = createSignal<GraphNode | undefined>()
  const graph = createMemo(() => memory.graph())
  const { controller, attach } = createGraphController()

  const counts = createMemo(() => {
    const map = new Map<string, number>()
    for (const node of graph().nodes) {
      if (node.type === "topic" || !node.kind) continue
      map.set(node.kind, (map.get(node.kind) ?? 0) + 1)
    }
    return map
  })

  const matches = createMemo(() => {
    const needle = query().trim().toLowerCase()
    if (!needle) return new Set<string>()
    return new Set(
      graph()
        .nodes.filter((node) => node.label.toLowerCase().includes(needle))
        .map((node) => node.id),
    )
  })

  const toggleKind = (kind: string) => {
    setHiddenKinds((current) => {
      const next = new Set(current)
      if (next.has(kind)) next.delete(kind)
      else next.add(kind)
      return next
    })
  }

  /** Keyboard- and screen-reader-reachable alternative to clicking the canvas. */
  const listed = createMemo(() => {
    const needle = query().trim().toLowerCase()
    const nodes = graph()
      .nodes.filter((node) => !node.type || node.type === "topic" || !hiddenKinds().has(node.kind ?? ""))
      .filter((node) => (needle ? node.label.toLowerCase().includes(needle) : true))
    return [...nodes].sort((a, b) => (b.degree ?? b.event_count ?? 0) - (a.degree ?? a.event_count ?? 0)).slice(0, 60)
  })

  const relatedTopics = createMemo(() => {
    const node = selected()
    if (!node || node.type === "topic") return []
    return graph()
      .edges.filter((edge) => edge.target === node.id || edge.source === node.id)
      .map((edge) => (edge.source === node.id ? edge.target : edge.source))
      .map((id) => graph().nodes.find((candidate) => candidate.id === id))
      .filter((candidate): candidate is GraphNode => Boolean(candidate))
  })

  return (
    <div class="flex h-full min-h-0 flex-col gap-3">
      <div class="flex shrink-0 flex-col gap-2">
        <div class="flex items-center gap-2">
          <ButtonV2 size="small" variant="ghost" onClick={props.onClose}>
            <Icon name="arrow-left" size="small" />
            {language.t("memory.graph.backToSnapshot")}
          </ButtonV2>
          <span class="ml-auto text-12-regular text-v2-text-text-faint">
            {language.t("memory.graph.summary", {
              topics: graph().stats.topics,
              entities: graph().stats.entities,
              relations: graph().stats.relations,
            })}
          </span>
        </div>
        <GraphToolbar
          query={query()}
          onQuery={setQuery}
          hiddenKinds={hiddenKinds()}
          onToggleKind={toggleKind}
          onReset={() => controller.reset()}
          onZoom={(factor) => controller.zoom(factor)}
          counts={counts()}
        />
      </div>

      <div class="flex min-h-0 flex-1 gap-3">
        <div class="relative min-h-0 min-w-0 flex-1 overflow-hidden rounded-[10px] border border-v2-border-border-base bg-v2-background-bg-base shadow-[var(--v2-elevation-raised)]">
          <Show
            when={graph().nodes.length > 0}
            fallback={
              <EmptyState
                icon="dot-grid"
                title={language.t("memory.graph.empty")}
                description={language.t("memory.graph.empty.description")}
              />
            }
          >
            <GraphCanvas
              data={graph()}
              selectedId={selected()?.id}
              hiddenKinds={hiddenKinds()}
              matches={matches()}
              onSelect={setSelected}
              onReady={attach}
            />
          </Show>
        </div>

        <aside class="flex w-56 shrink-0 flex-col gap-4 overflow-y-auto">
          <Section title={language.t("memory.graph.selection")}>
            <Show
              when={selected()}
              fallback={
                <p class="px-1 text-12-regular text-v2-text-text-faint">{language.t("memory.graph.selection.empty")}</p>
              }
            >
              {(node) => (
                <Card>
                  <div class="flex flex-col gap-2">
                    <div class="flex items-center gap-2">
                      <span class="min-w-0 flex-1 text-12-medium text-v2-text-text-base">{node().label}</span>
                      <Show when={node().type === "topic"}>
                        <StateChip state={node().state} />
                      </Show>
                    </div>
                    <Show when={node().summary || node().goal}>
                      <p class="text-12-regular text-v2-text-text-muted">
                        {summarize(node().summary || node().goal, 200)}
                      </p>
                    </Show>
                    <div class="flex flex-wrap gap-x-4 gap-y-1 text-12-regular text-v2-text-text-faint">
                      <Show when={node().type !== "topic"}>
                        <span>{language.t(tagKindLabelKey(node().kind))}</span>
                      </Show>
                      <Show when={node().event_count !== undefined}>
                        <span>{language.t("memory.topics.eventCount", { count: node().event_count ?? 0 })}</span>
                      </Show>
                      <Show when={node().degree !== undefined}>
                        <span>
                          {language.t("memory.graph.degree")} {node().degree}
                        </span>
                      </Show>
                    </div>
                  </div>
                </Card>
              )}
            </Show>
          </Section>

          <Show when={relatedTopics().length > 0}>
            <Section title={language.t("memory.graph.relatedTopics")} count={relatedTopics().length}>
              <Card class="flex flex-col gap-1 border-v2-border-border-base bg-v2-background-bg-layer-01 p-1">
                <For each={relatedTopics()}>
                  {(node) => (
                    <button
                      type="button"
                      onClick={() => {
                        setSelected(node)
                        controller.focus(node.id)
                      }}
                      class="flex items-center gap-2 rounded-[4px] px-1.5 py-1 text-left hover:bg-v2-overlay-simple-overlay-hover"
                    >
                      <span class="min-w-0 flex-1 truncate text-12-regular text-v2-text-text-base">{node.label}</span>
                    </button>
                  )}
                </For>
              </Card>
            </Section>
          </Show>

          <Section
            title={language.t("memory.graph.nodeList")}
            count={listed().length}
            bodyClass="flex flex-col rounded-[6px] border border-v2-border-border-base bg-v2-background-bg-layer-01 py-1"
          >
            <For each={listed()}>
              {(node) => (
                <button
                  type="button"
                  onClick={() => {
                    setSelected(node)
                    controller.focus(node.id)
                  }}
                  classList={{
                    "flex items-center gap-2 px-2 py-1 text-left hover:bg-v2-overlay-simple-overlay-hover": true,
                    "bg-v2-background-bg-layer-02": selected()?.id === node.id,
                  }}
                >
                  <Icon
                    name={node.type === "topic" ? "bullet-list" : "dot-grid"}
                    size="small"
                    class="shrink-0 text-v2-icon-icon-muted"
                  />
                  <span class="min-w-0 flex-1 truncate text-12-regular text-v2-text-text-muted">{node.label}</span>
                </button>
              )}
            </For>
          </Section>
        </aside>
      </div>
    </div>
  )
}
