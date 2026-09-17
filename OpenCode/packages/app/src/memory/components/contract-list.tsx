import { For, Show } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"
import { useLanguage } from "@/context/language"
import { describeValue } from "../format"
import { fieldLabelKey, type Tone } from "../labels"
import type { RestoreField } from "../types"
import { toneText } from "./tone"

function fieldTone(status: string | undefined): Tone {
  if (status === "present") return "success"
  if (status === "conflicted") return "danger"
  return "warning"
}

/**
 * The restore contract — what the agent will be handed when this topic resumes.
 * Missing entries are the interesting ones, so they read as a warning rather
 * than as an absence.
 */
export function ContractList(props: { fields: RestoreField[] | undefined; limit?: number; onSelect?: () => void }) {
  const language = useLanguage()
  const fields = () => (props.limit ? (props.fields ?? []).slice(0, props.limit) : (props.fields ?? []))
  const hidden = () => (props.fields?.length ?? 0) - fields().length
  const missing = () => (props.fields ?? []).filter((field) => field.status !== "present").length

  return (
    <Show
      when={(props.fields?.length ?? 0) > 0}
      fallback={
        <p class="px-2 py-1.5 text-12-regular text-v2-text-text-faint">{language.t("memory.contract.empty")}</p>
      }
    >
      <div class="flex flex-col">
        <For each={fields()}>
          {(field) => (
            <div class="flex items-start gap-2 border-b border-v2-border-border-muted px-2 py-1.5 last:border-b-0">
              <span class="w-[9rem] shrink-0 truncate text-12-regular text-v2-text-text-faint">
                {language.t(fieldLabelKey(field.name))}
              </span>
              <span
                classList={{
                  "min-w-0 flex-1 text-12-regular": true,
                  "text-v2-text-text-base": field.status === "present",
                  "text-v2-text-text-faint italic": field.status !== "present",
                }}
              >
                {field.status === "present" ? describeValue(field.value) : language.t("memory.contract.missing")}
              </span>
              <span class="flex shrink-0 items-center gap-1">
                <Icon
                  name={fieldTone(field.status) === "success" ? "circle-check" : "warning"}
                  size="small"
                  class={toneText[fieldTone(field.status)]}
                />
              </span>
            </div>
          )}
        </For>
        <Show when={hidden() > 0}>
          <button
            type="button"
            onClick={() => props.onSelect?.()}
            class="px-2 py-1.5 text-left text-12-regular text-v2-text-text-faint hover:text-v2-text-text-muted"
          >
            {language.t("memory.contract.more", { count: hidden() })}
          </button>
        </Show>
        <Show when={missing() > 0}>
          <p class="px-2 pt-1 text-12-regular text-v2-state-fg-warning">
            {language.t("memory.contract.pending", { count: missing() })}
          </p>
        </Show>
      </div>
    </Show>
  )
}
