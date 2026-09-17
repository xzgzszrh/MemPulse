import { createMemo, createResource, createSignal, For, Show } from "solid-js"
import { useNavigate, useParams } from "@solidjs/router"
import { Icon } from "@opencode-ai/ui/icon"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { IconButtonV2 } from "@opencode-ai/ui/v2/icon-button-v2"
import { TextInputV2 } from "@opencode-ai/ui/v2/text-input-v2"
import { TooltipV2 } from "@opencode-ai/ui/v2/tooltip-v2"
import { useDialog } from "@opencode-ai/ui/context/dialog"
import { ConfirmDialog } from "../components/confirm-dialog"
import { CreateTopicDialog, BindTopicDialog } from "../components/operation-dialog"
import { useLanguage } from "@/context/language"
import { useSDK } from "@/context/sdk"
import { Card, Section } from "../components/section"
import { ContractList } from "../components/contract-list"
import { EmptyState, MemoryGate } from "../components/empty-state"
import { EventRow } from "../components/event-row"
import { StateChip } from "../components/topic-row"
import { formatDateTime } from "../format"
import type { SearchHit } from "../types"
import { useMemorySurface } from "../store"

/**
 * The memory side of a session.
 *
 * Everything here is derived from what the capture bridge already recorded, so
 * the panel answers three questions at a glance: which topic this session is
 * feeding, what the agent will be handed when it resumes, and what has been
 * captured so far.
 */
export function SessionMemoryTab() {
  const memory = useMemorySurface()
  const language = useLanguage()
  const dialog = useDialog()
  const sdk = useSDK()
  const params = useParams<{ id?: string }>()
  const navigate = useNavigate()

  const [query, setQuery] = createSignal("")
  const [busy, setBusy] = createSignal(false)

  const directory = createMemo(() => sdk().directory)
  const sessionId = createMemo(() => params.id)

  const topic = createMemo(() => memory.topicForSession(sessionId(), directory()))
  const sessionEvents = createMemo(() => memory.eventsForSession(sessionId(), directory()))

  const [pack, { refetch: refetchPack }] = createResource(
    () => topic()?.topic_id,
    (topicId) => memory.client.restore(topicId).catch(() => undefined),
  )

  const [results] = createResource(
    () => (query().trim().length > 1 ? query().trim() : undefined),
    (value) => memory.client.search(value, 20).catch(() => undefined),
  )

  const createCheckpoint = async () => {
    const target = topic()
    if (!target) return
    void dialog.show(() => (
      <ConfirmDialog
        title={language.t("memory.operation.kind.checkpoint")}
        description={target.title}
        confirmLabel={language.t("memory.action.confirm")}
        onConfirm={async () => {
          setBusy(true)
          try {
            await memory.client.checkpoint(target.topic_id)
            await memory.refresh()
            await refetchPack()
          } finally {
            setBusy(false)
          }
        }}
      />
    ))
  }

  return (
    <div class="flex h-full min-h-0 flex-col">
      <div class="flex items-center gap-2 border-b border-v2-border-border-base px-3 py-2">
        <Icon name="brain" size="small" class="text-v2-icon-icon-muted" />
        <span class="text-12-medium text-v2-text-text-base">{language.t("session.tab.memory")}</span>
        <div class="ml-auto flex items-center gap-1">
          <TooltipV2 value={language.t("memory.action.openWorkbench")}>
            <IconButtonV2
              size="small"
              variant="ghost"
              aria-label={language.t("memory.action.openWorkbench")}
              onClick={() => navigate("/")}
              icon={<Icon name="square-arrow-top-right" size="small" />}
            />
          </TooltipV2>
          <TooltipV2 value={language.t("memory.action.refresh")}>
            <IconButtonV2
              size="small"
              variant="ghost"
              aria-label={language.t("memory.action.refresh")}
              onClick={() => {
                void memory.refresh()
                void refetchPack()
              }}
              icon={<Icon name="reset" size="small" />}
            />
          </TooltipV2>
        </div>
      </div>

      <MemoryGate status={memory.status()} error={memory.error()} onRetry={() => void memory.refresh()}>
        <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-3 py-3">
          <div class="flex flex-wrap gap-2">
            <ButtonV2
              variant="ghost"
              onClick={() =>
                void dialog.show(() => <CreateTopicDialog sessionId={sessionId()} directory={directory()} />)
              }
            >
              {language.t("memory.operation.kind.create_topic")}
            </ButtonV2>
            <ButtonV2
              variant="ghost"
              disabled={!sessionId()}
              onClick={() =>
                void dialog.show(() => (
                  <BindTopicDialog sessionId={sessionId()!} directory={directory()} topics={memory.topics()} />
                ))
              }
            >
              {language.t("memory.operation.kind.bind_topic")}
            </ButtonV2>
          </div>
          <Show
            when={topic()}
            fallback={
              <EmptyState
                icon="brain"
                title={language.t("memory.session.noTopic.title")}
                description={language.t("memory.session.noTopic.description")}
                compact
              />
            }
          >
            {(current) => (
              <div class="flex flex-col gap-4">
                <div class="flex flex-col gap-2 rounded-[6px] border border-v2-border-border-base bg-v2-background-bg-layer-01 px-3 py-2.5">
                  <div class="flex items-center gap-2">
                    <span class="min-w-0 flex-1 truncate text-12-medium text-v2-text-text-base">{current().title}</span>
                    <StateChip state={current().state} />
                  </div>
                  <div class="flex items-center gap-3 text-12-regular text-v2-text-text-faint">
                    <span>{language.t("memory.topics.eventCount", { count: current().event_ids?.length ?? 0 })}</span>
                    <Show when={current().updated_at}>
                      <span>{formatDateTime(current().updated_at)}</span>
                    </Show>
                  </div>
                </div>

                <Section
                  title={language.t("memory.contract.title")}
                  count={pack()?.fields?.length}
                  action={
                    <TooltipV2 value={language.t("memory.session.checkpoint.create")}>
                      <IconButtonV2
                        size="small"
                        variant="ghost"
                        disabled={busy()}
                        aria-label={language.t("memory.session.checkpoint.create")}
                        onClick={() => void createCheckpoint()}
                        icon={<Icon name="checklist" size="small" />}
                      />
                    </TooltipV2>
                  }
                >
                  <Card class="border-v2-border-border-base bg-v2-background-bg-layer-01 p-0">
                    <ContractList fields={pack()?.fields} />
                  </Card>
                </Section>

                <Show when={pack()?.checkpoint?.found}>
                  <Section title={language.t("memory.session.checkpoint.title")}>
                    <Card>
                      <div class="flex flex-col gap-1">
                        <span class="text-12-regular text-v2-text-text-muted">
                          {formatDateTime(pack()?.checkpoint?.created_at)}
                        </span>
                        <span class="text-12-regular text-v2-text-text-faint">
                          {language.t("memory.session.checkpoint.revision", {
                            revision: pack()?.checkpoint?.revision ?? 0,
                          })}
                        </span>
                      </div>
                    </Card>
                  </Section>
                </Show>
              </div>
            )}
          </Show>

          <Section
            title={language.t("memory.session.captured")}
            count={sessionEvents().length}
            bodyClass="flex flex-col rounded-[6px] border border-v2-border-border-base bg-v2-background-bg-layer-01 py-1"
          >
            <Show
              when={sessionEvents().length > 0}
              fallback={
                <p class="px-2 py-3 text-12-regular text-v2-text-text-faint">
                  {language.t("memory.session.captured.empty")}
                </p>
              }
            >
              <For each={sessionEvents().slice(0, 40)}>{(event) => <EventRow event={event} dense />}</For>
            </Show>
          </Section>

          <Section title={language.t("memory.action.search")} bodyClass="flex flex-col gap-2">
            <TextInputV2
              value={query()}
              placeholder={language.t("memory.search.placeholder")}
              onInput={(event) => setQuery(event.currentTarget.value)}
              leadingIcon={<Icon name="magnifying-glass" size="small" />}
              showClearButton={Boolean(query())}
              onClearClick={() => setQuery("")}
            />
            <Show when={results()}>
              {(hits) => (
                <Card class="flex flex-col border-v2-border-border-base bg-v2-background-bg-layer-01 p-0">
                  <Show
                    when={hits().results.length > 0}
                    fallback={
                      <p class="px-2 py-2 text-12-regular text-v2-text-text-faint">
                        {language.t("memory.search.empty")}
                      </p>
                    }
                  >
                    <For each={hits().results.slice(0, 8)}>
                      {(hit: SearchHit) => (
                        <button
                          type="button"
                          class="border-b border-v2-border-border-muted px-2 py-1.5 text-left last:border-b-0 hover:bg-v2-overlay-simple-overlay-hover"
                          onClick={() => navigate("/")}
                        >
                          <span class="line-clamp-2 text-12-regular text-v2-text-text-base">{hit.content}</span>
                          <span class="text-12-regular text-v2-text-text-faint">{hit.topic_title}</span>
                        </button>
                      )}
                    </For>
                  </Show>
                </Card>
              )}
            </Show>
          </Section>

          <ButtonV2 variant="outline" size="small" onClick={() => navigate("/")}>
            <Icon name="arrow-right" size="small" />
            {language.t("memory.action.openWorkbench")}
          </ButtonV2>
        </div>
      </MemoryGate>
    </div>
  )
}
