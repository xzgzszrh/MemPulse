import { createEffect, createResource, For, onCleanup, onMount, Show } from "solid-js"
import { createStore } from "solid-js/store"
import { useDialog } from "@opencode-ai/ui/context/dialog"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { TextInputV2 } from "@opencode-ai/ui/v2/text-input-v2"
import { Dialog, DialogBody, DialogFooter, DialogHeader, DialogTitleGroup } from "@opencode-ai/ui/v2/dialog-v2"
import { useLanguage } from "@/context/language"
import { useMemory } from "../store"
import type { MemoryOperation, Topic } from "../types"
import { tagKindLabelKey } from "../labels"
import "./memory-dialog.css"

const fields = {
  removed_tags: "memory.operation.field.removedTags",
  topic_id: "memory.operation.field.topic",
  source_id: "memory.operation.field.source",
  target_id: "memory.operation.field.target",
  event: "memory.operation.field.event",
  title: "memory.operation.field.title",
  goal: "memory.topics.goal",
  project_ref: "memory.operation.field.project",
  content: "memory.operation.field.content",
  key: "memory.operation.field.key",
  scope_type: "memory.operation.field.scope",
  scope_id: "memory.operation.field.scope",
  reason: "memory.operation.field.reason",
  field_path: "memory.operation.field.field",
  session: "memory.operation.field.session",
  missing_tags: "memory.operation.field.missing",
  topics_count: "memory.operation.field.topicsCount",
  events_count: "memory.operation.field.eventsCount",
  archive_count: "memory.operation.field.archiveCount",
} as const

export function OperationDialog(props: { operation: MemoryOperation }) {
  const memory = useMemory()
  const language = useLanguage()
  const dialog = useDialog()
  const [state, setState] = createStore({ busy: false, error: "" })
  const apply = async (accept: boolean) => {
    setState({ busy: true, error: "" })
    try {
      if (accept) await memory.client.confirm(props.operation)
      else await memory.client.reject(props.operation.id)
      await memory.refresh({ graph: true })
      dialog.close()
    } catch (error) {
      setState("error", error instanceof Error ? error.message : String(error))
    } finally {
      setState("busy", false)
    }
  }
  return (
    <Dialog size="large" fit containerClass="memory-dialog-container">
      <DialogHeader>
        <DialogTitleGroup
          title={language.t(`memory.operation.kind.${props.operation.kind}`)}
          description={language.t("memory.operation.review.description")}
        />
      </DialogHeader>
      <DialogBody class="flex max-h-[60vh] flex-col gap-3 overflow-y-auto">
        <Show when={props.operation.kind === "import_demo"}>
          <p class="text-12-regular text-v2-text-text-muted">{language.t("memory.operation.import.description")}</p>
        </Show>
        <dl class="memory-operation-fields text-12-regular">
          <For each={props.operation.preview.fields}>
            {(field) => (
              <>
                <dt class="text-v2-text-text-muted">
                  {language.t(fields[field.key as keyof typeof fields] ?? "memory.operation.field.content")}
                </dt>
                <dd class="min-w-0 whitespace-pre-wrap break-words text-v2-text-text-base">{field.value}</dd>
              </>
            )}
          </For>
        </dl>
        <Show when={props.operation.preview.tags.length}>
          <div class="flex flex-wrap gap-1">
            <For each={props.operation.preview.tags}>
              {(tag) => (
                <span class="rounded-md border border-v2-border-border-base px-2 py-1 text-12-regular">
                  {tag.label || tag.value} · {language.t(tagKindLabelKey(tag.kind))} ·{" "}
                  {language.t(
                    tag.status === "pending"
                      ? "memory.operation.tag.pending"
                      : tag.status === "attribute"
                        ? "memory.operation.tag.attribute"
                        : "memory.operation.tag.accepted",
                  )}
                </span>
              )}
            </For>
          </div>
        </Show>
        <p class="text-12-regular text-v2-text-text-muted">
          {language.t("memory.operation.affected", { count: props.operation.preview.affected_events })}
        </p>
        <Show when={state.error}>
          <p role="alert" class="text-12-regular text-v2-text-text-base">
            {state.error}
          </p>
        </Show>
      </DialogBody>
      <DialogFooter>
        <ButtonV2 variant="ghost" disabled={state.busy} onClick={() => void apply(false)}>
          {language.t("memory.operation.reject")}
        </ButtonV2>
        <ButtonV2
          variant={props.operation.kind.startsWith("forget") ? "danger" : "contrast"}
          disabled={state.busy}
          onClick={() => void apply(true)}
        >
          {language.t("memory.action.confirm")}
        </ButtonV2>
      </DialogFooter>
    </Dialog>
  )
}

/** Pending agent actions remain reviewable even when the memory side panel is closed. */
export function MemoryOperationCenter() {
  const memory = useMemory()
  const language = useLanguage()
  const dialog = useDialog()
  const [state, setState] = createStore<{ operations: MemoryOperation[]; seen: string[] }>({ operations: [], seen: [] })
  let loading = false
  const refresh = async () => {
    if (loading || !memory.available || document.hidden) return
    loading = true
    try {
      setState("operations", (await memory.client.pending()).operations)
    } catch {
      /* Offline memory keeps normal chat usable. */
    } finally {
      loading = false
    }
  }
  const open = (operation: MemoryOperation) => {
    setState("seen", (seen) => [...seen, operation.id])
    void dialog.show(
      () => <OperationDialog operation={operation} />,
      () => void refresh(),
    )
  }
  onMount(() => {
    void refresh()
    const timer = setInterval(() => void refresh(), 2500)
    onCleanup(() => clearInterval(timer))
  })
  createEffect(() => {
    const next = state.operations.find((operation) => !state.seen.includes(operation.id))
    if (next && !dialog.active) open(next)
  })
  return (
    <Show when={state.operations[0]}>
      {(operation) => (
        <div class="pointer-events-auto fixed bottom-4 right-4 z-40 rounded-lg border border-v2-border-border-base bg-v2-background-bg-base p-1 shadow-lg">
          <ButtonV2 variant="ghost" onClick={() => open(operation())}>
            {language.t("memory.operation.pending", { count: state.operations.length })}
          </ButtonV2>
        </div>
      )}
    </Show>
  )
}

export function CreateTopicDialog(props: { sessionId?: string; directory?: string }) {
  const memory = useMemory()
  const language = useLanguage()
  const dialog = useDialog()
  const [state, setState] = createStore({ title: "", goal: "", keywords: "", busy: false, error: "" })
  const [sources, setSources] = createStore<{ selected: string[] }>({ selected: [] })
  const create = async () => {
    setState({ busy: true, error: "" })
    try {
      await memory.client.commit("create_topic", {
        title: state.title.trim(),
        goal: state.goal.trim(),
        keywords: state.keywords
          .split(/[,，、\n]/)
          .map((item) => item.trim())
          .filter(Boolean),
        session_id: props.sessionId,
        project_ref: props.directory,
        event_ids: sources.selected,
      })
      await memory.refresh({ graph: true })
      dialog.close()
    } catch (error) {
      setState("error", error instanceof Error ? error.message : String(error))
    } finally {
      setState("busy", false)
    }
  }
  return (
    <Dialog size="large" fit containerClass="memory-dialog-container">
      <DialogHeader>
        <DialogTitleGroup
          title={language.t("memory.operation.kind.create_topic")}
          description={language.t("memory.operation.create.description")}
        />
      </DialogHeader>
      <DialogBody class="flex flex-col gap-3">
        <TextInputV2
          aria-label={language.t("memory.operation.field.title")}
          placeholder={language.t("memory.operation.field.title")}
          value={state.title}
          onInput={(event) => setState("title", event.currentTarget.value)}
        />
        <TextInputV2
          aria-label={language.t("memory.topics.goal")}
          placeholder={language.t("memory.operation.goal.placeholder")}
          value={state.goal}
          onInput={(event) => setState("goal", event.currentTarget.value)}
        />
        <TextInputV2
          aria-label={language.t("memory.operation.keywords")}
          placeholder={language.t("memory.operation.keywords")}
          value={state.keywords}
          onInput={(event) => setState("keywords", event.currentTarget.value)}
        />
        <Show when={props.directory}>
          <p class="break-all text-12-regular text-v2-text-text-muted">
            {language.t("memory.operation.field.project")}：{props.directory}
          </p>
        </Show>
        <SourceSelector
          sessionId={props.sessionId}
          selected={sources.selected}
          onChange={(value) => setSources("selected", value)}
        />
        <Show when={state.error}>
          <p role="alert" class="text-12-regular">
            {state.error}
          </p>
        </Show>
      </DialogBody>
      <DialogFooter>
        <ButtonV2 variant="ghost" disabled={state.busy} onClick={() => dialog.close()}>
          {language.t("memory.action.cancel")}
        </ButtonV2>
        <ButtonV2
          variant="contrast"
          disabled={state.busy || state.title.trim().length < 2 || state.goal.trim().length < 8}
          onClick={() => void create()}
        >
          {language.t("memory.action.confirm")}
        </ButtonV2>
      </DialogFooter>
    </Dialog>
  )
}

export function BindTopicDialog(props: { sessionId: string; directory: string; topics: Topic[] }) {
  const memory = useMemory()
  const language = useLanguage()
  const dialog = useDialog()
  const [state, setState] = createStore({ selected: "", busy: false, error: "" })
  const [sources, setSources] = createStore<{ selected: string[] }>({ selected: [] })
  const bind = async () => {
    setState({ busy: true, error: "" })
    try {
      await memory.client.commit("bind_topic", {
        topic_id: state.selected,
        session_id: props.sessionId,
        project_ref: props.directory,
        event_ids: sources.selected,
      })
      await memory.refresh()
      dialog.close()
    } catch (error) {
      setState("error", error instanceof Error ? error.message : String(error))
    } finally {
      setState("busy", false)
    }
  }
  return (
    <Dialog size="large" fit containerClass="memory-dialog-container">
      <DialogHeader>
        <DialogTitleGroup
          title={language.t("memory.operation.kind.bind_topic")}
          description={language.t("memory.operation.bind.description")}
        />
      </DialogHeader>
      <DialogBody class="flex max-h-[55vh] flex-col gap-2 overflow-y-auto">
        <p class="break-all text-12-regular text-v2-text-text-muted">{props.directory}</p>
        <For each={props.topics}>
          {(topic) => (
            <label class="flex cursor-pointer items-start gap-3 rounded-lg border border-v2-border-border-base p-3">
              <input
                type="radio"
                name="memory-task"
                value={topic.topic_id}
                checked={state.selected === topic.topic_id}
                onChange={() => setState("selected", topic.topic_id)}
              />
              <span>
                <span class="block text-14-medium">{topic.title}</span>
                <span class="block text-12-regular text-v2-text-text-muted">{topic.goal}</span>
              </span>
            </label>
          )}
        </For>
        <SourceSelector
          sessionId={props.sessionId}
          selected={sources.selected}
          onChange={(value) => setSources("selected", value)}
        />
        <Show when={state.error}>
          <p role="alert" class="text-12-regular">
            {state.error}
          </p>
        </Show>
      </DialogBody>
      <DialogFooter>
        <ButtonV2 variant="ghost" disabled={state.busy} onClick={() => dialog.close()}>
          {language.t("memory.action.cancel")}
        </ButtonV2>
        <ButtonV2 variant="contrast" disabled={state.busy || !state.selected} onClick={() => void bind()}>
          {language.t("memory.action.confirm")}
        </ButtonV2>
      </DialogFooter>
    </Dialog>
  )
}

function SourceSelector(props: { sessionId?: string; selected: string[]; onChange: (selected: string[]) => void }) {
  const memory = useMemory()
  const language = useLanguage()
  const [inbox] = createResource(
    () => props.sessionId,
    (sessionId) => memory.client.inbox(sessionId),
  )
  return (
    <Show when={inbox()?.events.length}>
      <details class="rounded-lg border border-v2-border-border-base p-3">
        <summary class="cursor-pointer text-12-medium">{language.t("memory.operation.sources")}</summary>
        <div class="mt-2 flex max-h-48 flex-col gap-2 overflow-y-auto">
          <For each={inbox()?.events}>
            {(event) => (
              <label class="flex items-start gap-2 text-12-regular">
                <input
                  type="checkbox"
                  checked={props.selected.includes(event.event_id)}
                  onChange={(change) =>
                    props.onChange(
                      change.currentTarget.checked
                        ? [...props.selected, event.event_id]
                        : props.selected.filter((id) => id !== event.event_id),
                    )
                  }
                />
                <span class="min-w-0 break-words" title={event.content}>
                  {event.content.slice(0, 300)}
                </span>
              </label>
            )}
          </For>
        </div>
      </details>
    </Show>
  )
}
