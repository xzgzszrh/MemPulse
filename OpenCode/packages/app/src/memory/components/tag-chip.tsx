import { For, Show } from "solid-js"
import { useLanguage } from "@/context/language"
import { tagKindLabelKey, tagSwatch } from "../labels"
import type { Tag } from "../types"

/**
 * Tags are rendered as a colour dot plus their canonical value. The dot colour
 * comes from the fixed avatar palette keyed by kind, which keeps person /
 * resource / keyword / time / vector distinguishable in both themes without
 * introducing colours the design system does not already own.
 */
export function TagChip(props: { tag: Tag; onClick?: () => void }) {
  const language = useLanguage()
  return (
    <button
      type="button"
      disabled={!props.onClick}
      onClick={() => props.onClick?.()}
      title={language.t(tagKindLabelKey(props.tag.kind))}
      classList={{
        "inline-flex h-5 max-w-[18ch] items-center gap-1.5 rounded-[4px] border px-1.5": true,
        "border-v2-border-border-base bg-v2-background-bg-layer-01": true,
        "cursor-pointer hover:bg-v2-overlay-simple-overlay-hover": Boolean(props.onClick),
        "cursor-default": !props.onClick,
      }}
    >
      <span class="size-1.5 shrink-0 rounded-full" style={{ "background-color": tagSwatch(props.tag.kind) }} />
      <span class="truncate text-12-regular text-v2-text-text-muted">
        {props.tag.label || props.tag.value || props.tag.canonical}
      </span>
    </button>
  )
}

export function TagList(props: { tags: Tag[] | undefined; limit?: number; onSelect?: (tag: Tag) => void }) {
  const tags = () => (props.limit ? (props.tags ?? []).slice(0, props.limit) : (props.tags ?? []))
  const hidden = () => (props.tags?.length ?? 0) - tags().length

  return (
    <Show when={tags().length > 0}>
      <div class="flex flex-wrap items-center gap-1">
        <For each={tags()}>
          {(tag) => <TagChip tag={tag} onClick={props.onSelect ? () => props.onSelect!(tag) : undefined} />}
        </For>
        <Show when={hidden() > 0}>
          <span class="text-12-regular text-v2-text-text-faint">+{hidden()}</span>
        </Show>
      </div>
    </Show>
  )
}
