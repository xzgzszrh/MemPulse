import { Match, Show, Switch, type JSX } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { useLanguage } from "@/context/language"
import type { MemoryStatus } from "../store"

/** The plain empty/blocked state used wherever a memory panel has nothing to show. */
export function EmptyState(props: {
  icon?: Parameters<typeof Icon>[0]["name"]
  title: JSX.Element
  description?: JSX.Element
  action?: JSX.Element
  compact?: boolean
}) {
  return (
    <div
      classList={{
        "flex flex-col items-center justify-center gap-2 text-center": true,
        "px-4 py-6": !props.compact,
        "px-3 py-4": Boolean(props.compact),
      }}
    >
      <Show when={props.icon}>
        <Icon name={props.icon!} class="text-v2-icon-icon-muted" />
      </Show>
      <div class="flex flex-col gap-1">
        <span class="text-12-medium text-v2-text-text-muted">{props.title}</span>
        <Show when={props.description}>
          <span class="max-w-[36ch] text-12-regular text-v2-text-text-faint">{props.description}</span>
        </Show>
      </div>
      <Show when={props.action}>{props.action}</Show>
    </div>
  )
}

/**
 * One place that decides what a non-ready store looks like, so the session tab,
 * the workbench and the settings section degrade identically instead of each
 * inventing a different failure screen.
 */
export function MemoryGate(props: {
  status: MemoryStatus
  error?: string
  onRetry: () => void
  children: JSX.Element
}) {
  const language = useLanguage()

  return (
    <Switch>
      <Match when={props.status === "ready"}>{props.children}</Match>
      <Match when={props.status === "loading"}>
        <EmptyState icon="brain" title={language.t("memory.status.loading")} compact />
      </Match>
      <Match when={props.status === "unavailable"}>
        <EmptyState
          icon="brain"
          title={language.t("memory.status.unavailable.title")}
          description={language.t("memory.status.unavailable.description")}
          compact
        />
      </Match>
      <Match when={props.status === "error"}>
        <EmptyState
          icon="warning"
          title={language.t("memory.status.error.title")}
          description={props.error}
          action={
            <ButtonV2 size="small" variant="outline" onClick={props.onRetry}>
              {language.t("memory.action.retry")}
            </ButtonV2>
          }
          compact
        />
      </Match>
    </Switch>
  )
}
