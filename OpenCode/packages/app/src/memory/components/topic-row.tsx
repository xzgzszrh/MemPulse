import { Show, type JSX } from "solid-js"
import { useLanguage } from "@/context/language"
import { getRelativeTime } from "@/utils/time"
import { stateLabelKey, stateTone } from "../labels"
import { summarize } from "../format"
import type { Topic } from "../types"
import { toneChip } from "./tone"

export function StateChip(props: { state: Topic["state"] | undefined; class?: string }) {
  const language = useLanguage()
  return (
    <span
      class={`inline-flex h-5 shrink-0 items-center whitespace-nowrap rounded-[4px] border px-1.5 text-12-regular ${toneChip[stateTone(props.state)]} ${props.class ?? ""}`}
    >
      {language.t(stateLabelKey(props.state))}
    </span>
  )
}

/** Row used by the topic list and by search results that point at a topic. */
export function TopicRow(props: {
  topic: Topic
  events?: number
  selected?: boolean
  onSelect?: () => void
  trailing?: JSX.Element
}) {
  const language = useLanguage()
  const count = () => props.events ?? props.topic.event_ids?.length ?? 0

  return (
    <button
      type="button"
      data-component="memory-topic-row"
      onClick={() => props.onSelect?.()}
      classList={{
        "flex w-full min-w-0 shrink-0 flex-col gap-1 rounded-[6px] border px-2.5 py-2 text-left transition-colors": true,
        "border-v2-border-border-strong bg-v2-background-bg-layer-02": Boolean(props.selected),
        "border-v2-border-border-base bg-v2-background-bg-layer-01 hover:bg-v2-overlay-simple-overlay-hover":
          !props.selected,
      }}
    >
      <div class="flex w-full items-center gap-2">
        <span class="min-w-0 flex-1 truncate text-12-medium text-v2-text-text-base">{props.topic.title}</span>
        <StateChip state={props.topic.state} />
      </div>
      <Show when={props.topic.summary || props.topic.goal}>
        <span class="w-full min-w-0 truncate text-12-regular text-v2-text-text-faint">
          {summarize(props.topic.summary || props.topic.goal, 120)}
        </span>
      </Show>
      <div class="flex w-full items-center gap-3 text-12-regular text-v2-text-text-faint">
        <span>{language.t("memory.topics.eventCount", { count: count() })}</span>
        <Show when={props.topic.updated_at}>
          <span>{getRelativeTime(props.topic.updated_at!, language.t)}</span>
        </Show>
        <Show when={props.trailing}>
          <span class="ml-auto flex items-center gap-1">{props.trailing}</span>
        </Show>
      </div>
    </button>
  )
}
