import { createMemo, createResource, createSignal, For, Show } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { IconButtonV2 } from "@opencode-ai/ui/v2/icon-button-v2"
import { TextInputV2 } from "@opencode-ai/ui/v2/text-input-v2"
import { TooltipV2 } from "@opencode-ai/ui/v2/tooltip-v2"
import { useDialog } from "@opencode-ai/ui/context/dialog"
import { useLanguage } from "@/context/language"
import { formatDateTime } from "@/memory/format"
import { eventStatusLabelKey, eventStatusTone, sourceIcon, sourceLabelKey } from "@/memory/labels"
import { useMemory } from "@/memory/store"
import type { MemoryEvent } from "@/memory/types"
import { Card, Section } from "../components/section"
import { EmptyState } from "../components/empty-state"
import { EventRow } from "../components/event-row"
import { ConfirmDialog } from "../components/confirm-dialog"
import { FilterChip } from "../components/filter-chip"
import { MoveEventDialog } from "../components/topic-dialogs"
import { toneText } from "../components/tone"

const PAGE_SIZE = 40

const SOURCE_FILTERS = [
  { value: "conversation", label: "memory.source.conversation" },
  { value: "tool", label: "memory.source.tool" },
  { value: "configuration", label: "memory.source.configuration" },
] as const

const STATUS_FILTERS = [
  { value: "success", label: "memory.eventStatus.success" },
  { value: "failed", label: "memory.eventStatus.failed" },
  { value: "pending", label: "memory.eventStatus.pending" },
] as const

export function EventsView() {
  const memory = useMemory()
  const language = useLanguage()
  const dialog = useDialog()

  const [query, setQuery] = createSignal("")
  const [source, setSource] = createSignal<string | undefined>()
  const [status, setStatus] = createSignal<string | undefined>()
  const [selectedId, setSelectedId] = createSignal<string>()
  const [page, setPage] = createSignal(0)

  /** Searching the backend reaches events beyond the bootstrap window. */
  const [remote] = createResource(
    () => (query().trim().length > 1 ? query().trim() : undefined),
    (value) => memory.client.search(value, 50).catch(() => undefined),
  )

  const base = createMemo<MemoryEvent[]>(() => {
    const hits = remote()
    if (hits && query().trim().length > 1) {
      // Remote hits carry less detail; keep only ids we can resolve locally,
      // and fall back to the hit itself so search still works on long histories.
      return hits.results
        .map((hit) => memory.byRecent().find((event) => event.event_id === hit.event_id) ?? undefined)
        .filter((event): event is MemoryEvent => Boolean(event))
    }
    return memory.byRecent()
  })

  const filtered = createMemo(() =>
    base().filter((event) => {
      if (source() && event.source_type !== source()) return false
      if (status() && event.status !== status()) return false
      return true
    }),
  )

  const pageCount = createMemo(() => Math.max(1, Math.ceil(filtered().length / PAGE_SIZE)))
  const paged = createMemo(() => filtered().slice(page() * PAGE_SIZE, page() * PAGE_SIZE + PAGE_SIZE))
  const selected = createMemo(() => filtered().find((event) => event.event_id === selectedId()) ?? paged()[0])

  const remoteHits = createMemo(() => {
    const hits = remote()
    if (!hits || query().trim().length <= 1) return []
    const local = new Set(memory.byRecent().map((event) => event.event_id))
    return hits.results.filter((hit) => !local.has(hit.event_id))
  })

  const forget = (event: MemoryEvent) => {
    void dialog.show(() => (
      <ConfirmDialog
        title={language.t("memory.events.forget.title")}
        description={language.t("memory.events.forget.description")}
        confirmLabel={language.t("memory.events.forget.confirm")}
        variant="danger"
        onConfirm={async () => {
          await memory.mutate((client) => client.forgetEvent(event.event_id))
        }}
      />
    ))
  }

  return (
    <div class="flex h-full min-h-0">
      <div class="flex w-96 shrink-0 flex-col gap-2 border-r border-v2-border-border-base p-3">
        <TextInputV2
          value={query()}
          placeholder={language.t("memory.search.placeholder")}
          onInput={(event) => {
            setQuery(event.currentTarget.value)
            setPage(0)
          }}
          leadingIcon={<Icon name="magnifying-glass" size="small" />}
          showClearButton={Boolean(query())}
          onClearClick={() => setQuery("")}
        />

        <div class="flex flex-wrap items-center gap-1">
          <For each={SOURCE_FILTERS}>
            {(item) => (
              <FilterChip
                active={source() === item.value}
                onClick={() => {
                  setSource(source() === item.value ? undefined : item.value)
                  setPage(0)
                }}
                label={language.t(item.label)}
                icon={sourceIcon(item.value)}
              />
            )}
          </For>
          <For each={STATUS_FILTERS}>
            {(item) => (
              <FilterChip
                active={status() === item.value}
                onClick={() => {
                  setStatus(status() === item.value ? undefined : item.value)
                  setPage(0)
                }}
                label={language.t(item.label)}
              />
            )}
          </For>
        </div>

        <div class="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
          <Show
            when={paged().length > 0}
            fallback={<EmptyState icon="console" title={language.t("memory.events.empty")} compact />}
          >
            <For each={paged()}>
              {(event) => (
                <EventRow
                  event={event}
                  selected={selected()?.event_id === event.event_id}
                  onSelect={() => setSelectedId(event.event_id)}
                  showTopic
                />
              )}
            </For>
          </Show>

          <Show when={remoteHits().length > 0}>
            <Section
              title={language.t("memory.events.olderHits")}
              count={remoteHits().length}
              class="mt-2 flex flex-col gap-1"
            >
              <For each={remoteHits()}>
                {(hit) => (
                  <div class="rounded-[6px] border border-v2-border-border-base bg-v2-background-bg-layer-01 px-2 py-1.5">
                    <span class="line-clamp-2 text-12-regular text-v2-text-text-muted">{hit.content}</span>
                    <span class="text-12-regular text-v2-text-text-faint">{hit.topic_title}</span>
                  </div>
                )}
              </For>
            </Section>
          </Show>
        </div>

        <Show when={pageCount() > 1}>
          <div class="flex items-center gap-2">
            <ButtonV2
              size="small"
              variant="ghost"
              disabled={page() === 0}
              onClick={() => setPage((current) => Math.max(0, current - 1))}
            >
              {language.t("memory.action.previous")}
            </ButtonV2>
            <span class="text-12-regular text-v2-text-text-faint [font-variant-numeric:tabular-nums]">
              {page() + 1} / {pageCount()}
            </span>
            <ButtonV2
              size="small"
              variant="ghost"
              disabled={page() >= pageCount() - 1}
              onClick={() => setPage((current) => Math.min(pageCount() - 1, current + 1))}
            >
              {language.t("memory.action.next")}
            </ButtonV2>
          </div>
        </Show>
      </div>

      <div class="flex min-h-0 min-w-0 flex-1 flex-col">
        <Show when={selected()} fallback={<EmptyState icon="console" title={language.t("memory.events.empty")} />}>
          {(event) => (
            <>
              <header class="flex shrink-0 items-center gap-2 border-b border-v2-border-border-base px-4 py-3">
                <Icon name={sourceIcon(event().source_type)} size="small" class="text-v2-icon-icon-muted" />
                <span class={toneText[eventStatusTone(event().status)]}>
                  {language.t(eventStatusLabelKey(event().status))}
                </span>
                <span class="text-12-regular text-v2-text-text-faint">{formatDateTime(event().occurred_at)}</span>
                <div class="ml-auto flex items-center gap-1">
                  <TooltipV2 value={language.t("memory.events.move.action")}>
                    <IconButtonV2
                      size="small"
                      variant="ghost"
                      aria-label={language.t("memory.events.move.action")}
                      onClick={() =>
                        void dialog.show(() => <MoveEventDialog eventId={event().event_id} content={event().content} />)
                      }
                      icon={<Icon name="arrow-right" size="small" />}
                    />
                  </TooltipV2>
                  <TooltipV2 value={language.t("memory.events.forget.action")}>
                    <IconButtonV2
                      size="small"
                      variant="ghost"
                      aria-label={language.t("memory.events.forget.action")}
                      onClick={() => forget(event())}
                      icon={<Icon name="trash" size="small" />}
                    />
                  </TooltipV2>
                </div>
              </header>

              <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-3">
                <Section title={language.t("memory.events.content")}>
                  <Card>
                    <p class="whitespace-pre-wrap text-12-regular text-v2-text-text-base">{event().content}</p>
                  </Card>
                </Section>

                <Section title={language.t("memory.events.attributes")}>
                  <Card>
                    <dl class="grid grid-cols-2 gap-x-4 gap-y-2">
                      <Attribute label={language.t("memory.events.topic")} value={event().topic_title} />
                      <Attribute
                        label={language.t("memory.events.source")}
                        value={language.t(sourceLabelKey(event().source_type))}
                      />
                      <Attribute label={language.t("memory.events.eventId")} value={event().event_id} mono />
                      <Show when={event().tool}>
                        <Attribute label={language.t("memory.events.tool")} value={event().tool} />
                      </Show>
                      <Show when={event().app}>
                        <Attribute label={language.t("memory.events.app")} value={event().app} />
                      </Show>
                    </dl>
                  </Card>
                </Section>

                <Show when={event().metadata && Object.keys(event().metadata!).length > 0}>
                  <Section title={language.t("memory.events.metadata")}>
                    <Card class="border-v2-border-border-base bg-v2-background-bg-layer-01 p-0">
                      <div class="flex flex-col">
                        <For each={Object.entries(event().metadata ?? {})}>
                          {([key, value]) => (
                            <div class="flex items-start gap-2 border-b border-v2-border-border-muted px-3 py-1.5 last:border-b-0">
                              <span class="w-[10rem] shrink-0 truncate text-12-mono text-v2-text-text-faint">
                                {key}
                              </span>
                              <span class="min-w-0 flex-1 truncate text-12-mono text-v2-text-text-muted">
                                {typeof value === "string" ? value : JSON.stringify(value)}
                              </span>
                            </div>
                          )}
                        </For>
                      </div>
                    </Card>
                  </Section>
                </Show>
              </div>
            </>
          )}
        </Show>
      </div>
    </div>
  )
}

function Attribute(props: { label: string; value: string | undefined; mono?: boolean }) {
  return (
    <div class="flex min-w-0 flex-col gap-0.5">
      <dt class="text-12-regular text-v2-text-text-faint">{props.label}</dt>
      <dd
        classList={{
          "truncate text-12-mono text-v2-text-text-base": Boolean(props.mono),
          "truncate text-12-regular text-v2-text-text-base": !props.mono,
        }}
      >
        {props.value ?? "—"}
      </dd>
    </div>
  )
}
