/**
 * Shared painting for the knowledge graph. Both the snapshot on the home page
 * and the interactive canvas render through here, so the preview is a faithful
 * still of the version you get when you click through — same colours, same
 * label priorities, same de-collision.
 */

import { nodeSwatch } from "./labels"
import type { LayoutState, Sim } from "./graph-layout"
import type { GraphEdge } from "./types"

export type Palette = {
  surface: string
  label: string
  labelMuted: string
  edge: string
  edgeStrong: string
  selection: string
  swatches: Map<string, string>
}

const SWATCH_NAMES = ["blue", "purple", "yellow", "cyan", "green", "red", "pink", "orange", "gray"]

/**
 * Read the design tokens off the live element so the graph follows the theme.
 * The literals are last-resort fallbacks for a token that failed to resolve —
 * they are never expected to be used.
 */
export function readPalette(element: HTMLElement): Palette {
  const style = getComputedStyle(element)
  const token = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback

  const swatches = new Map<string, string>()
  for (const name of SWATCH_NAMES) {
    swatches.set(`var(--v2-avatar-bg-${name})`, token(`--v2-avatar-bg-${name}`, "#5c5c5cff"))
  }

  return {
    surface: token("--v2-background-bg-base", "#ffffffff"),
    label: token("--v2-text-text-base", "#161616ff"),
    labelMuted: token("--v2-text-text-faint", "#808080ff"),
    edge: token("--v2-border-border-base", "#0000001a"),
    edgeStrong: token("--v2-border-border-strong", "#00000033"),
    selection: token("--v2-text-text-accent", "#034cffff"),
    swatches,
  }
}

function resolveColor(palette: Palette, value: string, fallback: string) {
  if (!value.startsWith("var(")) return value
  return palette.swatches.get(value) ?? fallback
}

export type DrawOptions = {
  palette: Palette
  width: number
  height: number
  scale: number
  offsetX: number
  offsetY: number
  edges: GraphEdge[]
  selectedId?: string
  hoverId?: string
  matches?: Set<string>
  /** Draw every node label, not just the important ones. */
  allLabels?: boolean
}

/**
 * Paint one frame. The caller owns the base transform — it has already applied
 * the device-pixel-ratio scale — and this function only pushes the graph's own
 * translate/scale on top. Resetting the transform here would silently drop the
 * DPR scale and draw everything at half size on a retina screen.
 */
export function drawGraph(context: CanvasRenderingContext2D, state: LayoutState, options: DrawOptions) {
  const { palette, width, height, scale, offsetX, offsetY } = options
  const { sims, index, neighbors } = state
  const focusId = options.hoverId ?? options.selectedId
  const related = focusId ? neighbors.get(focusId) : undefined

  context.save()
  context.clearRect(0, 0, width, height)
  if (sims.length === 0) {
    context.restore()
    return
  }

  context.translate(offsetX, offsetY)
  context.scale(scale, scale)

  for (const edge of options.edges) {
    const a = index.get(edge.source)
    const b = index.get(edge.target)
    if (!a || !b) continue
    const strong = Boolean(edge.weight && edge.weight > 1)
    const inFocus = !focusId || edge.source === focusId || edge.target === focusId
    context.globalAlpha = focusId ? (inFocus ? 0.9 : 0.12) : strong ? 0.75 : 0.4
    context.strokeStyle = strong ? palette.edgeStrong : palette.edge
    context.lineWidth = (strong ? 1.6 : 1) / scale
    context.beginPath()
    context.moveTo(a.x, a.y)
    context.lineTo(b.x, b.y)
    context.stroke()
  }

  for (const sim of sims) {
    const node = sim.node
    const isFocus = node.id === focusId
    const isRelated = related?.has(node.id)
    const isMatch = options.matches?.has(node.id)
    const dimmed = Boolean(focusId) && !isFocus && !isRelated

    context.globalAlpha = dimmed ? 0.28 : 1
    context.beginPath()
    context.arc(sim.x, sim.y, sim.radius, 0, Math.PI * 2)
    context.fillStyle = resolveColor(palette, nodeSwatch(node), "#5c5c5cff")
    context.fill()

    // A ring in the surface colour separates overlapping nodes.
    context.lineWidth = 1.5 / scale
    context.strokeStyle = palette.surface
    context.stroke()

    if (isFocus || isMatch) {
      context.beginPath()
      context.arc(sim.x, sim.y, sim.radius + 3 / scale, 0, Math.PI * 2)
      context.lineWidth = 1.5 / scale
      context.strokeStyle = palette.selection
      context.stroke()
    }
  }

  drawLabels(context, state, options, related)
  context.globalAlpha = 1
  context.restore()
}

function drawLabels(
  context: CanvasRenderingContext2D,
  state: LayoutState,
  options: DrawOptions,
  related: Set<string> | undefined,
) {
  const { palette, scale } = options
  const focusId = options.hoverId ?? options.selectedId
  const showLabels = options.allLabels || scale > 0.55

  // Lower rank wins the space when two labels would overlap.
  const rank = (sim: Sim) => {
    const node = sim.node
    if (node.id === focusId) return 0
    if (options.matches?.has(node.id)) return 1
    if (node.type === "topic") return 2
    if (related?.has(node.id)) return 3
    return 4
  }
  const order = [...state.sims].sort((a, b) => rank(a) - rank(b))

  context.font = `${12 / scale}px "Inter", sans-serif`
  context.textBaseline = "middle"
  const lineHeight = 13 / scale
  const taken: Array<{ x1: number; y1: number; x2: number; y2: number }> = []

  for (const sim of order) {
    const node = sim.node
    const isFocus = node.id === focusId
    const isMatch = options.matches?.has(node.id)
    const dimmed = Boolean(focusId) && !isFocus && !(related?.has(node.id) ?? false)
    if (dimmed) continue

    const hub = (node.degree ?? node.event_count ?? 0) > 2
    if (!isFocus && !isMatch && !hub && node.type !== "topic") continue
    if (!isFocus && !isMatch && !showLabels && node.type !== "topic") continue

    const gap = 5 / scale
    const x1 = sim.x + sim.radius + gap
    const width = context.measureText(node.label).width
    const y1 = sim.y - lineHeight / 2
    const box = { x1, y1, x2: x1 + width, y2: y1 + lineHeight }
    if (!(isFocus || isMatch) && taken.some((r) => r.x1 < box.x2 && r.x2 > box.x1 && r.y1 < box.y2 && r.y2 > box.y1))
      continue
    taken.push(box)

    context.globalAlpha = 1
    // A one-pixel offset copy in the surface colour keeps the label legible
    // where edges run underneath it.
    context.fillStyle = palette.surface
    context.fillText(node.label, x1 + 1 / scale, sim.y + 1 / scale)
    context.fillStyle =
      isFocus || isMatch ? palette.selection : node.type === "topic" ? palette.label : palette.labelMuted
    context.fillText(node.label, x1, sim.y)
  }
}
