import { createMemo, Show } from "solid-js"
import { BasicTool } from "@opencode-ai/session-ui/basic-tool"
import { Markdown } from "@opencode-ai/session-ui/markdown"
import { ToolRegistry, type ToolProps } from "@opencode-ai/session-ui/message-part"
import { useLanguage } from "@/context/language"

/**
 * Timeline cards for the `memory_*` tools the MemPulse plugin registers with the
 * agent (packages/opencode/src/plugin/mempulse.ts). Without these the calls fall
 * back to the generic "Called `memory_search`" row; with them a memory action
 * reads like the built-in tools do — an icon, what was asked, and the evidence
 * that came back, folded away until you want it.
 */

function Output(props: { output?: string }) {
  const language = useLanguage()
  return (
    <Show when={props.output}>
      <div data-component="tool-output" data-scrollable tabIndex={0} role="region" aria-label={language.t("memory.title")}>
        <Markdown text={props.output!} />
      </div>
    </Show>
  )
}

function clip(value: unknown, max = 80) {
  if (typeof value !== "string") return ""
  const flat = value.replace(/\s+/g, " ").trim()
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat
}

function register(name: string, render: (props: ToolProps) => any) {
  ToolRegistry.register({ name, render })
}

register("memory_search", (props) => {
  const language = useLanguage()
  const hits = createMemo(() => (typeof props.metadata.hits === "number" ? props.metadata.hits : -1))
  return (
    <BasicTool
      {...props}
      icon="magnifying-glass"
      trigger={{
        title: language.t("memory.tool.search"),
        subtitle: clip(props.input.query),
        args: hits() >= 0 ? [language.t("memory.tool.search.hits", { count: hits() })] : [],
      }}
    >
      <Output output={props.output} />
    </BasicTool>
  )
})

register("memory_recall", (props) => {
  const language = useLanguage()
  return (
    <BasicTool
      {...props}
      icon="archive"
      trigger={{
        title: language.t("memory.tool.recall"),
        subtitle: clip(props.metadata.topic_title) || clip(props.input.query) || clip(props.input.topic_id) || language.t("memory.tool.recall.current"),
        args: Array.isArray(props.metadata.missing) && props.metadata.missing.length ? [language.t("memory.contract.pending", { count: props.metadata.missing.length })] : [],
      }}
    >
      <Output output={props.output} />
    </BasicTool>
  )
})

register("memory_topics", (props) => {
  const language = useLanguage()
  return (
    <BasicTool
      {...props}
      icon="bullet-list"
      trigger={{
        title: language.t("memory.tool.topics"),
        subtitle: clip(props.input.query),
        args: typeof props.metadata.count === "number" ? [language.t("memory.tool.topics.count", { count: props.metadata.count })] : [],
      }}
    >
      <Output output={props.output} />
    </BasicTool>
  )
})

register("memory_remember", (props) => {
  const language = useLanguage()
  const kind = createMemo(() => (typeof props.input.kind === "string" ? props.input.kind : "note"))
  const kindLabel = createMemo(() => language.t(`memory.tool.remember.${kind()}` as "memory.tool.remember.note"))
  return (
    <BasicTool
      {...props}
      icon="brain"
      trigger={{
        title: language.t("memory.tool.remember"),
        subtitle: clip(props.input.content, 96),
        args: [kindLabel(), ...(typeof props.input.key === "string" && props.input.key ? [props.input.key] : []), ...(props.input.temporary ? [language.t("memory.tool.remember.temporary")] : [])],
      }}
    >
      <Output output={props.output} />
    </BasicTool>
  )
})

register("memory_checkpoint", (props) => {
  const language = useLanguage()
  return (
    <BasicTool
      {...props}
      icon="check"
      trigger={{
        title: language.t("memory.tool.checkpoint"),
        subtitle: clip(props.input.topic_id) || language.t("memory.tool.recall.current"),
      }}
    >
      <Output output={props.output} />
    </BasicTool>
  )
})

register("memory_forget", (props) => {
  const language = useLanguage()
  return (
    <BasicTool
      {...props}
      icon="trash"
      trigger={{
        title: language.t("memory.tool.forget"),
        subtitle: clip(props.input.target_id),
        args: [typeof props.input.target_type === "string" ? props.input.target_type : "", ...(props.input.reason ? [clip(props.input.reason, 60)] : [])].filter(Boolean),
      }}
    >
      <Output output={props.output} />
    </BasicTool>
  )
})
