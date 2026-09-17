import { createMemo, createResource, createSignal, For, Show } from "solid-js"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { CreateTopicDialog } from "../components/operation-dialog"
import { Icon } from "@opencode-ai/ui/icon"
import { IconButtonV2 } from "@opencode-ai/ui/v2/icon-button-v2"
import { TextInputV2 } from "@opencode-ai/ui/v2/text-input-v2"
import { MenuV2 } from "@opencode-ai/ui/v2/menu-v2"
import { TooltipV2 } from "@opencode-ai/ui/v2/tooltip-v2"
import { useDialog } from "@opencode-ai/ui/context/dialog"
import { useLanguage } from "@/context/language"
import { formatDateTime } from "@/memory/format"
import { useMemory } from "@/memory/store"
import { Card, Section } from "../components/section"
import { ContractList } from "../components/contract-list"
import { EmptyState } from "../components/empty-state"
import { EventRow } from "../components/event-row"
import { StateChip, TopicRow } from "../components/topic-row"
import { TagList } from "../components/tag-chip"
import { ConfirmDialog } from "../components/confirm-dialog"
import { FilterChip } from "../components/filter-chip"
import { MergeDialog, SplitDialog } from "../components/topic-dialogs"
import "./topics.css"

const STATE_FILTERS = [
  { value: "active", label: "memory.state.active" },
  { value: "incomplete", label: "memory.state.incomplete" },
  { value: "archived", label: "memory.state.archived" },
] as const

export function TopicsView(props: { initialTopicId?: string; directory?: string } = {}) {
  const memory = useMemory()
  const language = useLanguage()
  const dialog = useDialog()

  const [query, setQuery] = createSignal("")
  const [state, setState] = createSignal<string | undefined>()
  const [selectedId, setSelectedId] = createSignal<string | undefined>(props.initialTopicId)

  const filtered = createMemo(() => {
    const needle = query().trim().toLowerCase()
    return memory.byUpdated().filter((topic) => {
      if (state() && topic.state !== state()) return false
      if (!needle) return true
      return (
        topic.title.toLowerCase().includes(needle) ||
        (topic.summary ?? "").toLowerCase().includes(needle) ||
        topic.tags.some((tag) => tag.value.toLowerCase().includes(needle))
      )
    })
  })

  // Fall back to the first row so the detail pane is never empty when the list
  // has content; a stale id (after a merge) resolves to undefined and also falls back.
  const selected = createMemo(() => memory.topic(selectedId()) ?? filtered()[0])

  const [pack, { refetch }] = createResource(
    () => selected()?.topic_id,
    (topicId) => memory.client.restore(topicId).catch(() => undefined),
  )

  const topicEvents = createMemo(() => {
    const id = selected()?.topic_id
    if (!id) return []
    if (pack()?.topic_id === id)
      return (pack()?.events ?? []).map((event) => ({ ...event, topic_id: id, topic_title: selected()?.title ?? "" }))
    return memory.eventsByTopic().get(id) ?? []
  })

  const checkpoint = createMemo(() =>
    memory
      .governance()
      .checkpoints.filter((row) => row.topic_id === selected()?.topic_id)
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .at(0),
  )

  const relatedEntities = createMemo(() => {
    const id = selected()?.topic_id
    if (!id) return []
    const ids = memory
      .graph()
      .edges.filter((edge) => edge.source === id)
      .map((edge) => edge.target)
    return memory.graph().nodes.filter((node) => ids.includes(node.id))
  })

  const runCheckpoint = async () => {
    const topic = selected()
    if (!topic) return
    void dialog.show(() => (
      <ConfirmDialog
        title={language.t("memory.operation.kind.checkpoint")}
        description={topic.title}
        confirmLabel={language.t("memory.action.confirm")}
        onConfirm={async () => {
          await memory.client.checkpoint(topic.topic_id)
          await memory.refresh()
          await refetch()
        }}
      />
    ))
  }

  const confirmForget = () => {
    const topic = selected()
    if (!topic) return
    void dialog.show(() => (
      <ConfirmDialog
        title={language.t("memory.topics.forget.title")}
        description={language.t("memory.topics.forget.description", { title: topic.title })}
        confirmLabel={language.t("memory.topics.forget.confirm")}
        variant="danger"
        onConfirm={async () => {
          await memory.mutate((client) => client.forgetTopic(topic.topic_id))
        }}
      />
    ))
  }

  return (
    <div class="memory-topics h-full min-h-0 min-w-0">
      <div class="memory-topics-layout flex h-full min-h-0 min-w-0">
      <div class="memory-topics-list flex min-h-0 min-w-0 shrink-0 flex-col gap-2 border-r border-v2-border-border-base p-3">
        <ButtonV2
          size="small"
          variant="neutral"
          onClick={() => void dialog.show(() => <CreateTopicDialog directory={props.directory} />)}
        >
          {language.t("memory.operation.kind.create_topic")}
        </ButtonV2>
        <TextInputV2
          value={query()}
          placeholder={language.t("memory.topics.searchPlaceholder")}
          onInput={(event) => setQuery(event.currentTarget.value)}
          leadingIcon={<Icon name="magnifying-glass" size="small" />}
          showClearButton={Boolean(query())}
          onClearClick={() => setQuery("")}
        />
        <div class="flex flex-wrap items-center gap-1">
          <FilterChip active={!state()} onClick={() => setState(undefined)} label={language.t("memory.filter.all")} />
          <For each={STATE_FILTERS}>
            {(item) => (
              <FilterChip
                active={state() === item.value}
                onClick={() => setState(state() === item.value ? undefined : item.value)}
                label={language.t(item.label)}
              />
            )}
          </For>
        </div>
        <div class="flex min-h-0 min-w-0 flex-1 flex-col gap-1.5 overflow-x-hidden overflow-y-auto">
          <Show
            when={filtered().length > 0}
            fallback={<EmptyState icon="bullet-list" title={language.t("memory.topics.empty")} compact />}
          >
            <For each={filtered()}>
              {(topic) => (
                <TopicRow
                  topic={topic}
                  selected={selected()?.topic_id === topic.topic_id}
                  onSelect={() => setSelectedId(topic.topic_id)}
                />
              )}
            </For>
          </Show>
        </div>
      </div>

      <div class="memory-topics-detail flex min-h-0 min-w-0 flex-1 flex-col">
        <Show when={selected()} fallback={<EmptyState icon="bullet-list" title={language.t("memory.topics.empty")} />}>
          {(topic) => (
            <>
              <header class="flex shrink-0 items-start gap-2 border-b border-v2-border-border-base px-4 py-3">
                <div class="flex min-w-0 flex-1 flex-col gap-1">
                  <div class="flex min-w-0 items-center gap-2">
                    <h2 class="min-w-0 truncate text-14-medium text-v2-text-text-base">{topic().title}</h2>
                    <StateChip state={topic().state} />
                  </div>
                  <span class="text-12-regular text-v2-text-text-faint">
                    {language.t("memory.topics.updatedAt", { time: formatDateTime(topic().updated_at) })}
                  </span>
                </div>
                <div class="flex shrink-0 items-center gap-1">
                  <TooltipV2 value={language.t("memory.session.checkpoint.create")}>
                    <IconButtonV2
                      size="small"
                      variant="ghost"
                      aria-label={language.t("memory.session.checkpoint.create")}
                      onClick={() => void runCheckpoint()}
                      icon={<Icon name="checklist" size="small" />}
                    />
                  </TooltipV2>
                  <MenuV2 gutter={4} modal={false} placement="bottom-end">
                    <MenuV2.Trigger
                      as={IconButtonV2}
                      variant="ghost"
                      size="small"
                      icon={<Icon name="menu" size="small" />}
                      aria-label={language.t("memory.action.more")}
                    />
                    <MenuV2.Portal>
                      <MenuV2.Content>
                        <MenuV2.Item onSelect={() => void dialog.show(() => <MergeDialog source={topic()} />)}>
                          {language.t("memory.topics.merge.action")}
                        </MenuV2.Item>
                        <MenuV2.Item
                          onSelect={() =>
                            void dialog.show(() => <SplitDialog topic={topic()} events={topicEvents()} />)
                          }
                        >
                          {language.t("memory.topics.split.action")}
                        </MenuV2.Item>
                        <MenuV2.Separator />
                        <MenuV2.Item onSelect={confirmForget}>{language.t("memory.topics.forget.action")}</MenuV2.Item>
                      </MenuV2.Content>
                    </MenuV2.Portal>
                  </MenuV2>
                </div>
              </header>

              <div class="memory-topics-body flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-x-hidden overflow-y-auto px-4 py-3">
                <Section title={language.t("memory.topics.goal")}>
                  <Card>
                    <p class="text-12-regular text-v2-text-text-base">
                      {topic().goal || language.t("memory.topics.goal.empty")}
                    </p>
                  </Card>
                </Section>

                <Show when={topic().summary && topic().summary?.trim() !== topic().goal?.trim()}>
                  <Section title={language.t("memory.topics.summary")}>
                    <Card>
                      <p class="text-12-regular text-v2-text-text-muted">{topic().summary}</p>
                    </Card>
                  </Section>
                </Show>

                <Section title={language.t("memory.topics.tags")} count={topic().tags.length}>
                  <Show
                    when={topic().tags.length > 0}
                    fallback={
                      <p class="px-1 text-12-regular text-v2-text-text-faint">
                        {language.t("memory.topics.tags.empty")}
                      </p>
                    }
                  >
                    <Card>
                      <TagList tags={topic().tags} />
                    </Card>
                  </Show>
                </Section>

                <Show when={relatedEntities().length > 0}>
                  <Section title={language.t("memory.topics.entities")} count={relatedEntities().length}>
                    <Card>
                      <div class="flex flex-wrap gap-1">
                        <For each={relatedEntities()}>
                          {(node) => (
                            <span title={node.label} class="inline-flex h-5 max-w-full items-center truncate rounded-[4px] border border-v2-border-border-base bg-v2-background-bg-layer-02 px-1.5 text-12-regular text-v2-text-text-muted">
                              {node.label}
                            </span>
                          )}
                        </For>
                      </div>
                    </Card>
                  </Section>
                </Show>

                <Section title={language.t("memory.contract.title")} count={pack()?.fields?.length}>
                  <Card class="border-v2-border-border-base bg-v2-background-bg-layer-01 p-0">
                    <ContractList fields={pack()?.fields} />
                  </Card>
                </Section>

                <Show when={checkpoint()}>
                  {(row) => (
                    <Section title={language.t("memory.session.checkpoint.title")}>
                      <Card>
                        <div class="flex items-center gap-3 text-12-regular text-v2-text-text-muted">
                          <span>{formatDateTime(row().created_at)}</span>
                          <span class="text-v2-text-text-faint">
                            {language.t("memory.session.checkpoint.revision", { revision: row().revision ?? 0 })}
                          </span>
                        </div>
                      </Card>
                    </Section>
                  )}
                </Show>

                <Section
                  title={language.t("memory.topics.timeline")}
                  count={topicEvents().length}
                  bodyClass="flex flex-col rounded-[6px] border border-v2-border-border-base bg-v2-background-bg-layer-01 py-1"
                >
                  <Show
                    when={topicEvents().length > 0}
                    fallback={
                      <p class="px-2 py-3 text-12-regular text-v2-text-text-faint">
                        {language.t("memory.events.empty")}
                      </p>
                    }
                  >
                    <For each={topicEvents().slice(0, 30)}>{(event) => <EventRow event={event} />}</For>
                  </Show>
                </Section>
              </div>
            </>
          )}
        </Show>
      </div>
      </div>
    </div>
  )
}
