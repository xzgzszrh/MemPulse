import { createMemo, createSignal, For, Show } from "solid-js"
import { useDialog } from "@opencode-ai/ui/context/dialog"
import { Dialog, DialogBody, DialogFooter, DialogHeader, DialogTitleGroup } from "@opencode-ai/ui/v2/dialog-v2"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { TextInputV2 } from "@opencode-ai/ui/v2/text-input-v2"
import { useLanguage } from "@/context/language"
import { getRelativeTime } from "@/utils/time"
import { summarize } from "../format"
import type { Topic } from "../types"
import { useMemory } from "../store"
import { StateChip } from "./topic-row"

function TopicPicker(props: {
  topics: Topic[]
  selected: string | undefined
  onSelect: (id: string) => void
  empty: string
}) {
  return (
    <Show
      when={props.topics.length > 0}
      fallback={<p class="px-1 py-2 text-12-regular text-v2-text-text-faint">{props.empty}</p>}
    >
      <div class="flex max-h-64 flex-col overflow-y-auto rounded-[6px] border border-v2-border-border-base">
        <For each={props.topics}>
          {(topic) => (
            <button
              type="button"
              onClick={() => props.onSelect(topic.topic_id)}
              classList={{
                "flex items-center gap-2 border-b border-v2-border-border-muted px-2.5 py-2 text-left last:border-b-0": true,
                "bg-v2-background-bg-layer-02": props.selected === topic.topic_id,
                "hover:bg-v2-overlay-simple-overlay-hover": props.selected !== topic.topic_id,
              }}
            >
              <span class="min-w-0 flex-1 truncate text-12-regular text-v2-text-text-base">{topic.title}</span>
              <StateChip state={topic.state} />
            </button>
          )}
        </For>
      </div>
    </Show>
  )
}

/** Fold one topic into another; the source keeps a pointer to where it went. */
export function MergeDialog(props: { source: Topic }) {
  const memory = useMemory()
  const dialog = useDialog()
  const language = useLanguage()
  const [target, setTarget] = createSignal<string>()
  const [busy, setBusy] = createSignal(false)

  const candidates = createMemo(() => memory.byUpdated().filter((topic) => topic.topic_id !== props.source.topic_id))

  const run = async () => {
    const targetId = target()
    if (!targetId) return
    setBusy(true)
    await memory.mutate((client) => client.mergeTopics(props.source.topic_id, targetId))
    setBusy(false)
    dialog.close()
  }

  return (
    <Dialog size="large">
      <DialogHeader>
        <DialogTitleGroup
          title={language.t("memory.topics.merge.title")}
          description={language.t("memory.topics.merge.description", { title: props.source.title })}
        />
      </DialogHeader>
      <DialogBody class="flex flex-col gap-2">
        <TopicPicker
          topics={candidates()}
          selected={target()}
          onSelect={setTarget}
          empty={language.t("memory.topics.merge.empty")}
        />
      </DialogBody>
      <DialogFooter>
        <ButtonV2 variant="ghost" onClick={() => dialog.close()} disabled={busy()}>
          {language.t("memory.action.cancel")}
        </ButtonV2>
        <ButtonV2 variant="contrast" onClick={() => void run()} disabled={!target() || busy()}>
          {language.t("memory.topics.merge.confirm")}
        </ButtonV2>
      </DialogFooter>
    </Dialog>
  )
}

/** Move one event to another topic. */
export function MoveEventDialog(props: { eventId: string; content: string }) {
  const memory = useMemory()
  const dialog = useDialog()
  const language = useLanguage()
  const [target, setTarget] = createSignal<string>()
  const [busy, setBusy] = createSignal(false)

  const run = async () => {
    const targetId = target()
    if (!targetId) return
    setBusy(true)
    await memory.mutate((client) => client.moveEvent(props.eventId, targetId))
    setBusy(false)
    dialog.close()
  }

  return (
    <Dialog size="large">
      <DialogHeader>
        <DialogTitleGroup title={language.t("memory.events.move.title")} description={summarize(props.content, 160)} />
      </DialogHeader>
      <DialogBody class="flex flex-col gap-2">
        <TopicPicker
          topics={memory.byUpdated()}
          selected={target()}
          onSelect={setTarget}
          empty={language.t("memory.topics.empty")}
        />
      </DialogBody>
      <DialogFooter>
        <ButtonV2 variant="ghost" onClick={() => dialog.close()} disabled={busy()}>
          {language.t("memory.action.cancel")}
        </ButtonV2>
        <ButtonV2 variant="contrast" onClick={() => void run()} disabled={!target() || busy()}>
          {language.t("memory.events.move.confirm")}
        </ButtonV2>
      </DialogFooter>
    </Dialog>
  )
}

/**
 * Peel selected events out of a topic into a new one. The backend requires at
 * least one event and a non-empty title, so the confirm stays disabled until
 * both are present.
 */
export function SplitDialog(props: {
  topic: Topic
  events: { event_id: string; content: string; occurred_at: string }[]
}) {
  const memory = useMemory()
  const dialog = useDialog()
  const language = useLanguage()
  const [selected, setSelected] = createSignal<Set<string>>(new Set())
  const [title, setTitle] = createSignal("")
  const [busy, setBusy] = createSignal(false)

  const toggle = (id: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const run = async () => {
    if (!selected().size || !title().trim()) return
    setBusy(true)
    await memory.mutate((client) => client.splitTopic(props.topic.topic_id, [...selected()], title().trim()))
    setBusy(false)
    dialog.close()
  }

  return (
    <Dialog size="large">
      <DialogHeader>
        <DialogTitleGroup
          title={language.t("memory.topics.split.title")}
          description={language.t("memory.topics.split.description", { title: props.topic.title })}
        />
      </DialogHeader>
      <DialogBody class="flex flex-col gap-2">
        <TextInputV2
          value={title()}
          placeholder={language.t("memory.topics.split.namePlaceholder")}
          onInput={(event) => setTitle(event.currentTarget.value)}
        />
        <div class="flex max-h-64 flex-col overflow-y-auto rounded-[6px] border border-v2-border-border-base">
          <For each={props.events}>
            {(event) => (
              <label class="flex cursor-pointer items-start gap-2 border-b border-v2-border-border-muted px-2.5 py-2 last:border-b-0 hover:bg-v2-overlay-simple-overlay-hover">
                <input
                  type="checkbox"
                  class="mt-0.5"
                  checked={selected().has(event.event_id)}
                  onChange={() => toggle(event.event_id)}
                />
                <span class="flex min-w-0 flex-col gap-0.5">
                  <span class="text-12-regular text-v2-text-text-base">{summarize(event.content, 120)}</span>
                  <span class="text-12-regular text-v2-text-text-faint">
                    {getRelativeTime(event.occurred_at, language.t)}
                  </span>
                </span>
              </label>
            )}
          </For>
        </div>
      </DialogBody>
      <DialogFooter>
        <ButtonV2 variant="ghost" onClick={() => dialog.close()} disabled={busy()}>
          {language.t("memory.action.cancel")}
        </ButtonV2>
        <ButtonV2
          variant="contrast"
          onClick={() => void run()}
          disabled={!selected().size || !title().trim() || busy()}
        >
          {language.t("memory.topics.split.confirm", { count: selected().size })}
        </ButtonV2>
      </DialogFooter>
    </Dialog>
  )
}
