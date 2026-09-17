/**
 * Force-directed layout, as pure functions.
 *
 * Kept separate from any renderer so the animated canvas and the static
 * snapshot on the home page run the *same* physics — a snapshot that used a
 * different algorithm would drift out of agreement with the version you get by
 * clicking through.
 *
 * The model is Fruchterman-Reingold: repulsion k²/d across every pair,
 * attraction d²/k along edges, with k derived from the drawing area. Deriving
 * the ideal distance from the canvas is what stops a small graph from
 * collapsing into the middle — a fixed repulsion constant loses to the springs
 * as soon as the viewport is large.
 */

import type { GraphEdge, GraphNode } from "./types"

export type Sim = {
  node: GraphNode
  x: number
  y: number
  /** Accumulated displacement for the current step. */
  dx: number
  dy: number
  radius: number
  pinned: boolean
}

export type LayoutState = {
  sims: Sim[]
  index: Map<string, Sim>
  neighbors: Map<string, Set<string>>
  edges: GraphEdge[]
  width: number
  height: number
}

export type LayoutInput = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  /** Tag kinds excluded from the drawing. */
  hiddenKinds?: Set<string>
}

export function radiusFor(node: GraphNode): number {
  const base = node.type === "topic" ? 9 : 5
  const degree = node.degree ?? node.event_count ?? 1
  return base + Math.min(9, Math.sqrt(Math.max(0, degree)) * 2.2)
}

export function visibleNodes(nodes: GraphNode[], hiddenKinds?: Set<string>): GraphNode[] {
  return nodes.filter((node) => {
    if (node.type !== "topic" && node.kind && hiddenKinds?.has(node.kind)) return false
    return true
  })
}

function edgesWithin(edges: GraphEdge[], ids: Set<string>): GraphEdge[] {
  return edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target))
}

/**
 * Build a layout. Passing the previous state reuses node positions, so a poll or
 * a filter change nudges the graph instead of throwing it back to the start.
 */
export function createLayout(input: LayoutInput, width: number, height: number, previous?: LayoutState): LayoutState {
  const nodes = visibleNodes(input.nodes, input.hiddenKinds)
  const ids = new Set(nodes.map((node) => node.id))
  const edges = edgesWithin(input.edges, ids)

  const neighbors = new Map(nodes.map((node) => [node.id, new Set<string>()]))
  for (const edge of edges) {
    neighbors.get(edge.source)?.add(edge.target)
    neighbors.get(edge.target)?.add(edge.source)
  }

  const cx = width / 2
  const cy = height / 2
  const sims = nodes.map((node, i) => {
    const existing = previous?.index.get(node.id)
    if (existing) {
      existing.node = node
      existing.radius = radiusFor(node)
      return existing
    }
    // Seed on a ring so the first steps do not explode out of a single point.
    const angle = (i / Math.max(1, nodes.length)) * Math.PI * 2
    const spread = Math.min(width, height) * 0.32
    return {
      node,
      x: cx + Math.cos(angle) * spread,
      y: cy + Math.sin(angle) * spread,
      dx: 0,
      dy: 0,
      radius: radiusFor(node),
      pinned: false,
    }
  })

  return { sims, index: new Map(sims.map((sim) => [sim.node.id, sim])), neighbors, edges, width, height }
}

/** One physics step. `alpha` is the cooling factor in (0, 1]. */
export function stepLayout(state: LayoutState, alpha: number): void {
  const { sims, index, edges } = state
  const count = Math.max(1, sims.length)
  if (!count) return

  const k = Math.sqrt((state.width * state.height) / count) * 0.42
  const temperature = Math.max(1.5, k * 0.14) * alpha
  const gravity = k * 0.006
  const cx = state.width / 2
  const cy = state.height / 2

  for (const sim of sims) {
    sim.dx = 0
    sim.dy = 0
  }

  for (let i = 0; i < count; i++) {
    const a = sims[i]
    for (let j = i + 1; j < count; j++) {
      const b = sims[j]
      let dx = b.x - a.x
      let dy = b.y - a.y
      let distance = Math.hypot(dx, dy)
      if (distance < 0.01) {
        // Deterministic nudge for coincident nodes.
        dx = i % 2 === 0 ? 0.7 : -0.7
        dy = j % 2 === 0 ? 0.7 : -0.7
        distance = 0.99
      }
      const force = (k * k) / distance
      const ux = dx / distance
      const uy = dy / distance
      a.dx -= ux * force
      a.dy -= uy * force
      b.dx += ux * force
      b.dy += uy * force
    }
  }

  for (const edge of edges) {
    const a = index.get(edge.source)
    const b = index.get(edge.target)
    if (!a || !b) continue
    const dx = b.x - a.x
    const dy = b.y - a.y
    const distance = Math.max(0.01, Math.hypot(dx, dy))
    // Heavier edges (shared entities) pull harder so clusters read as clusters.
    const weight = 1 + Math.min(2, (edge.weight ?? 1) - 1) * 0.6
    const force = ((distance * distance) / k) * weight
    const ux = dx / distance
    const uy = dy / distance
    a.dx += ux * force
    a.dy += uy * force
    b.dx -= ux * force
    b.dy -= uy * force
  }

  for (const sim of sims) {
    // Keeps disconnected components from drifting off-screen.
    sim.dx += (cx - sim.x) * gravity
    sim.dy += (cy - sim.y) * gravity
    if (sim.pinned) continue
    const length = Math.hypot(sim.dx, sim.dy)
    if (length > 0.0001) {
      const step = Math.min(length, temperature) / length
      sim.x += sim.dx * step
      sim.y += sim.dy * step
    }
    // Keep nodes inside the viewport so nothing settles out of reach.
    const pad = sim.radius + 8
    sim.x = Math.min(state.width - pad, Math.max(pad, sim.x))
    sim.y = Math.min(state.height - pad, Math.max(pad, sim.y))
  }

  // Hard-core separation. Forces alone cannot guarantee that wide nodes stop
  // overlapping — a topic with ten edges out-pulls any repulsion constant — so
  // residual overlap is resolved geometrically after the step.
  for (let i = 0; i < count; i++) {
    const a = sims[i]
    for (let j = i + 1; j < count; j++) {
      const b = sims[j]
      let dx = b.x - a.x
      let dy = b.y - a.y
      let distance = Math.hypot(dx, dy)
      const minimum = a.radius + b.radius + 6
      if (distance >= minimum) continue
      if (distance < 0.01) {
        dx = 0.7
        dy = -0.7
        distance = 0.99
      }
      const push = ((minimum - distance) / distance) * 0.5
      if (!a.pinned) {
        a.x -= dx * push
        a.y -= dy * push
      }
      if (!b.pinned) {
        b.x += dx * push
        b.y += dy * push
      }
    }
  }
}

/**
 * Run the layout to completion synchronously. Used by the static snapshot: no
 * animation frames, no timers, one burst of work and then nothing.
 */
export function computeLayout(input: LayoutInput, width: number, height: number, steps = 320): LayoutState {
  const state = createLayout(input, width, height)
  for (let i = 0; i < steps; i++) {
    stepLayout(state, Math.max(0.02, 1 - i / steps))
  }
  return state
}

export function boundsOf(state: LayoutState) {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const sim of state.sims) {
    minX = Math.min(minX, sim.x - sim.radius)
    maxX = Math.max(maxX, sim.x + sim.radius)
    minY = Math.min(minY, sim.y - sim.radius)
    maxY = Math.max(maxY, sim.y + sim.radius)
  }
  return { minX, minY, maxX, maxY }
}

/**
 * The view transform that frames a settled layout inside a box. Shared so the
 * still snapshot and the interactive canvas fill their frame identically —
 * without it the snapshot paints at 1:1 and the graph reads as a small blob in
 * a large empty panel.
 */
export function fitTransform(state: LayoutState, width: number, height: number, padding = 48) {
  const { minX, minY, maxX, maxY } = boundsOf(state)
  const scale = Math.min(
    1.8,
    Math.max(0.2, Math.min(width / (maxX - minX + padding * 2), height / (maxY - minY + padding * 2))),
  )
  return {
    scale,
    x: width / 2 - ((minX + maxX) / 2) * scale,
    y: height / 2 - ((minY + maxY) / 2) * scale,
  }
}

/** A cheap identity for a graph, so callers can cache a layout across polls. */
export function graphSignature(input: LayoutInput): string {
  const hidden = input.hiddenKinds ? [...input.hiddenKinds].sort().join(",") : ""
  const nodes = input.nodes.map((node) => node.id).join(",")
  const edges = input.edges.map((edge) => `${edge.source}>${edge.target}`).join(",")
  return `${input.nodes.length}|${input.edges.length}|${hidden}|${nodes}|${edges}`
}
