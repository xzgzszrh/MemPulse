import { Show, type JSX } from "solid-js"

/**
 * A titled block. Every memory panel is a stack of these so headers, counts and
 * trailing actions line up across the session panel and the workbench.
 */
export function Section(props: {
  title: JSX.Element
  count?: number
  action?: JSX.Element
  children: JSX.Element
  class?: string
  bodyClass?: string
}) {
  return (
    <section class={props.class ?? "flex min-w-0 shrink-0 flex-col gap-2"}>
      <header class="flex h-7 items-center gap-2">
        <h3 class="text-12-medium text-v2-text-text-muted">{props.title}</h3>
        <Show when={props.count !== undefined}>
          <span class="text-12-regular text-v2-text-text-faint [font-variant-numeric:tabular-nums]">{props.count}</span>
        </Show>
        <div class="ml-auto flex items-center gap-1">
          <Show when={props.action}>{props.action}</Show>
        </div>
      </header>
      <div class={props.bodyClass ?? "flex min-w-0 flex-col"}>{props.children}</div>
    </section>
  )
}

/** A bordered surface used for the inner blocks of a panel. */
export function Card(props: { children: JSX.Element; class?: string }) {
  return (
    <div
      class={
        props.class ?? "min-w-0 rounded-[6px] border border-v2-border-border-base bg-v2-background-bg-layer-01 px-3 py-2.5"
      }
    >
      {props.children}
    </div>
  )
}
