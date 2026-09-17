import { createMemo, Match, Switch } from "solid-js"
import { createStore } from "solid-js/store"
import { DateTime } from "luxon"
import { ScrollView } from "@opencode-ai/ui/scroll-view"
import { useLanguage } from "@/context/language"
import { sessionTitle } from "@/utils/session-title"
import { displayName } from "@/pages/layout/helpers"
import { useMemory } from "@/memory/store"
import { WorkbenchHeader } from "@/memory/components/workbench-header"
import { createHomeController } from "./home/home-controller"
import { createHomeProjectsController } from "./home/home-projects-controller"
import { HomeProjects } from "./home/home-projects"
import { createHomeScrollController } from "./home/home-scroll-controller"
import { createHomeSessionSearchController } from "./home/home-session-search-controller"
import { createHomeSessionsController } from "./home/home-sessions-controller"
import { HomeSessions } from "./home/home-sessions"
import { MemoryContent } from "@/memory/home/memory-content"
import { isMemorySection, type HomeSection, type MemorySection } from "@/memory/home/sections"
import type { RecentSession } from "@/memory/views/overview-3d"
import type { LocalProject } from "@/context/layout"

/**
 * The app's landing surface.
 *
 * Opens on the MemPulse overview: the memory constellation with quick actions
 * to start a session, resume a recent one, or step into a workbench section.
 * Memory sections show the sidebar beside their content; picking a project
 * switches to the classic sessions view for that project.
 */
export function NewHome() {
  const home = createHomeController()
  const projects = createHomeProjectsController(home)
  const sessions = createHomeSessionsController(home)
  const search = createHomeSessionSearchController(home, sessions)
  const scroll = createHomeScrollController(sessions.data.groups)
  const language = useLanguage()
  const memory = useMemory()

  const [view, setView] = createStore<{ section: HomeSection; topicId?: string }>({ section: "overview" })
  const section = () => view.section
  const setSection = (section: HomeSection) => setView({ section, topicId: undefined })
  const openTopic = (topicId: string) => setView({ section: "topics", topicId })
  const chooseProject = (project: LocalProject) => {
    const server = home.server.focused()
    if (server) home.project.choose(server, project.worktree)
  }
  const browseProject = () => {
    const server = home.server.focused()
    if (server) projects.project.choose(server)
  }
  const newSession = () => (home.project.newSession() ? sessions.session.create() : browseProject())

  const openProject = (worktree: string) => {
    setSection("sessions")
    const server = home.server.focused()
    if (server) home.project.select(server, worktree)
  }

  const recent = createMemo<RecentSession[]>(() =>
    sessions.data
      .records()
      .slice(0, 3)
      .map((record) => ({
        id: record.session.id,
        title: sessionTitle(record.session.title) || record.session.id,
        when: relativeDay(record.session.time.updated ?? record.session.time.created, language),
        project: record.projectName,
        open: () => sessions.session.open(record.session),
      })),
  )

  return (
    <div
      class={`
        m-2 min-h-0 flex-1 self-stretch overflow-hidden rounded-[10px]
        bg-v2-background-bg-base shadow-[var(--v2-elevation-raised)]
      `}
    >
      <Switch>
        <Match when={section() === "overview"}>
          <div class="h-full w-full min-h-0 overflow-hidden">
            <MemoryContent
              section="overview"
              projects={projects.project.list()}
              project={home.project.newSession()}
              recent={recent()}
              onNewSession={newSession}
              onChooseProject={chooseProject}
              onBrowseProject={browseProject}
              onOpenProject={(project) => openProject(project.worktree)}
              onSelectSection={setSection}
              onOpenTopic={openTopic}
            />
          </div>
        </Match>

        <Match when={section() !== "overview"}>
          <div class="flex h-full w-full min-h-0 min-w-0 divide-x divide-v2-border-border-base">
            <div class="h-full w-[260px] shrink-0 min-h-0 pl-3.5 pr-2">
              <HomeProjects projects={projects} scroll={scroll} section={section} onSelectSection={setSection} />
            </div>
            <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
              <Switch>
                <Match when={section() === "sessions"}>
                  <WorkbenchHeader
                    title={
                      home.project.selected()
                        ? displayName(home.project.selected()!)
                        : language.t("sidebar.project.recentSessions")
                    }
                    status={memory.status()}
                    onOverview={() => setSection("overview")}
                  />
                  <ScrollView
                    class="min-h-0 flex-1 [container-type:size]"
                    thumbContainer={scroll.viewport.thumbTrack}
                    thumbHoverTarget={scroll.viewport.hoverTarget}
                    viewportRef={scroll.viewport.setViewport}
                    onScroll={(event) => scroll.viewport.update(event.currentTarget.scrollTop)}
                    onWheel={(event) => scroll.viewport.containOuterWheel(event)}
                  >
                    <div class="mx-auto w-full max-w-[760px] px-6">
                      <HomeSessions sessions={sessions} search={search} scroll={scroll} />
                    </div>
                  </ScrollView>
                </Match>
                <Match when={isMemorySection(section())}>
                  <MemoryContent
                    section={section() as MemorySection}
                    projects={projects.project.list()}
                    project={home.project.newSession()}
                    recent={recent()}
                    onNewSession={newSession}
                    onChooseProject={chooseProject}
                    onBrowseProject={browseProject}
                    onOpenProject={(project) => openProject(project.worktree)}
                    onSelectSection={setSection}
                    initialTopicId={view.topicId}
                    onOpenTopic={openTopic}
                  />
                </Match>
              </Switch>
            </div>
          </div>
        </Match>
      </Switch>
    </div>
  )
}

function relativeDay(millis: number, language: ReturnType<typeof useLanguage>) {
  const time = DateTime.fromMillis(millis)
  const now = DateTime.local()
  if (time.hasSame(now, "day")) return time.toFormat("HH:mm")
  if (time.hasSame(now.minus({ days: 1 }), "day")) return language.t("home.sessions.group.yesterday")
  return time.toFormat(time.hasSame(now, "year") ? "MM-dd" : "yyyy-MM-dd")
}
