import { createMemo, createSignal, Show } from "solid-js"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { useLanguage } from "@/context/language"
import { showToast } from "@/utils/toast"
import type { MemoryClient } from "@/memory/client"
import { useMemory } from "@/memory/store"
import { Card, Section } from "../components/section"
import { toneDot } from "../components/tone"

function toneFor(value: string | undefined): keyof typeof toneDot {
  if (!value) return "neutral"
  if (["ready", "ok", "loaded", "strict", "not_configured"].includes(value)) return "neutral"
  if (["unloaded", "drafts_included"].includes(value)) return "warning"
  if (["failed", "error", "missing"].includes(value)) return "danger"
  return "neutral"
}

/**
 * What the engine is actually running. The README is explicit that several
 * capabilities are not yet verified on target hardware, so this page reports
 * the reported state verbatim instead of dressing it up.
 */
export function HealthView() {
  const memory = useMemory()
  const language = useLanguage()
  const [busy, setBusy] = createSignal<string>()

  const health = createMemo(() => memory.health())
  const sdk = createMemo(() => health()?.sdk_status)

  const run = async (name: string, action: (client: MemoryClient) => Promise<unknown>) => {
    setBusy(name)
    const result = await memory.mutate(action)
    setBusy(undefined)
    showToast({
      variant: result === undefined ? "error" : "success",
      title: result === undefined ? language.t("memory.health.action.failed") : language.t("memory.health.action.done"),
    })
  }

  return (
    <div class="flex h-full flex-col gap-5 overflow-y-auto px-4 py-4">
      <Section title={language.t("memory.health.service")}>
        <Card>
          <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
            <Row label={language.t("memory.health.service")} value={health()?.service} />
            <Row label={language.t("memory.health.storage")} value={health()?.storage} />
            <Row label={language.t("memory.health.scope")} value={health()?.scope} />
            <Row label={language.t("memory.health.schema")} value={health()?.schema_version?.toString()} />
            <Row label={language.t("memory.health.db")} value={health()?.db} mono />
          </dl>
        </Card>
      </Section>

      <Section title={language.t("memory.health.retrieval")}>
        <Card>
          <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
            <Row
              label={language.t("memory.health.backend")}
              value={health()?.embedding_backend}
              tone={toneFor(health()?.embedding_backend)}
            />
            <Row
              label={language.t("memory.health.indexPolicy")}
              value={health()?.index_policy}
              tone={toneFor(health()?.index_policy)}
            />
            <Row
              label={language.t("memory.health.topiccore")}
              value={health()?.topiccore ? language.t("memory.health.on") : language.t("memory.health.off")}
            />
            <Row
              label={language.t("memory.health.ok")}
              value={health()?.ok ? language.t("memory.health.on") : language.t("memory.health.off")}
              tone={health()?.ok ? "success" : "danger"}
            />
          </dl>
        </Card>
      </Section>

      <Section title={language.t("memory.health.sdk")}>
        <Card>
          <Show
            when={sdk()}
            fallback={<p class="text-12-regular text-v2-text-text-faint">{language.t("memory.health.sdk.none")}</p>}
          >
            {(value) => (
              <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
                <Row label={language.t("memory.health.sdk.backend")} value={value().backend} />
                <Row
                  label={language.t("memory.health.sdk.status")}
                  value={value().status}
                  tone={value().status === "ok" ? "success" : "warning"}
                />
                <Row label={language.t("memory.health.sdk.model")} value={value().model} />
                <Row label={language.t("memory.health.sdk.dimension")} value={value().dimension?.toString()} />
                <Show when={value().message}>
                  <div class="col-span-2 flex flex-col gap-0.5">
                    <dt class="text-12-regular text-v2-text-text-faint">{language.t("memory.health.sdk.message")}</dt>
                    <dd class="text-12-regular text-v2-text-text-muted">{value().message}</dd>
                  </div>
                </Show>
              </dl>
            )}
          </Show>
        </Card>
      </Section>

      <Section title={language.t("memory.health.maintenance")}>
        <Card>
          <div class="flex flex-col gap-3">
            <p class="text-12-regular text-v2-text-text-muted">{language.t("memory.health.maintenance.hint")}</p>
            <div class="flex flex-wrap items-center gap-2">
              <ButtonV2
                size="small"
                variant="outline"
                disabled={busy() === "reindex"}
                onClick={() => void run("reindex", (client) => client.reindex())}
              >
                {language.t("memory.health.action.reindex")}
              </ButtonV2>
              <ButtonV2
                size="small"
                variant="outline"
                disabled={busy() === "worker"}
                onClick={() => void run("worker", (client) => client.worker())}
              >
                {language.t("memory.health.action.worker")}
              </ButtonV2>
            </div>
          </div>
        </Card>
      </Section>

      <Section title={language.t("memory.health.workspace")}>
        <Card>
          <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
            <Row
              label={language.t("memory.workspace.label")}
              value={language.t(memory.workspace() === "demo" ? "memory.workspace.demo" : "memory.workspace.personal")}
            />
            <Row label={language.t("memory.stat.topics")} value={String(memory.stats().topics)} />
            <Row label={language.t("memory.stat.events")} value={String(memory.stats().events)} />
            <Row label={language.t("memory.stat.entities")} value={String(memory.stats().entities)} />
          </dl>
        </Card>
      </Section>
    </div>
  )
}

function Row(props: { label: string; value: string | undefined; mono?: boolean; tone?: keyof typeof toneDot }) {
  return (
    <div class="flex min-w-0 flex-col gap-0.5">
      <dt class="text-12-regular text-v2-text-text-faint">{props.label}</dt>
      <dd class="flex min-w-0 items-center gap-1.5">
        <Show when={props.tone}>
          <span class={`size-1.5 shrink-0 rounded-full ${toneDot[props.tone!]}`} />
        </Show>
        <span
          class={
            props.mono
              ? "truncate text-12-mono text-v2-text-text-base"
              : "truncate text-12-regular text-v2-text-text-base"
          }
        >
          {props.value ?? "—"}
        </span>
      </dd>
    </div>
  )
}
