import { Show, type JSX } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"
import { useLanguage } from "@/context/language"
import { MemPulseMark } from "./brand"
import type { MemoryStatus } from "../store"

/**
 * The 40px bar at the top of every home content column — the same bar whether
 * the column shows a project's sessions or a memory section, so moving between
 * them changes the content, not the frame.
 */
export function WorkbenchHeader(props: {
  title: string
  status?: MemoryStatus
  actions?: JSX.Element
  onOverview?: () => void
}) {
  const language = useLanguage()
  return (
    <div class="flex h-10 shrink-0 items-center justify-between border-b border-v2-border-border-base px-3">
      <div class="flex min-w-0 items-center gap-2">
        <MemPulseMark size={16} />
        <Show when={props.status}>
          <span
            class="flex h-1.5 w-1.5 rounded-full"
            classList={{
              "bg-v2-state-fg-success": props.status === "ready",
              "bg-v2-state-fg-warning": props.status === "loading",
              "bg-v2-state-fg-danger": props.status === "error" || props.status === "unavailable",
            }}
          />
        </Show>
        <span class="text-12-regular text-v2-text-text-faint">/</span>
        <span class="truncate text-12-medium text-v2-text-text-base">{props.title}</span>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        {props.actions}
        <Show when={props.onOverview}>
          <button
            type="button"
            onClick={() => props.onOverview?.()}
            class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-v2-border-border-base bg-v2-background-bg-base px-2.5 py-1 text-12-medium text-v2-text-text-muted transition-colors hover:bg-surface-raised-base hover:text-v2-text-text-base"
          >
            <Icon name="brain" size="small" />
            <span>{language.t("memory.tab.overview")}</span>
          </button>
        </Show>
      </div>
    </div>
  )
}
