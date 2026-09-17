import { createMemo, For, Show } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { ProjectAvatar } from "@opencode-ai/ui/v2/project-avatar-v2"
import { useLanguage } from "@/context/language"
import { getProjectAvatarVariant, type LocalProject } from "@/context/layout"
import { displayName, getProjectAvatarSource } from "@/pages/layout/helpers"
import { getRelativeTime } from "@/utils/time"
import { formatCount, summarize } from "@/memory/format"
import { useMemory } from "@/memory/store"
import { stateLabelKey, stateTone } from "@/memory/labels"
import { EmptyState } from "../components/empty-state"
import { toneChip, toneDot } from "../components/tone"

/**
 * The "recent" section of the memory home: what has been happening lately, as
 * floating cards rather than a dense list. It replaces a conventional overview
 * table — the graph next door already carries the shape of the whole store, so
 * this column is about the user's own recent work.
 */

export function RecentSection(props: {
  projects: LocalProject[]
  onOpenProject?: (project: LocalProject) => void
  onOpenSection?: (section: "topics" | "events") => void
}) {
  const memory = useMemory()
  const language = useLanguage()

  const stats = createMemo(() => memory.stats())
  const topics = createMemo(() => memory.byUpdated().slice(0, 6))
  const events = createMemo(() => memory.byRecent().slice(0, 6))

  return (
    <div class="flex flex-col gap-6 pb-8">
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label={language.t("memory.stat.topics")} value={stats().topics} icon="bullet-list" />
        <StatCard label={language.t("memory.stat.events")} value={stats().events} icon="console" />
        <StatCard label={language.t("memory.stat.entities")} value={stats().entities} icon="dot-grid" />
        <StatCard
          label={language.t("memory.stat.incomplete")}
          value={stats().incomplete}
          icon="warning"
          tone={stats().incomplete > 0 ? "warning" : "neutral"}
        />
      </div>

      <Show when={props.projects.length > 0}>
        <div class="flex flex-col gap-2">
          <h3 class="text-12-medium text-v2-text-text-muted">{language.t("memory.recent.projects")}</h3>
          <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <For each={props.projects.slice(0, 4)}>
              {(project) => (
                <button
                  type="button"
                  onClick={() => props.onOpenProject?.(project)}
                  class="flex items-center gap-3 rounded-[10px] border border-v2-border-border-base bg-v2-background-bg-base px-3 py-2.5 text-left shadow-[var(--v2-elevation-raised)] transition-shadow hover:shadow-[var(--v2-elevation-floating)]"
                >
                  <ProjectAvatar
                    fallback={displayName(project)}
                    src={getProjectAvatarSource(project.id, project.icon)}
                    variant={getProjectAvatarVariant(project.icon?.color)}
                  />
                  <div class="flex min-w-0 flex-1 flex-col">
                    <span class="truncate text-12-medium text-v2-text-text-base">{displayName(project)}</span>
                    <span class="truncate text-12-regular text-v2-text-text-faint">{project.worktree}</span>
                  </div>
                  <Icon name="chevron-right" size="small" class="text-v2-icon-icon-muted" />
                </button>
              )}
            </For>
          </div>
        </div>
      </Show>

      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-2">
          <h3 class="text-12-medium text-v2-text-text-muted">{language.t("memory.recent.topics")}</h3>
          <ButtonV2 size="small" variant="ghost" onClick={() => props.onOpenSection?.("topics")}>
            {language.t("memory.action.viewAll")}
          </ButtonV2>
        </div>
        <Show
          when={topics().length > 0}
          fallback={<EmptyState icon="bullet-list" title={language.t("memory.topics.empty")} compact />}
        >
          <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <For each={topics()}>
              {(topic) => (
                <button
                  type="button"
                  onClick={() => props.onOpenSection?.("topics")}
                  class="flex flex-col gap-2 rounded-[10px] border border-v2-border-border-base bg-v2-background-bg-base px-3 py-3 text-left shadow-[var(--v2-elevation-raised)] transition-shadow hover:shadow-[var(--v2-elevation-floating)]"
                >
                  <div class="flex w-full items-center gap-2">
                    <span class="min-w-0 flex-1 truncate text-12-medium text-v2-text-text-base">{topic.title}</span>
                    <span
                      class={`inline-flex h-5 shrink-0 items-center rounded-[4px] border px-1.5 text-12-regular ${toneChip[stateTone(topic.state)]}`}
                    >
                      {language.t(stateLabelKey(topic.state))}
                    </span>
                  </div>
                  <Show when={topic.summary || topic.goal}>
                    <span class="line-clamp-2 text-12-regular text-v2-text-text-muted">
                      {summarize(topic.summary || topic.goal, 140)}
                    </span>
                  </Show>
                  <div class="flex w-full items-center gap-3 text-12-regular text-v2-text-text-faint">
                    <span>{language.t("memory.topics.eventCount", { count: topic.event_ids?.length ?? 0 })}</span>
                    <Show when={topic.updated_at}>
                      <span>{getRelativeTime(topic.updated_at!, language.t)}</span>
                    </Show>
                  </div>
                </button>
              )}
            </For>
          </div>
        </Show>
      </div>

      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-2">
          <h3 class="text-12-medium text-v2-text-text-muted">{language.t("memory.recent.events")}</h3>
          <ButtonV2 size="small" variant="ghost" onClick={() => props.onOpenSection?.("events")}>
            {language.t("memory.action.viewAll")}
          </ButtonV2>
        </div>
        <Show
          when={events().length > 0}
          fallback={<EmptyState icon="console" title={language.t("memory.events.empty")} compact />}
        >
          <div class="flex flex-col gap-2">
            <For each={events()}>
              {(event) => (
                <button
                  type="button"
                  onClick={() => props.onOpenSection?.("events")}
                  class="flex flex-col gap-1 rounded-[10px] border border-v2-border-border-base bg-v2-background-bg-base px-3 py-2.5 text-left shadow-[var(--v2-elevation-raised)] transition-shadow hover:shadow-[var(--v2-elevation-floating)]"
                >
                  <span class="line-clamp-2 text-12-regular text-v2-text-text-base">
                    {summarize(event.content, 160)}
                  </span>
                  <div class="flex items-center gap-3 text-12-regular text-v2-text-text-faint">
                    <span class="truncate">{event.topic_title}</span>
                    <Show when={event.occurred_at}>
                      <span class="ml-auto shrink-0">{getRelativeTime(event.occurred_at, language.t)}</span>
                    </Show>
                  </div>
                </button>
              )}
            </For>
          </div>
        </Show>
      </div>
    </div>
  )
}

function StatCard(props: {
  label: string
  value: number
  icon: Parameters<typeof Icon>[0]["name"]
  tone?: "neutral" | "warning"
}) {
  return (
    <div class="flex flex-col gap-1.5 rounded-[10px] border border-v2-border-border-base bg-v2-background-bg-base px-3 py-3 shadow-[var(--v2-elevation-raised)]">
      <div class="flex items-center gap-1.5">
        <Icon
          name={props.icon}
          size="small"
          class={props.tone === "warning" ? "text-v2-state-fg-warning" : "text-v2-icon-icon-muted"}
        />
        <span class="text-12-regular text-v2-text-text-faint">{props.label}</span>
        <Show when={props.tone === "warning" && props.value > 0}>
          <span class={`ml-auto size-1.5 rounded-full ${toneDot.warning}`} />
        </Show>
      </div>
      <span class="text-20-medium text-v2-text-text-base [font-variant-numeric:tabular-nums]">
        {formatCount(props.value)}
      </span>
    </div>
  )
}
