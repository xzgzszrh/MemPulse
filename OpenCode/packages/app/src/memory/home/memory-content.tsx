import { Match, Show, Switch } from "solid-js"
import { useLanguage } from "@/context/language"
import type { LocalProject } from "@/context/layout"
import { WorkbenchHeader } from "../components/workbench-header"
import { MemoryGate } from "../components/empty-state"
import { useMemorySurface } from "../store"
import type { HomeSection, MemorySection } from "./sections"
import { sectionLabelKey } from "./section-labels"
import { Overview3D, type RecentSession } from "../views/overview-3d"
import { GraphSection } from "../views/graph"
import { RecentSection } from "../views/recent"
import { TopicsView } from "../views/topics"
import { EventsView } from "../views/events"
import { GovernanceView } from "../views/governance"
import { HealthView } from "../views/health"

/**
 * The memory half of the home page.
 *
 * The overview always renders — it is the app's front door, so a memory service
 * that is still starting (or missing, in a browser preview) does not replace
 * the landing page. The workbench sections need the data, so they sit behind
 * the gate.
 */
export function MemoryContent(props: {
  section: MemorySection
  projects: LocalProject[]
  project?: LocalProject
  recent?: RecentSession[]
  initialTopicId?: string
  onOpenTopic: (topicId: string) => void
  onNewSession?: () => void
  onChooseProject: (project: LocalProject) => void
  onBrowseProject: () => void
  onOpenProject: (project: LocalProject) => void
  onSelectSection: (section: HomeSection) => void
}) {
  const memory = useMemorySurface({ graph: true })
  const language = useLanguage()

  return (
    <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <Show when={props.section !== "overview"}>
        <WorkbenchHeader
          title={language.t(sectionLabelKey(props.section))}
          status={memory.status()}
          onOverview={() => props.onSelectSection("overview")}
        />
      </Show>

      <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
        <Switch>
          <Match when={props.section === "overview"}>
            <Overview3D
              projects={props.projects}
              project={props.project}
              recent={props.recent ?? []}
              onNewSession={() => props.onNewSession?.()}
              onChooseProject={props.onChooseProject}
              onBrowseProject={props.onBrowseProject}
              onEnterWorkbench={(sec) => props.onSelectSection(sec || "topics")}
              onOpenTopic={props.onOpenTopic}
              onOpenProject={props.onOpenProject}
            />
          </Match>
          <Match when={props.section !== "overview"}>
            <MemoryGate
              status={memory.status()}
              error={memory.error()}
              onRetry={() => void memory.refresh({ graph: true })}
            >
              <Switch>
                <Match when={props.section === "topics"}>
                  <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
                    <TopicsView initialTopicId={props.initialTopicId} directory={props.project?.worktree} />
                  </div>
                </Match>
                <Match when={props.section === "graph"}>
                  <div class="flex min-h-0 flex-1 flex-col overflow-hidden p-4">
                    <GraphSection />
                  </div>
                </Match>
                <Match when={props.section === "recent"}>
                  <div class="min-h-0 flex-1 overflow-y-auto p-4">
                    <RecentSection
                      projects={props.projects}
                      onOpenProject={props.onOpenProject}
                      onOpenSection={props.onSelectSection}
                    />
                  </div>
                </Match>
                <Match when={props.section === "events"}>
                  <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
                    <EventsView />
                  </div>
                </Match>
                <Match when={props.section === "governance"}>
                  <div class="min-h-0 flex-1 overflow-y-auto p-4">
                    <GovernanceView />
                  </div>
                </Match>
                <Match when={props.section === "health"}>
                  <div class="min-h-0 flex-1 overflow-y-auto p-4">
                    <HealthView />
                  </div>
                </Match>
              </Switch>
            </MemoryGate>
          </Match>
        </Switch>
      </div>
    </div>
  )
}
