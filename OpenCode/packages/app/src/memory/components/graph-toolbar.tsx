import { For, Show } from "solid-js"
import { Icon } from "@opencode-ai/ui/icon"
import { TextInputV2 } from "@opencode-ai/ui/v2/text-input-v2"
import { IconButtonV2 } from "@opencode-ai/ui/v2/icon-button-v2"
import { TooltipV2 } from "@opencode-ai/ui/v2/tooltip-v2"
import { useLanguage } from "@/context/language"
import { TAG_KINDS, tagKindLabelKey, tagSwatch } from "../labels"

export function GraphToolbar(props: {
  query: string
  onQuery: (value: string) => void
  hiddenKinds: Set<string>
  onToggleKind: (kind: string) => void
  onReset: () => void
  onZoom: (factor: number) => void
  counts: Map<string, number>
}) {
  const language = useLanguage()

  return (
    <div class="flex flex-wrap items-center gap-2">
      <div class="w-56">
        <TextInputV2
          value={props.query}
          placeholder={language.t("memory.graph.searchPlaceholder")}
          onInput={(event) => props.onQuery(event.currentTarget.value)}
          leadingIcon={<Icon name="magnifying-glass" size="small" />}
        />
      </div>

      <div class="flex flex-wrap items-center gap-1">
        <For each={TAG_KINDS}>
          {(kind) => {
            const hidden = () => props.hiddenKinds.has(kind)
            return (
              <button
                type="button"
                aria-pressed={!hidden()}
                onClick={() => props.onToggleKind(kind)}
                classList={{
                  "inline-flex h-6 items-center gap-1.5 rounded-[4px] border px-2 text-12-regular transition-colors": true,
                  "border-v2-border-border-base bg-v2-background-bg-layer-01 text-v2-text-text-muted hover:bg-v2-overlay-simple-overlay-hover":
                    !hidden(),
                  "border-v2-border-border-muted bg-transparent text-v2-text-text-faint": hidden(),
                }}
              >
                <span
                  class="size-1.5 rounded-full"
                  classList={{ "opacity-40": hidden() }}
                  style={{ "background-color": tagSwatch(kind) }}
                />
                {language.t(tagKindLabelKey(kind))}
                <span class="text-v2-text-text-faint [font-variant-numeric:tabular-nums]">
                  {props.counts.get(kind) ?? 0}
                </span>
              </button>
            )
          }}
        </For>
      </div>

      <div class="ml-auto flex items-center gap-1">
        <TooltipV2 value={language.t("memory.graph.zoomOut")}>
          <IconButtonV2
            size="small"
            variant="ghost"
            aria-label={language.t("memory.graph.zoomOut")}
            onClick={() => props.onZoom(1 / 1.25)}
            icon={<Icon name="collapse" size="small" />}
          />
        </TooltipV2>
        <TooltipV2 value={language.t("memory.graph.zoomIn")}>
          <IconButtonV2
            size="small"
            variant="ghost"
            aria-label={language.t("memory.graph.zoomIn")}
            onClick={() => props.onZoom(1.25)}
            icon={<Icon name="expand" size="small" />}
          />
        </TooltipV2>
        <TooltipV2 value={language.t("memory.graph.relayout")}>
          <IconButtonV2
            size="small"
            variant="ghost"
            aria-label={language.t("memory.graph.relayout")}
            onClick={props.onReset}
            icon={<Icon name="reset" size="small" />}
          />
        </TooltipV2>
        <Show when={props.query}>
          <TooltipV2 value={language.t("memory.graph.clearSearch")}>
            <IconButtonV2
              size="small"
              variant="ghost"
              aria-label={language.t("memory.graph.clearSearch")}
              onClick={() => props.onQuery("")}
              icon={<Icon name="close-small" size="small" />}
            />
          </TooltipV2>
        </Show>
      </div>
    </div>
  )
}
