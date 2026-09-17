/**
 * Payload shapes returned by the local MemPulse service over the desktop
 * memory bridge. Field names mirror the Python models so a change on that side
 * shows up here as a compiler error rather than a blank panel.
 */

export type Workspace = "demo" | "personal"

export type TagKind = "person" | "resource" | "keyword" | "time" | "vector"

export type Tag = {
  kind: TagKind | string
  canonical: string
  value: string
  status?: string
  label?: string
  confidence?: number
  source_event_ids?: string[]
}

export type TopicState = "active" | "incomplete" | "archived" | string

export type Topic = {
  topic_id: string
  title: string
  goal?: string
  summary?: string
  state: TopicState
  revision: number
  event_ids: string[]
  updated_at?: string
  created_at?: string
  tags: Tag[]
  metadata?: Record<string, unknown>
}

export type SourceType = "conversation" | "tool" | "configuration" | string
export type EventStatus = "success" | "failed" | "pending" | string

export type MemoryEvent = {
  event_id: string
  topic_id: string
  topic_title: string
  content: string
  occurred_at: string
  source_type: SourceType
  status: EventStatus
  is_fallback?: boolean
  tool?: string
  app?: string
  metadata?: Record<string, unknown>
}

export type RestoreFieldStatus = "present" | "missing" | "conflicted" | string

export type RestoreField = {
  name: string
  value: unknown
  status: RestoreFieldStatus
  evidence_event_ids?: string[]
}

export type Checkpoint = {
  found?: boolean
  checkpoint_id?: string
  topic_id?: string
  revision?: number
  summary?: string
  created_at?: string
  state?: Record<string, unknown>
}

export type RestorePack = {
  topic_id: string
  title?: string
  overview?: string
  fields: RestoreField[]
  events: MemoryEvent[]
  directory?: MemoryEvent[]
  missing: string[]
  topic_revision?: number
  checkpoint?: Checkpoint
  embedding_backend?: string
  fingerprint?: string
}

export type Preference = {
  id?: string
  pref_key: string
  value: unknown
  reason?: string
  scope_type?: string
  scope_id?: string
  choice_type?: string
  valid_from?: string
  valid_to?: string
  status?: string
  created_at?: string
  evidence_event_id?: string
}

export type Knowledge = {
  id?: string
  knowledge_key: string
  value: unknown
  reason?: string
  scope_type?: string
  scope_id?: string
  valid_from?: string
  valid_to?: string
  supersedes?: string
  disputed?: boolean
  dispute_reason?: string
  status?: string
  created_at?: string
  evidence_event_id?: string
}

export type CheckpointRecord = {
  checkpoint_id?: string
  topic_id: string
  created_at: string
  revision?: number
  summary?: string
  state?: Record<string, unknown>
}

export type TombstoneReceipt = {
  tombstone_id?: string
  target_type: "event" | "field" | "topic" | string
  target_id: string
  scope?: Record<string, unknown>
  requested_by?: string
  status: "blocked" | "processing" | "processed" | string
  reason?: string
  created_at: string
}

export type Governance = {
  preferences: Preference[]
  knowledge: Knowledge[]
  checkpoints: CheckpointRecord[]
  receipts: TombstoneReceipt[]
}

export type SdkStatus = {
  backend?: string
  status?: string
  model?: string
  dimension?: number
  message?: string
}

export type Health = {
  ok?: boolean
  service?: string
  storage?: string
  db?: string
  scope?: string
  topiccore?: boolean
  embedding_backend?: string
  sdk_status?: SdkStatus
  schema_version?: number
  index_policy?: string
}

export type Stats = {
  topics: number
  events: number
  tags: number
}

export type Bootstrap = {
  topics: Topic[]
  events: MemoryEvent[]
  governance: Governance
  health: Health
  workspace: Workspace
  stats: Stats
  bindings?: Array<{ session_id: string; project_ref: string; topic_id: string; confirmed_at: string }>
}

export type MemoryOperationKind =
  | "create_topic"
  | "bind_topic"
  | "remember"
  | "rename_topic"
  | "checkpoint"
  | "forget"
  | "forget_field"
  | "move"
  | "merge"
  | "split"
  | "update_tags"
  | "import_demo"
export type MemoryOperation = {
  id: string
  kind: MemoryOperationKind
  status: "pending" | "executing" | "applied" | "rejected" | "failed"
  fingerprint: string
  payload: Record<string, unknown>
  preview: { fields: Array<{ key: string; value: string }>; tags: Tag[]; affected_events: number }
  result?: Record<string, unknown>
  error?: string
}

export type GraphNode = {
  id: string
  label: string
  type: "topic" | "entity" | string
  kind?: TagKind | string
  canonical?: string
  state?: TopicState
  revision?: number
  goal?: string
  summary?: string
  event_count?: number
  degree?: number
  tags?: string[]
  size: number
}

export type GraphEdgeType = "topic_tag" | "topic_topic" | "co_occurrence" | string

export type GraphEdge = {
  id: string
  source: string
  target: string
  type: GraphEdgeType
  kind?: string
  weight?: number
  shared?: string[]
  label?: string
}

export type Graph = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: { topics: number; entities: number; relations: number }
}

export type SearchHit = {
  event_id: string
  topic_id?: string
  topic_title?: string
  content?: string
  occurred_at?: string
  source_type?: SourceType
  status?: EventStatus
  score?: number
}

export type SearchResult = {
  query: string
  results: SearchHit[]
  truncated?: boolean
  backend?: string
  elapsed_ms?: number
  route?: Route
}

export type Route = {
  route: "NEW" | "RESUME" | "ATTACH" | "AMBIGUOUS" | string
  topic_id?: string | null
  candidates?: Array<{ topic_id: string; title?: string; score?: number }>
  embedding_backend?: string
}

export type Relation = {
  relation_id?: string
  person_id?: string
  display_name?: string
  event_count?: number
  events?: MemoryEvent[]
  [key: string]: unknown
}

export type ForgetReceipt = {
  tombstone_id?: string
  status?: string
  target_type?: string
  target_id?: string
  reason?: string
}

/** The memory sections the home page can show. Order here is sidebar order. */
export const MEMORY_SECTIONS = ["overview", "topics", "graph", "recent", "events", "governance", "health"] as const

export type MemorySection = (typeof MEMORY_SECTIONS)[number]

export function isMemorySection(value: string): value is MemorySection {
  return (MEMORY_SECTIONS as readonly string[]).includes(value)
}
