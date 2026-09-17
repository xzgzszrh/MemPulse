import type { Accessor } from "solid-js"
import type { HomeSection } from "@/memory/home/sections"
import type { HomeProjectsController } from "./home-projects-controller"
import { HomeProjectsView } from "./home-projects-view"
import type { HomeScrollController } from "./home-scroll-controller"

export function HomeProjects(props: {
  projects: HomeProjectsController
  scroll: HomeScrollController
  section: Accessor<HomeSection>
  onSelectSection: (section: HomeSection) => void
}) {
  return (
    <HomeProjectsView
      language={props.projects.copy.language}
      servers={props.projects.server.list}
      projects={props.projects.project.list}
      recentlyClosed={props.projects.project.recentlyClosed}
      selection={props.projects.selection.value}
      homedir={props.projects.project.homedir}
      serverHealth={props.projects.server.health}
      projectsForServer={props.projects.server.projects}
      collapsed={props.projects.server.collapsed}
      canDefaultServer={props.projects.server.canDefault}
      defaultServerKey={props.projects.server.defaultKey}
      canRevealProject={props.projects.project.canReveal}
      unseenCount={props.projects.project.unseenCount}
      onWheel={props.scroll.viewport.containWheel}
      onChooseProject={props.projects.project.choose}
      onFocusServer={props.projects.server.focus}
      onToggleCollapsed={props.projects.server.toggleCollapsed}
      onEditServer={props.projects.server.edit}
      onSetDefaultServer={props.projects.server.setDefault}
      onRemoveServer={props.projects.server.remove}
      onMoveProject={props.projects.project.move}
      onSelectProject={(server, directory) => {
        // Picking a project is a request for its sessions, so the content column
        // follows the click. From a memory section the row may already be the
        // selected project, and upstream's toggle would deselect it — force the
        // selection instead so the click always lands on that project's sessions.
        if (props.section() !== "sessions") {
          props.onSelectSection("sessions")
          props.projects.project.focus(server, directory)
          return
        }
        props.projects.project.select(server, directory)
      }}
      onAddProjects={props.projects.project.add}
      onOpenProjectNewSession={props.projects.project.openNewSession}
      onEditProject={props.projects.project.edit}
      onRevealProject={props.projects.project.reveal}
      onClearNotifications={props.projects.project.clearNotifications}
      onCloseProject={props.projects.project.close}
      onOpenSettings={props.projects.utility.settings}
      onOpenHelp={props.projects.utility.help}
      section={props.section}
      onSelectSection={props.onSelectSection}
    />
  )
}
