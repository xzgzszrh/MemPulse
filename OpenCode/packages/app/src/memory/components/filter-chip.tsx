import { Show } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"

/** Small toggle used by the topic state, event source and event status filters. */
export function FilterChip(props: {
  active: boolean
  label: string
  onClick: () => void
  icon?: Parameters<typeof Icon>[0]["name"]
}) {
  return (
    <button
      type="button"
      aria-pressed={props.active}
      onClick={props.onClick}
      classList={{
        "inline-flex h-6 items-center gap-1.5 rounded-[4px] border px-2 text-12-regular transition-colors": true,
        "border-v2-border-border-strong bg-v2-background-bg-layer-02 text-v2-text-text-base": props.active,
        "border-v2-border-border-base bg-transparent text-v2-text-text-muted hover:bg-v2-overlay-simple-overlay-hover":
          !props.active,
      }}
    >
      <Show when={props.icon}>
        <Icon name={props.icon!} size="small" />
      </Show>
      {props.label}
    </button>
  )
}
