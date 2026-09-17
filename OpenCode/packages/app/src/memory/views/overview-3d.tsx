import { createEffect, createMemo, createSignal, For, onCleanup, onMount, Show } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { KeybindV2 } from "@opencode-ai/ui/v2/keybind-v2"
import { MenuV2 } from "@opencode-ai/ui/v2/menu-v2"
import { useCommand } from "@/context/command"
import type { LocalProject } from "@/context/layout"
import { useLanguage } from "@/context/language"
import { displayName } from "@/pages/layout/helpers"
import { buildScene, mountConstellation, placeholderGraph, type SceneNode } from "../constellation"
import { readPalette } from "../graph-render"
import { MemPulseWordmark } from "../components/brand"
import { useMemory } from "../store"
import type { MemorySection } from "../types"
import "./overview-3d.css"

export type RecentSession = {
  id: string
  title: string
  when: string
  project: string
  open: () => void
}

/**
 * The landing surface: MemPulse's mark over the live memory constellation, and
 * two floating surfaces for recent sessions and the next action. Workbench
 * sections are reached through the workbench entry rather than repeated here.
 *
 * Styling follows the OpenCode v2 tokens end to end (surface, hairline borders,
 * Inter, one accent) so the page belongs to the app instead of sitting on top
 * of it. The 3D scene is real data from the memory service; an empty workspace
 * shows a faint placeholder constellation rather than a blank canvas.
 */
export function Overview3D(props: {
  projects: LocalProject[]
  project?: LocalProject
  recent: RecentSession[]
  onNewSession: () => void
  onChooseProject: (project: LocalProject) => void
  onBrowseProject: () => void
  onEnterWorkbench: (section?: MemorySection) => void
  onOpenTopic: (topicId: string) => void
  onOpenProject?: (project: LocalProject) => void
}) {
  const memory = useMemory()
  const language = useLanguage()
  const command = useCommand()
  let containerRef: HTMLDivElement | undefined
  let canvasRef: HTMLCanvasElement | undefined

  const [hovered, setHovered] = createSignal<{ node: SceneNode; x: number; y: number }>()
  const [reducedMotion, setReducedMotion] = createSignal(false)
  const [scene, setScene] = createSignal(buildScene(placeholderGraph(), fallbackPalette()))

  const graph = createMemo(() => {
    const live = memory.graph()
    return live.nodes.length > 0 ? live : placeholderGraph()
  })
  const empty = createMemo(() => memory.graph().nodes.length === 0)
  const stats = memory.stats
  const newSessionKeybind = createMemo(() => command.keybindParts("session.new"))
  const project = createMemo(() => props.project ?? props.projects[0])
  const projectName = createMemo(() => {
    const value = project()
    return value ? displayName(value) : ""
  })
  const projectPath = createMemo(() => project()?.worktree ?? "")

  onMount(() => {
    const canvas = canvasRef
    const container = containerRef
    if (!canvas || !container) return
    const media = window.matchMedia("(prefers-reduced-motion: reduce)")
    setReducedMotion(media.matches)
    const onMedia = (event: MediaQueryListEvent) => setReducedMotion(event.matches)
    media.addEventListener("change", onMedia)

    // Rebuild whenever the data or the theme changes; the render loop reads the signal.
    createEffect(() => {
      setScene(buildScene(graph(), readPalette(container)))
    })
    const themeObserver = new MutationObserver(() => setScene(buildScene(graph(), readPalette(container))))
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "data-theme", "data-color-scheme", "style"],
    })

    const dispose = mountConstellation(canvas, container, {
      scene,
      reducedMotion,
      onHover: (node, at) => setHovered(node && node.label ? { node, x: at.x, y: at.y } : undefined),
      onSelect: (node) => {
        if (node.id.startsWith("placeholder_")) return
        if (node.type === "topic") {
          props.onOpenTopic(node.id)
          return
        }
        props.onEnterWorkbench("graph")
      },
    })
    createEffect(() => {
      scene()
      reducedMotion()
      dispose.invalidate()
    })
    onCleanup(() => {
      dispose()
      themeObserver.disconnect()
      media.removeEventListener("change", onMedia)
    })
  })

  const tooltipStyle = () => {
    const h = hovered()
    if (!h || !containerRef) return {}
    const rect = containerRef.getBoundingClientRect()
    const left = Math.min(rect.width - 272, Math.max(12, h.x + 16))
    const top = Math.min(rect.height - 120, Math.max(12, h.y - 12))
    return { left: `${left}px`, top: `${top}px` }
  }

  return (
    <div
      ref={containerRef}
      class="memory-overview relative h-full w-full select-none overflow-hidden bg-v2-background-bg-base text-v2-text-text-base"
    >
      <canvas
        ref={canvasRef}
        class="absolute inset-0 block h-full w-full cursor-grab active:cursor-grabbing"
        aria-hidden="true"
      />
      <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_62%,var(--v2-background-bg-deep)_100%)] opacity-50" />

      {/* Hover card */}
      <Show when={hovered()}>
        {(h) => (
          <div
            class="pointer-events-none absolute z-20 w-64 rounded-[10px] border border-v2-border-border-base bg-v2-background-bg-base p-3 shadow-[var(--v2-elevation-floating)]"
            style={tooltipStyle()}
          >
            <div class="flex items-center gap-2">
              <span class="h-2 w-2 shrink-0 rounded-full" style={{ "background-color": h().node.color }} />
              <span class="truncate text-14-medium text-v2-text-text-base">{h().node.label}</span>
              <span class="ml-auto shrink-0 text-12-regular text-v2-text-text-faint">
                {h().node.type === "topic"
                  ? language.t("memory.landing.node.topic")
                  : language.t("memory.landing.node.entity")}
              </span>
            </div>
            <Show when={h().node.goal}>
              <p class="mt-1.5 line-clamp-2 text-12-regular leading-[1.5] text-v2-text-text-muted">{h().node.goal}</p>
            </Show>
            <div class="mt-2 flex items-center justify-between border-t border-v2-border-border-base pt-2 text-12-regular text-v2-text-text-faint">
              <span>
                {h().node.type === "topic"
                  ? language.t("memory.topics.eventCount", { count: h().node.eventCount })
                  : `${language.t("memory.graph.degree")} ${h().node.degree}`}
              </span>
              <span class="text-v2-text-text-accent">{language.t("memory.landing.node.open")}</span>
            </div>
          </div>
        )}
      </Show>

      {/* The overlay leaves the constellation interactive between its surfaces. */}
      <div class="pointer-events-none relative flex h-full min-h-0 flex-col gap-16 overflow-y-auto overscroll-contain px-5 pb-6 pt-8 sm:px-8">
        <div class="flex shrink-0 flex-col items-center gap-3">
          <MemPulseWordmark height={56} />
          <p class="text-center text-12-regular text-v2-text-text-muted">{language.t("memory.landing.tagline")}</p>
        </div>

        <div class="mx-auto mt-auto flex w-full max-w-[880px] shrink-0 flex-col gap-3">
          <div class="memory-home-panels grid gap-3">
            <section
              class="memory-home-surface pointer-events-auto min-w-0 rounded-[16px] p-4"
              aria-label={language.t("memory.landing.card.recent")}
            >
              <h2 class="memory-home-heading text-12-medium text-v2-text-text-muted">{language.t("memory.landing.card.recent")}</h2>
              <Show
                when={props.recent.length > 0}
                fallback={
                  <div class="memory-home-empty flex items-center gap-2 text-14-regular text-v2-text-text-muted">
                    <Icon name="bubble-5" size="small" />
                    <span>{language.t("memory.landing.card.recent.empty")}</span>
                  </div>
                }
              >
                <ul class="memory-home-recent-list -mx-2" data-component="memory-home-recent-list">
                  <For each={props.recent.slice(0, 3)}>
                    {(item) => (
                      <li>
                        <button
                          type="button"
                          class="memory-home-recent group flex h-full w-full min-w-0 items-center gap-2 rounded-lg px-2 text-left transition-colors hover:bg-v2-overlay-simple-overlay-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-v2-border-border-focus"
                          title={item.title}
                          onClick={item.open}
                        >
                          <span class="min-w-0 flex-1 truncate text-14-regular text-v2-text-text-base">
                            {item.title}
                          </span>
                          <span class="shrink-0 text-12-regular text-v2-text-text-muted">{item.when}</span>
                          <Icon name="arrow-right" size="small" class="shrink-0 text-v2-icon-icon-muted" />
                        </button>
                      </li>
                    )}
                  </For>
                </ul>
              </Show>
            </section>

            <div class="memory-home-surface memory-home-actions pointer-events-auto min-w-0 rounded-[16px] p-4">
              <MenuV2 placement="top-start" gutter={6} modal={false}>
                <MenuV2.Trigger
                  as={ButtonV2}
                  variant="ghost"
                  class="memory-home-project"
                  title={projectPath() || language.t("command.project.open")}
                >
                  <span class="flex min-w-0 items-center gap-2">
                    <Icon name="folder" size="small" class="shrink-0" />
                    <span class="truncate">
                      {projectName() || language.t("memory.landing.card.newSession.noProject")}
                    </span>
                  </span>
                  <Icon name="chevron-down" size="small" class="shrink-0" />
                </MenuV2.Trigger>
                <MenuV2.Portal>
                  <MenuV2.Content class="memory-home-project-menu">
                    <Show when={props.projects.length > 0}>
                      <MenuV2.RadioGroup
                        value={projectPath()}
                        onChange={(directory) => {
                          const selected = props.projects.find((item) => item.worktree === directory)
                          if (selected) props.onChooseProject(selected)
                        }}
                      >
                        <For each={props.projects}>
                          {(item) => (
                            <MenuV2.RadioItem class="memory-home-project-option" value={item.worktree} title={item.worktree}>
                              <span class="memory-home-project-label">
                                <span class="block truncate">{displayName(item)}</span>
                                <span class="block truncate text-12-regular text-v2-text-text-muted">{item.worktree}</span>
                              </span>
                            </MenuV2.RadioItem>
                          )}
                        </For>
                      </MenuV2.RadioGroup>
                      <MenuV2.Separator />
                    </Show>
                    <MenuV2.Item onSelect={props.onBrowseProject}>
                      <Icon name="folder" size="small" />
                      {language.t("command.project.open")}
                    </MenuV2.Item>
                  </MenuV2.Content>
                </MenuV2.Portal>
              </MenuV2>
              <ButtonV2 size="large" variant="contrast" class="memory-home-action" onClick={props.onNewSession}>
                <span class="flex min-w-0 items-center gap-2">
                  <Icon name="new-session" size="small" />
                  <span class="truncate">{language.t("memory.landing.card.newSession")}</span>
                </span>
                <Show when={newSessionKeybind().length > 0}>
                  <KeybindV2 keys={newSessionKeybind()} variant="ghost" class="memory-home-keybind shrink-0" />
                </Show>
              </ButtonV2>
              <ButtonV2
                size="large"
                variant="outline"
                class="memory-home-action"
                onClick={() => props.onEnterWorkbench("topics")}
              >
                <span class="flex min-w-0 items-center gap-2">
                  <Icon name="brain" size="small" />
                  <span class="truncate">{language.t("memory.landing.workbench")}</span>
                </span>
                <Icon name="arrow-right" size="small" />
              </ButtonV2>
              <ButtonV2
                size="large"
                variant="outline"
                class="memory-home-action"
                onClick={() => props.onEnterWorkbench("recent")}
              >
                <span class="flex min-w-0 items-center gap-2">
                  <Icon name="status" size="small" />
                  <span class="truncate">{language.t("memory.tab.recent")}</span>
                </span>
                <Icon name="arrow-right" size="small" />
              </ButtonV2>
            </div>
          </div>

          <div class="flex justify-center px-2 text-12-regular text-v2-text-text-muted">
            <Show when={memory.status() === "ready"}>
              <span class="rounded-md bg-v2-background-bg-base/80 px-2 py-0.5 backdrop-blur-md">
                <Show when={!empty()} fallback={language.t("memory.landing.empty")}>
                  {language.t("memory.graph.summary", {
                    topics: stats().topics,
                    entities: stats().entities,
                    relations: stats().relations,
                  })}
                </Show>
              </span>
            </Show>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Used only for the first frame before the container exists; real colours follow immediately. */
function fallbackPalette() {
  return {
    surface: "#ffffff",
    label: "#161616",
    labelMuted: "#808080",
    edge: "#0000001a",
    edgeStrong: "#00000033",
    selection: "#034cff",
    swatches: new Map<string, string>(),
  }
}
