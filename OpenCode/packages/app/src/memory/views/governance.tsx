import { createMemo, For, Show } from "solid-js"
import { useLanguage } from "@/context/language"
import { formatDateTime, describeValue } from "@/memory/format"
import type { Tone } from "@/memory/labels"
import { useMemory } from "@/memory/store"
import type { Knowledge, Preference, TombstoneReceipt } from "@/memory/types"
import { Card, Section } from "../components/section"
import { EmptyState } from "../components/empty-state"
import { toneChip } from "../components/tone"

const RECEIPT_TONE: Record<string, Tone> = {
  processed: "success",
  processing: "accent",
  blocked: "warning",
}

/**
 * Everything the memory system decided *about* the user rather than *from* the
 * user: preferences, versioned knowledge, checkpoints and forget receipts. Read
 * only — edits go through the agent or the CLI, which keeps the audit trail the
 * backend already maintains as the single source of truth.
 */
export function GovernanceView() {
  const memory = useMemory()
  const language = useLanguage()

  const governance = createMemo(() => memory.governance())

  return (
    <div class="flex h-full flex-col gap-5 overflow-y-auto px-4 py-4">
      <Section
        title={language.t("memory.governance.preferences")}
        count={governance().preferences.length}
        bodyClass="flex flex-col gap-1.5"
      >
        <Show
          when={governance().preferences.length > 0}
          fallback={<EmptyState icon="sliders" title={language.t("memory.governance.empty")} compact />}
        >
          <For each={governance().preferences}>
            {(item: Preference) => (
              <Card>
                <div class="flex flex-col gap-1">
                  <div class="flex items-center gap-2">
                    <span class="min-w-0 flex-1 truncate text-12-medium text-v2-text-text-base">{item.pref_key}</span>
                    <Show when={item.choice_type}>
                      <span class="inline-flex h-5 items-center rounded-[4px] border border-v2-border-border-base bg-v2-background-bg-layer-02 px-1.5 text-12-regular text-v2-text-text-muted">
                        {item.choice_type}
                      </span>
                    </Show>
                  </div>
                  <span class="text-12-regular text-v2-text-text-muted">{describeValue(item.value)}</span>
                  <div class="flex flex-wrap items-center gap-3 text-12-regular text-v2-text-text-faint">
                    <Show when={item.scope_type}>
                      <span>
                        {language.t("memory.governance.scope", {
                          scope: item.scope_id ? `${item.scope_type} · ${item.scope_id}` : item.scope_type!,
                        })}
                      </span>
                    </Show>
                    <Show when={item.created_at}>
                      <span>{formatDateTime(item.created_at)}</span>
                    </Show>
                  </div>
                </div>
              </Card>
            )}
          </For>
        </Show>
      </Section>

      <Section
        title={language.t("memory.governance.knowledge")}
        count={governance().knowledge.length}
        bodyClass="flex flex-col gap-1.5"
      >
        <Show
          when={governance().knowledge.length > 0}
          fallback={<EmptyState icon="branch" title={language.t("memory.governance.empty")} compact />}
        >
          <For each={governance().knowledge}>
            {(item: Knowledge) => (
              <Card>
                <div class="flex flex-col gap-1">
                  <div class="flex items-center gap-2">
                    <span class="min-w-0 flex-1 truncate text-12-medium text-v2-text-text-base">
                      {item.knowledge_key}
                    </span>
                    <Show when={item.disputed}>
                      <span
                        class={`inline-flex h-5 items-center rounded-[4px] border px-1.5 text-12-regular ${toneChip.warning}`}
                      >
                        {language.t("memory.governance.disputed")}
                      </span>
                    </Show>
                  </div>
                  <span class="text-12-regular text-v2-text-text-muted">{describeValue(item.value)}</span>
                  <div class="flex flex-wrap items-center gap-3 text-12-regular text-v2-text-text-faint">
                    <Show when={item.supersedes}>
                      <span>{language.t("memory.governance.supersedes", { id: item.supersedes! })}</span>
                    </Show>
                    <Show when={item.created_at}>
                      <span>{formatDateTime(item.created_at)}</span>
                    </Show>
                  </div>
                </div>
              </Card>
            )}
          </For>
        </Show>
      </Section>

      <Section
        title={language.t("memory.governance.checkpoints")}
        count={governance().checkpoints.length}
        bodyClass="flex flex-col rounded-[6px] border border-v2-border-border-base bg-v2-background-bg-layer-01"
      >
        <Show
          when={governance().checkpoints.length > 0}
          fallback={<EmptyState icon="checklist" title={language.t("memory.governance.empty")} compact />}
        >
          <For each={governance().checkpoints}>
            {(item) => (
              <div class="flex items-center gap-3 border-b border-v2-border-border-muted px-3 py-2 last:border-b-0">
                <span class="min-w-0 flex-1 truncate text-12-regular text-v2-text-text-base">
                  {memory.topic(item.topic_id)?.title ?? item.topic_id}
                </span>
                <span class="shrink-0 text-12-regular text-v2-text-text-faint">
                  {language.t("memory.session.checkpoint.revision", { revision: item.revision ?? 0 })}
                </span>
                <span class="shrink-0 text-12-regular text-v2-text-text-faint">{formatDateTime(item.created_at)}</span>
              </div>
            )}
          </For>
        </Show>
      </Section>

      <Section
        title={language.t("memory.governance.receipts")}
        count={governance().receipts.length}
        bodyClass="flex flex-col rounded-[6px] border border-v2-border-border-base bg-v2-background-bg-layer-01"
      >
        <Show
          when={governance().receipts.length > 0}
          fallback={<EmptyState icon="shield" title={language.t("memory.governance.receipts.empty")} compact />}
        >
          <For each={governance().receipts}>
            {(item: TombstoneReceipt) => (
              <div class="flex items-center gap-3 border-b border-v2-border-border-muted px-3 py-2 last:border-b-0">
                <span
                  class={`inline-flex h-5 shrink-0 items-center rounded-[4px] border px-1.5 text-12-regular ${
                    toneChip[RECEIPT_TONE[item.status] ?? "neutral"]
                  }`}
                >
                  {item.status}
                </span>
                <span class="shrink-0 text-12-regular text-v2-text-text-muted">{item.target_type}</span>
                <span class="min-w-0 flex-1 truncate text-12-mono text-v2-text-text-faint">{item.target_id}</span>
                <span class="shrink-0 text-12-regular text-v2-text-text-faint">{formatDateTime(item.created_at)}</span>
              </div>
            )}
          </For>
        </Show>
      </Section>
    </div>
  )
}
