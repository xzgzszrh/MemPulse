/**
 * Maps backend enum values onto the design system. Every visual attribute the
 * memory surfaces need — tone, swatch, icon — is resolved here so views stay
 * declarative and no component invents its own colour.
 */

import type { EventStatus, GraphNode, MemorySection, SourceType, TagKind, TopicState } from "./types"

/** Tone maps onto the v2 state tokens (`--v2-state-*`). */
export type Tone = "neutral" | "accent" | "success" | "warning" | "danger"

// Mirrors `TopicState` in MemPulse/src/mempulse/models.py.
const STATE_LABEL = {
  active: "memory.state.active",
  incomplete: "memory.state.incomplete",
  archived: "memory.state.archived",
} as const

export function stateLabelKey(state: TopicState | undefined) {
  if (state === "active" || state === "incomplete" || state === "archived") return STATE_LABEL[state]
  return "memory.state.unknown"
}

export function stateTone(state: TopicState | undefined): Tone {
  switch (state) {
    case "active":
      return "success"
    // Incomplete means the topic is missing required tags, so it is not yet
    // admitted to strict retrieval. That is worth flagging, not hiding.
    case "incomplete":
      return "warning"
    default:
      return "neutral"
  }
}

const EVENT_STATUS_LABEL = {
  success: "memory.eventStatus.success",
  failed: "memory.eventStatus.failed",
  pending: "memory.eventStatus.pending",
} as const

export function eventStatusLabelKey(status: EventStatus | undefined) {
  if (status === "success" || status === "failed" || status === "pending") return EVENT_STATUS_LABEL[status]
  return "memory.eventStatus.unknown"
}

export function eventStatusTone(status: EventStatus | undefined): Tone {
  switch (status) {
    case "success":
      return "success"
    case "failed":
      return "danger"
    case "pending":
      return "warning"
    default:
      return "neutral"
  }
}

const SOURCE_LABEL = {
  conversation: "memory.source.conversation",
  tool: "memory.source.tool",
  configuration: "memory.source.configuration",
} as const

export function sourceLabelKey(source: SourceType | undefined) {
  if (source === "conversation" || source === "tool" || source === "configuration") return SOURCE_LABEL[source]
  return "memory.source.other"
}

/** Icon names come from `@opencode-ai/ui/icon`; these all exist upstream. */
export function sourceIcon(source: SourceType | undefined): "bubble-5" | "console" | "sliders" | "code" {
  switch (source) {
    case "conversation":
      return "bubble-5"
    case "tool":
      return "console"
    case "configuration":
      return "sliders"
    default:
      return "code"
  }
}

// Mirrors `TagKind` in MemPulse/src/mempulse/models.py — the backend spells the
// kinds out in full, so labels and swatches key off those exact values.
const TAG_LABEL = {
  person: "memory.tagKind.person",
  resource: "memory.tagKind.resource",
  keyword: "memory.tagKind.keyword",
  time: "memory.tagKind.time",
  vector: "memory.tagKind.vector",
} as const

export function tagKindLabelKey(kind: string | undefined) {
  if (kind === "person" || kind === "resource" || kind === "keyword" || kind === "time" || kind === "vector")
    return TAG_LABEL[kind]
  return "memory.tagKind.other"
}

export const TAG_KINDS: TagKind[] = ["person", "resource", "keyword", "time", "vector"]

/**
 * Swatch colours reuse the project-avatar palette: it is the only fixed,
 * theme-independent colour set the design system already ships, so graph nodes
 * and tag chips stay legible in both light and dark without inventing values.
 */
const TAG_SWATCH: Record<string, string> = {
  person: "var(--v2-avatar-bg-blue)",
  resource: "var(--v2-avatar-bg-purple)",
  keyword: "var(--v2-avatar-bg-yellow)",
  time: "var(--v2-avatar-bg-cyan)",
  vector: "var(--v2-avatar-bg-green)",
}

export function tagSwatch(kind: string | undefined): string {
  return TAG_SWATCH[kind ?? ""] ?? "var(--v2-avatar-bg-gray)"
}

export function nodeSwatch(node: Pick<GraphNode, "type" | "kind" | "state">): string {
  if (node.type === "topic") {
    if (node.state === "incomplete") return "var(--v2-avatar-bg-orange)"
    if (node.state === "archived") return "var(--v2-avatar-bg-gray)"
    return "var(--v2-avatar-bg-pink)"
  }
  return tagSwatch(node.kind)
}

// The exact field names `TopicCore.restore` emits (MemPulse/src/mempulse/core.py).
const FIELD_LABEL: Record<string, string> = {
  input_files: "memory.field.inputFiles",
  completed_steps: "memory.field.completedSteps",
  pending_steps: "memory.field.pendingSteps",
  template_version: "memory.field.templateVersion",
  output_preference: "memory.field.outputPreference",
}

export function fieldLabelKey(name: string) {
  return FIELD_LABEL[name] ?? "memory.field.other"
}

const TAB_LABEL: Record<MemorySection, string> = {
  overview: "memory.tab.overview",
  topics: "memory.tab.topics",
  graph: "memory.tab.graph",
  recent: "memory.tab.recent",
  events: "memory.tab.events",
  governance: "memory.tab.governance",
  health: "memory.tab.health",
}

export function tabLabelKey(section: MemorySection) {
  return TAB_LABEL[section] as
    | "memory.tab.overview"
    | "memory.tab.graph"
    | "memory.tab.recent"
    | "memory.tab.topics"
    | "memory.tab.events"
    | "memory.tab.governance"
    | "memory.tab.health"
}

export const TAB_ICON: Record<
  MemorySection,
  "dot-grid" | "status" | "bullet-list" | "console" | "shield" | "checklist" | "brain"
> = {
  overview: "brain",
  topics: "bullet-list",
  graph: "dot-grid",
  recent: "status",
  events: "console",
  governance: "shield",
  health: "checklist",
}

const ROUTE_LABEL = {
  NEW: "memory.route.new",
  RESUME: "memory.route.resume",
  ATTACH: "memory.route.attach",
  AMBIGUOUS: "memory.route.ambiguous",
} as const

export function routeLabelKey(route: string | undefined) {
  if (route === "NEW" || route === "RESUME" || route === "ATTACH" || route === "AMBIGUOUS") return ROUTE_LABEL[route]
  return "memory.route.unknown"
}

export function routeTone(route: string | undefined): Tone {
  switch (route) {
    case "RESUME":
      return "success"
    case "ATTACH":
      return "accent"
    case "AMBIGUOUS":
      return "warning"
    default:
      return "neutral"
  }
}
