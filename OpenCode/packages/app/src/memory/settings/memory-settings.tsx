import { createMemo, Show } from "solid-js"
import { Switch } from "@opencode-ai/ui/switch"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { SelectV2 } from "@opencode-ai/ui/v2/select-v2"
import { useDialog } from "@opencode-ai/ui/context/dialog"
import { useLanguage } from "@/context/language"
import { useSettings } from "@/context/settings"
import { showToast } from "@/utils/toast"
import { MemoryGate } from "@/memory/components/empty-state"
import { useMemorySurface } from "@/memory/store"
import { ConfirmDialog } from "@/memory/components/confirm-dialog"
import type { Workspace } from "@/memory/types"
import { SettingsListV2 } from "@/components/settings-v2/parts/list"
import { SettingsRowV2 } from "@/components/settings-v2/parts/row"

const WORKSPACES: Workspace[] = ["demo", "personal"]

/**
 * Memory settings. Deliberately small: retrieval policy, capture and storage
 * are owned by the MemPulse service, and the panel reports those rather than
 * offering switches that would not actually change anything.
 */
export function MemorySettings() {
  const memory = useMemorySurface()
  const settings = useSettings()
  const language = useLanguage()
  const dialog = useDialog()

  const health = createMemo(() => memory.health())

  const switchWorkspace = async (workspace: Workspace | null) => {
    if (!workspace || workspace === memory.workspace()) return
    const result = await memory.switchWorkspace(workspace)
    if (!result) return
    showToast({
      variant: "success",
      title: language.t("memory.workspace.switched", {
        workspace: language.t(workspace === "demo" ? "memory.workspace.demo" : "memory.workspace.personal"),
      }),
    })
  }

  const reindex = () => {
    void dialog.show(() => (
      <ConfirmDialog
        title={language.t("memory.health.action.reindex")}
        description={language.t("memory.health.reindex.description")}
        confirmLabel={language.t("memory.action.confirm")}
        onConfirm={async () => {
          const result = await memory.mutate((client) => client.reindex())
          showToast({
            variant: result === undefined ? "error" : "success",
            title:
              result === undefined
                ? language.t("memory.health.action.failed")
                : language.t("memory.health.action.done"),
          })
        }}
      />
    ))
  }

  return (
    <div class="flex flex-col gap-4 p-4">
      <MemoryGate status={memory.status()} error={memory.error()} onRetry={() => void memory.refresh()}>
        <SettingsListV2>
          <SettingsRowV2
            title={language.t("settings.memory.workspace.title")}
            description={language.t("settings.memory.workspace.description")}
          >
            <SelectV2
              options={WORKSPACES}
              current={memory.workspace()}
              disabled={memory.switchingWorkspace()}
              value={(item) => item}
              label={(item) => language.t(item === "demo" ? "memory.workspace.demo" : "memory.workspace.personal")}
              onSelect={(value) => void switchWorkspace(value)}
              appearance="base"
            />
          </SettingsRowV2>

          <SettingsRowV2
            title={language.t("settings.memory.sessionTab.title")}
            description={language.t("settings.memory.sessionTab.description")}
          >
            <Switch
              checked={settings.memory.showSessionTab()}
              onChange={(checked) => settings.memory.setShowSessionTab(checked)}
            />
          </SettingsRowV2>

          <SettingsRowV2
            title={language.t("settings.memory.liveRefresh.title")}
            description={language.t("settings.memory.liveRefresh.description")}
          >
            <Switch
              checked={settings.memory.liveRefresh()}
              onChange={(checked) => settings.memory.setLiveRefresh(checked)}
            />
          </SettingsRowV2>

          <SettingsRowV2
            title={language.t("settings.memory.backend.title")}
            description={language.t("settings.memory.backend.description")}
          >
            <span class="text-12-mono text-v2-text-text-muted">{health()?.embedding_backend ?? "—"}</span>
          </SettingsRowV2>

          <SettingsRowV2
            title={language.t("settings.memory.indexPolicy.title")}
            description={language.t("settings.memory.indexPolicy.description")}
          >
            <span class="text-12-mono text-v2-text-text-muted">{health()?.index_policy ?? "—"}</span>
          </SettingsRowV2>

          <SettingsRowV2
            title={language.t("settings.memory.storage.title")}
            description={language.t("settings.memory.storage.description")}
          >
            <span class="max-w-[24ch] truncate text-12-mono text-v2-text-text-muted" title={health()?.db}>
              {health()?.db ?? "—"}
            </span>
          </SettingsRowV2>

          <SettingsRowV2
            title={language.t("settings.memory.reindex.title")}
            description={language.t("settings.memory.reindex.description")}
          >
            <ButtonV2 size="small" variant="outline" onClick={reindex}>
              {language.t("memory.health.action.reindex")}
            </ButtonV2>
          </SettingsRowV2>
        </SettingsListV2>

        <Show when={!memory.available}>
          <p class="text-12-regular text-v2-text-text-faint">{language.t("memory.status.unavailable.description")}</p>
        </Show>
      </MemoryGate>
    </div>
  )
}
