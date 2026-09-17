import { Show, type JSX } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"
import { useLanguage } from "@/context/language"
import { getRelativeTime } from "@/utils/time"
import { eventStatusLabelKey, eventStatusTone, sourceIcon, sourceLabelKey } from "../labels"
import { formatClock, summarize } from "../format"
import type { MemoryEvent } from "../types"
import { toneDot, toneText } from "./tone"

/** One captured event. Shared by the session live feed, the workbench and search. */
export function EventRow(props: {
  event: MemoryEvent
  dense?: boolean
  selected?: boolean
  actions?: JSX.Element
  onSelect?: () => void
  showTopic?: boolean
}) {
  const language = useLanguage()
  const tone = () => eventStatusTone(props.event.status)

  return (
    <div
      classList={{
        "group flex w-full gap-2 rounded-[6px] px-2 py-1.5": true,
        "bg-v2-background-bg-layer-02": Boolean(props.selected),
        "hover:bg-v2-overlay-simple-overlay-hover": Boolean(props.onSelect) && !props.selected,
      }}
    >
      <div class="flex w-4 shrink-0 justify-center pt-0.5">
        <Icon name={sourceIcon(props.event.source_type)} size="small" class="text-v2-icon-icon-muted" />
      </div>
      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <button
          type="button"
          disabled={!props.onSelect}
          onClick={() => props.onSelect?.()}
          classList={{
            "text-left": true,
            "cursor-pointer": Boolean(props.onSelect),
            "cursor-default": !props.onSelect,
          }}
        >
          <span class="block text-12-regular text-v2-text-text-base">
            {summarize(props.event.content, props.dense ? 90 : 180)}
          </span>
        </button>
        <div class="flex items-center gap-2 text-12-regular text-v2-text-text-faint">
          <span class="inline-flex items-center gap-1">
            <span class={`size-1.5 rounded-full ${toneDot[tone()]}`} />
            <span class={toneText[tone()]}>{language.t(eventStatusLabelKey(props.event.status))}</span>
          </span>
          <span>{language.t(sourceLabelKey(props.event.source_type))}</span>
          <Show when={props.showTopic && props.event.topic_title}>
            <span class="truncate">{props.event.topic_title}</span>
          </Show>
          <span class="ml-auto shrink-0 [font-variant-numeric:tabular-nums]">
            {formatClock(props.event.occurred_at) || getRelativeTime(props.event.occurred_at, language.t)}
          </span>
        </div>
      </div>
      <Show when={props.actions}>
        <div class="flex shrink-0 items-start gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          {props.actions}
        </div>
      </Show>
    </div>
  )
}
