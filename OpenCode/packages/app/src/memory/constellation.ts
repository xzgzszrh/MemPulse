/**
 * The memory constellation on the home page: topics and the entities they
 * share, laid out on a sphere and drawn with a light perspective camera.
 *
 * Deliberately restrained so it reads as OpenCode rather than a demo: colours
 * come from the live theme tokens (the same swatches the 2D graph uses), depth
 * is conveyed by size and alpha rather than glow, labels sit in the same quiet
 * pills as the rest of the workbench, and motion is a slow orbit the user can
 * take over by dragging. Honors `prefers-reduced-motion`.
 */

import { readPalette, type Palette } from "./graph-render"
import { nodeSwatch } from "./labels"
import type { Graph, GraphNode } from "./types"

export type SceneNode = {
  id: string
  label: string
  type: "topic" | "entity"
  kind?: string
  state?: string
  color: string
  x: number
  y: number
  z: number
  radius: number
  /** Number of edges touching the node — drives entity size and label priority. */
  degree: number
  eventCount: number
  goal?: string
  phase: number
}

export type SceneEdge = { a: number; b: number; weight: number; background: boolean }

export type Scene = { nodes: SceneNode[]; edges: SceneEdge[]; adjacency: Map<number, Set<number>> }

const TOPIC_ORBIT = 178
const GOLDEN = Math.PI * (3 - Math.sqrt(5))

function hash(value: string) {
  let h = 2166136261
  for (let i = 0; i < value.length; i++) h = Math.imul(h ^ value.charCodeAt(i), 16777619)
  return (h >>> 0) / 4294967295
}

function resolveSwatch(palette: Palette, node: Pick<GraphNode, "type" | "kind" | "state">) {
  const swatch = nodeSwatch(node)
  return palette.swatches.get(swatch) ?? palette.labelMuted
}

/** Fibonacci sphere: evenly spread points for any count, no clumping at the poles. */
function spherePoint(index: number, total: number, radius: number) {
  const y = total === 1 ? 0 : 1 - (2 * (index + 0.5)) / total
  const ring = Math.sqrt(Math.max(0, 1 - y * y))
  const theta = GOLDEN * index
  return { x: Math.cos(theta) * ring * radius, y: y * radius * 0.82, z: Math.sin(theta) * ring * radius }
}

function normalize(v: { x: number; y: number; z: number }) {
  const len = Math.hypot(v.x, v.y, v.z) || 1
  return { x: v.x / len, y: v.y / len, z: v.z / len }
}

function tangentBasis(n: { x: number; y: number; z: number }) {
  const helper = Math.abs(n.y) < 0.9 ? { x: 0, y: 1, z: 0 } : { x: 1, y: 0, z: 0 }
  const u = normalize({
    x: n.y * helper.z - n.z * helper.y,
    y: n.z * helper.x - n.x * helper.z,
    z: n.x * helper.y - n.y * helper.x,
  })
  const v = { x: n.y * u.z - n.z * u.y, y: n.z * u.x - n.x * u.z, z: n.x * u.y - n.y * u.x }
  return { u, v }
}

export function buildScene(graph: Graph, palette: Palette): Scene {
  const topics = graph.nodes
    .filter((node) => node.type === "topic")
    .sort((a, b) => (b.event_count ?? 0) - (a.event_count ?? 0))
  const entities = graph.nodes.filter((node) => node.type === "entity")
  const nodes: SceneNode[] = []
  const index = new Map<string, number>()

  topics.forEach((topic, i) => {
    const point = spherePoint(i, topics.length, TOPIC_ORBIT)
    index.set(topic.id, nodes.length)
    nodes.push({
      id: topic.id,
      label: topic.label,
      type: "topic",
      state: topic.state,
      color: resolveSwatch(palette, topic),
      ...point,
      radius: 8 + Math.min(6, (topic.event_count ?? 0) * 0.55),
      degree: 0,
      eventCount: topic.event_count ?? 0,
      goal: topic.goal || topic.summary,
      phase: hash(topic.id) * Math.PI * 2,
    })
  })

  // Which topics each entity hangs off, from the topic→entity edges.
  const owners = new Map<string, string[]>()
  for (const edge of graph.edges) {
    if (edge.type !== "topic_tag") continue
    const list = owners.get(edge.target) ?? []
    list.push(edge.source)
    owners.set(edge.target, list)
  }

  const ringSlot = new Map<string, number>()
  entities.forEach((entity) => {
    const parents = (owners.get(entity.id) ?? []).map((id) => index.get(id)).filter((i): i is number => i !== undefined)
    let position: { x: number; y: number; z: number }
    if (parents.length === 0) {
      const point = spherePoint(entities.indexOf(entity), entities.length, TOPIC_ORBIT * 1.45)
      position = point
    } else if (parents.length === 1) {
      // Exclusive entities orbit their topic on the sphere's outside, spread by the golden angle.
      const topic = nodes[parents[0]]
      const slot = ringSlot.get(topic.id) ?? 0
      ringSlot.set(topic.id, slot + 1)
      const outward = normalize(topic)
      const { u, v } = tangentBasis(outward)
      const angle = GOLDEN * slot + hash(entity.id) * 0.6
      const ring = 46 + (slot % 3) * 15 + hash(entity.id + "r") * 8
      const lift = 18 + (slot % 2) * 12
      position = {
        x: topic.x + outward.x * lift + (u.x * Math.cos(angle) + v.x * Math.sin(angle)) * ring,
        y: topic.y + outward.y * lift + (u.y * Math.cos(angle) + v.y * Math.sin(angle)) * ring,
        z: topic.z + outward.z * lift + (u.z * Math.cos(angle) + v.z * Math.sin(angle)) * ring,
      }
    } else {
      // Shared entities sit between the topics that share them — the visible seams of the graph.
      const centroid = parents.reduce(
        (acc, i) => ({
          x: acc.x + nodes[i].x / parents.length,
          y: acc.y + nodes[i].y / parents.length,
          z: acc.z + nodes[i].z / parents.length,
        }),
        { x: 0, y: 0, z: 0 },
      )
      const jitter = (hash(entity.id) - 0.5) * 26
      const scale = parents.length >= 3 ? 0.62 : 0.86
      position = {
        x: centroid.x * scale + jitter,
        y: centroid.y * scale + (hash(entity.id + "y") - 0.5) * 26,
        z: centroid.z * scale - jitter,
      }
    }
    index.set(entity.id, nodes.length)
    nodes.push({
      id: entity.id,
      label: entity.label,
      type: "entity",
      kind: entity.kind,
      color: resolveSwatch(palette, entity),
      ...position,
      radius: 3 + Math.min(3.5, (entity.degree ?? 1) * 0.9),
      degree: 0,
      eventCount: 0,
      phase: hash(entity.id) * Math.PI * 2,
    })
  })

  const edges: SceneEdge[] = []
  const adjacency = new Map<number, Set<number>>()
  const link = (a: number, b: number) => {
    if (!adjacency.has(a)) adjacency.set(a, new Set())
    if (!adjacency.has(b)) adjacency.set(b, new Set())
    adjacency.get(a)!.add(b)
    adjacency.get(b)!.add(a)
  }
  const seen = new Set<string>()
  for (const edge of graph.edges) {
    const a = index.get(edge.source)
    const b = index.get(edge.target)
    if (a === undefined || b === undefined || a === b) continue
    const key = a < b ? `${a}:${b}` : `${b}:${a}`
    if (seen.has(key)) continue
    seen.add(key)
    const weight = edge.type === "topic_topic" ? Math.min(3, edge.weight ?? 1) : edge.type === "co_occurrence" ? 0.6 : 1
    edges.push({ a, b, weight, background: nodes[a].type !== "topic" || nodes[b].type !== "topic" })
    link(a, b)
    nodes[a].degree += 1
    nodes[b].degree += 1
  }

  // Topic-topic links duplicate the shared-entity paths. Keep a sparse strong
  // backbone at rest; hovering still exposes every incident relationship.
  const degree = new Map<number, number>()
  const span = (edge: SceneEdge) =>
    Math.hypot(nodes[edge.a].x - nodes[edge.b].x, nodes[edge.a].y - nodes[edge.b].y, nodes[edge.a].z - nodes[edge.b].z)
  for (const edge of edges
    .filter((item) => !item.background)
    .sort((a, b) => b.weight - a.weight || span(a) - span(b))) {
    if ((degree.get(edge.a) ?? 0) >= 3 || (degree.get(edge.b) ?? 0) >= 3) continue
    edge.background = true
    degree.set(edge.a, (degree.get(edge.a) ?? 0) + 1)
    degree.set(edge.b, (degree.get(edge.b) ?? 0) + 1)
  }
  return { nodes, edges, adjacency }
}

export type ConstellationOptions = {
  scene: () => Scene
  reducedMotion: () => boolean
  onHover: (node: SceneNode | undefined, at: { x: number; y: number }) => void
  onSelect: (node: SceneNode) => void
  /** Optional local benchmark observer; the application does not enable it. */
  onFrame?: (frame: { durationMs: number; edgeStrokes: number; labels: number; pixels: number }) => void
}

type Projected = { node: SceneNode; index: number; sx: number; sy: number; scale: number; depth: number }

export function mountConstellation(canvas: HTMLCanvasElement, container: HTMLElement, options: ConstellationOptions) {
  const context = canvas.getContext("2d")
  if (!context) return Object.assign(() => {}, { invalidate: () => {} })
  const ctx = context

  let palette = readPalette(container)
  let font = getComputedStyle(container).fontFamily || "Inter, sans-serif"
  let width = 0
  let height = 0
  let dpr = 1

  // Camera. Yaw drifts on its own; the pointer nudges pitch/yaw a little and a
  // drag takes over completely. Zoom is the camera distance.
  let yaw = 0.55
  let pitch = 0.22
  let distance = 560
  let targetDistance = distance
  let dragging = false
  let dragMoved = false
  let lastX = 0
  let lastY = 0
  let pointerX = -1e5
  let pointerY = -1e5
  let inside = false
  let hovered = -1
  let raf = 0
  let last = performance.now()
  const projected: Projected[] = []
  let currentScene: Scene | undefined
  let byIndex: Projected[] = []
  const labelCache = new Map<string, { text: string; font: string; width: number; height: number }>()
  let dirty = true
  let disposed = false
  let focused = document.hasFocus()
  let nextFrame = 0
  let hoverTime = 0
  let hoverNotice: { node: SceneNode; x: number; y: number } | undefined

  function invalidate() {
    dirty = true
    if (disposed || document.hidden || raf) return
    nextFrame = 0
    raf = requestAnimationFrame(render)
  }

  const resize = () => {
    const rect = container.getBoundingClientRect()
    width = rect.width
    height = rect.height
    dpr = Math.min(2, window.devicePixelRatio || 1, Math.sqrt(6_000_000 / Math.max(1, width * height)))
    canvas.width = Math.max(1, Math.floor(width * dpr))
    canvas.height = Math.max(1, Math.floor(height * dpr))
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    labelCache.clear()
    dirty = true
  }
  resize()
  const observer = new ResizeObserver(() => {
    resize()
    invalidate()
  })
  observer.observe(container)

  const refreshTheme = () => {
    palette = readPalette(container)
    font = getComputedStyle(container).fontFamily || font
    labelCache.clear()
    invalidate()
  }
  const themeObserver = new MutationObserver(refreshTheme)
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class", "data-theme", "data-color-scheme", "style"],
  })
  const media = window.matchMedia("(prefers-color-scheme: dark)")
  media.addEventListener("change", refreshTheme)
  document.fonts.addEventListener("loadingdone", refreshTheme)

  // Pointer handling lives on the canvas only. The cards and buttons are later
  // siblings stacked above it, so their clicks never reach here — and this
  // canvas never captures a pointer that started on one of them.
  const onPointerDown = (event: PointerEvent) => {
    if (event.button !== 0) return
    dragging = true
    dragMoved = false
    lastX = event.clientX
    lastY = event.clientY
    canvas.setPointerCapture?.(event.pointerId)
    invalidate()
  }
  const onPointerMove = (event: PointerEvent) => {
    const rect = canvas.getBoundingClientRect()
    pointerX = event.clientX - rect.left
    pointerY = event.clientY - rect.top
    inside = true
    invalidate()
    if (!dragging) return
    const dx = event.clientX - lastX
    const dy = event.clientY - lastY
    if (Math.abs(dx) + Math.abs(dy) > 2) dragMoved = true
    yaw += dx * 0.006
    pitch = Math.max(-1.2, Math.min(1.2, pitch + dy * 0.006))
    lastX = event.clientX
    lastY = event.clientY
  }
  const onPointerUp = (event: PointerEvent) => {
    if (!dragging) return
    dragging = false
    canvas.releasePointerCapture?.(event.pointerId)
    if (!dragMoved && hovered >= 0) options.onSelect(projected[hovered].node)
    invalidate()
  }
  const onPointerLeave = () => {
    inside = false
    pointerX = -1e5
    pointerY = -1e5
    invalidate()
  }
  const onWheel = (event: WheelEvent) => {
    targetDistance = Math.max(380, Math.min(1000, targetDistance + event.deltaY * 0.6))
    invalidate()
  }
  canvas.addEventListener("pointerdown", onPointerDown)
  canvas.addEventListener("pointermove", onPointerMove)
  canvas.addEventListener("pointerup", onPointerUp)
  canvas.addEventListener("pointercancel", onPointerUp)
  canvas.addEventListener("pointerleave", onPointerLeave)
  canvas.addEventListener("wheel", onWheel, { passive: true })

  function labelLayout(node: SceneNode, size: number) {
    const text = node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label
    const key = `${font}:${node.type}:${size}:${text}`
    const cached = labelCache.get(key)
    if (cached) return cached
    ctx.font = `${node.type === "topic" ? 500 : 400} ${size}px ${font}`
    const width = Math.ceil(ctx.measureText(text).width + 14)
    const height = size + 8
    const layout = { text, font: ctx.font, width, height }
    if (labelCache.size >= 768) labelCache.delete(labelCache.keys().next().value!)
    labelCache.set(key, layout)
    return layout
  }

  function render(now: number) {
    raf = 0
    if (disposed || document.hidden) return
    if (now + 0.5 < nextFrame) {
      raf = requestAnimationFrame(render)
      return
    }
    const reduced = options.reducedMotion()
    const zooming = Math.abs(targetDistance - distance) > 0.1
    if (!dirty && reduced && !dragging && !zooming) return
    const started = options.onFrame ? performance.now() : 0
    let edgeStrokes = 0
    const dt = Math.min(0.05, (now - last) / 1000)
    last = now
    const interval = 1000 / 60
    // Advance the deadline instead of restarting it on each vsync; otherwise
    // slight vsync jitter turns the 60 fps budget into 40 fps.
    nextFrame = nextFrame > 0 && now - nextFrame < interval ? nextFrame + interval : now + interval
    if (width <= 0 || height <= 0) return

    if (!dragging && !reduced) yaw += dt * (inside ? 0.04 : 0.11)
    distance += (targetDistance - distance) * Math.min(1, dt * 8)

    const scene = options.scene()
    const { nodes, edges, adjacency } = scene
    if (scene !== currentScene) {
      currentScene = scene
      byIndex = nodes.map((node, index) => ({ node, index, sx: 0, sy: 0, scale: 0, depth: 0 }))
      labelCache.clear()
    }
    ctx.clearRect(0, 0, width, height)

    const cx = width / 2
    const cy = height / 2
    const parallaxX = inside && !dragging && !reduced ? ((pointerX - cx) / Math.max(1, cx)) * 0.12 : 0
    const parallaxY = inside && !dragging && !reduced ? ((pointerY - cy) / Math.max(1, cy)) * 0.1 : 0
    const cp = Math.cos(pitch + parallaxY)
    const sp = Math.sin(pitch + parallaxY)
    const cyaw = Math.cos(yaw + parallaxX)
    const syaw = Math.sin(yaw + parallaxX)
    const focal = 520
    // The scene is laid out at a fixed radius; positions stretch to the
    // viewport so the constellation fills the page behind the cards and the
    // mark, while node size and label size stay a function of depth alone.
    const extentX = TOPIC_ORBIT * 2 * (focal / distance)
    const extentY = extentX * 0.82
    const spreadX = Math.max(1, Math.min(3.2, (width * 0.86) / extentX))
    const spreadY = Math.max(1, Math.min(3.2, (height * 0.92) / extentY))

    projected.length = 0
    nodes.forEach((node, index) => {
      const x1 = node.x * cyaw + node.z * syaw
      const z1 = -node.x * syaw + node.z * cyaw
      const y2 = node.y * cp - z1 * sp
      const z2 = node.y * sp + z1 * cp
      const dz = distance + z2
      const item = byIndex[index]
      if (dz <= 40) {
        item.scale = 0
        return
      }
      const scale = focal / dz
      item.sx = cx + x1 * scale * spreadX
      item.sy = cy + y2 * scale * spreadY
      item.scale = scale
      item.depth = z2
      projected.push(item)
    })
    projected.sort((a, b) => b.depth - a.depth)

    // Hover: nearest node under the pointer, generous for small entities.
    let next = -1
    let best = 18
    for (let i = inside ? projected.length - 1 : -1; i >= 0; i--) {
      const p = projected[i]
      const d = Math.hypot(p.sx - pointerX, p.sy - pointerY)
      const reach = p.node.radius * p.scale + (p.node.type === "topic" ? 10 : 7)
      if (d < reach && d < best) {
        best = d
        next = i
      }
    }
    hovered = next
    const hit = next >= 0 ? projected[next] : undefined
    if (!hit && hoverNotice) {
      options.onHover(undefined, { x: 0, y: 0 })
      hoverNotice = undefined
    }
    if (
      hit &&
      (hoverNotice?.node !== hit.node ||
        (now - hoverTime >= 1000 / 30 && Math.hypot(hit.sx - hoverNotice.x, hit.sy - hoverNotice.y) >= 1))
    ) {
      hoverNotice = { node: hit.node, x: hit.sx, y: hit.sy }
      hoverTime = now
      options.onHover(hit.node, { x: hit.sx, y: hit.sy })
    }
    const hoveredIndex = hovered >= 0 ? projected[hovered].index : -1
    const neighbours = hoveredIndex >= 0 ? adjacency.get(hoveredIndex) : undefined

    const fade = (depth: number) => Math.max(0.18, Math.min(1, 1 - (depth + 80) / 640))

    // Keep simple independent strokes: large intersecting paths cause raster
    // stalls on some native canvas backends. Offscreen segments are skipped.
    ctx.lineCap = "round"
    for (const edge of edges) {
      const a = byIndex[edge.a]
      const b = byIndex[edge.b]
      if (!a?.scale || !b?.scale) continue
      if (
        (a.sx < 0 && b.sx < 0) ||
        (a.sx > width && b.sx > width) ||
        (a.sy < 0 && b.sy < 0) ||
        (a.sy > height && b.sy > height)
      )
        continue
      const touching = hoveredIndex >= 0 && (edge.a === hoveredIndex || edge.b === hoveredIndex)
      if (!edge.background && !touching) continue
      const alpha = fade((a.depth + b.depth) / 2)
      const strong = edge.weight > 1
      ctx.strokeStyle = touching ? palette.selection : strong ? palette.edgeStrong : palette.edge
      ctx.globalAlpha = touching ? 0.6 : alpha * (strong ? 0.26 : 0.18) * (hoveredIndex >= 0 ? 0.3 : 1)
      ctx.lineWidth = touching ? 1.1 : strong ? 0.65 : 0.55
      ctx.beginPath()
      ctx.moveTo(a.sx, a.sy)
      ctx.lineTo(b.sx, b.sy)
      ctx.stroke()
      edgeStrokes += 1
    }

    // Nodes, far to near.
    const placedLabels: Array<{ x: number; y: number; w: number; h: number }> = []
    const labelQueue: Array<{ p: Projected; priority: number }> = []
    for (const p of projected) {
      const { node, sx, sy, scale, depth, index } = p
      const isHovered = index === hoveredIndex
      const isNeighbour = neighbours?.has(index) ?? false
      const alpha = fade(depth) * (hoveredIndex >= 0 && !isHovered && !isNeighbour ? 0.55 : 1)
      const breathe = reduced || node.type !== "topic" ? 1 : 1 + Math.sin(now / 900 + node.phase) * 0.035
      const r = node.radius * scale * breathe * (isHovered ? 1.18 : 1)
      if (sx + r + 4 < 0 || sx - r - 4 > width || sy + r + 4 < 0 || sy - r - 4 > height) continue

      if (node.type === "topic") {
        ctx.beginPath()
        ctx.arc(sx, sy, r + 4 * scale, 0, Math.PI * 2)
        ctx.globalAlpha = 0.16 * alpha
        ctx.fillStyle = node.color
        ctx.fill()
      }
      ctx.beginPath()
      ctx.arc(sx, sy, r, 0, Math.PI * 2)
      ctx.globalAlpha = alpha
      ctx.fillStyle = node.color
      ctx.fill()
      // A surface-coloured ring separates overlapping nodes without a hard outline.
      ctx.lineWidth = node.type === "topic" ? 1.5 : 1
      ctx.globalAlpha = 0.9 * alpha
      ctx.strokeStyle = palette.surface
      ctx.stroke()
      if (isHovered) {
        ctx.beginPath()
        ctx.arc(sx, sy, r + 3, 0, Math.PI * 2)
        ctx.lineWidth = 1.2
        ctx.globalAlpha = 0.9
        ctx.strokeStyle = palette.selection
        ctx.stroke()
      }

      if (!node.label) continue
      if (node.type === "topic") labelQueue.push({ p, priority: 2 + (isHovered ? 10 : 0) - depth / 1000 })
      else if (isHovered || isNeighbour || (node.degree >= 2 && scale > 1.05))
        labelQueue.push({ p, priority: (isHovered ? 10 : isNeighbour ? 1.5 : 0.5) - depth / 1000 })
    }

    // Labels: front and hovered first; anything that would overlap is dropped.
    labelQueue.sort((a, b) => b.priority - a.priority)
    for (const { p } of labelQueue) {
      const { node, sx, sy, scale, depth, index } = p
      const isHovered = index === hoveredIndex
      const isNeighbour = neighbours?.has(index) ?? false
      const size = node.type === "topic" ? Math.round(12 * Math.min(1.15, Math.max(0.85, scale))) : 11
      const layout = labelLayout(node, size)
      const w = layout.width
      const h = layout.height
      const x = sx - w / 2
      const y = sy + node.radius * scale + 8
      if (y > height || y + h < 0 || x > width || x + w < 0) continue
      if (placedLabels.some((box) => x < box.x + box.w && x + w > box.x && y < box.y + box.h && y + h > box.y)) continue
      placedLabels.push({ x, y, w, h })
      const alpha = fade(depth) * (hoveredIndex >= 0 && !isHovered && !isNeighbour ? 0.6 : 1)
      ctx.beginPath()
      ctx.roundRect(x, y, w, h, 6)
      ctx.globalAlpha = 0.92 * alpha
      ctx.fillStyle = palette.surface
      ctx.fill()
      ctx.globalAlpha = alpha
      ctx.lineWidth = 1
      ctx.strokeStyle = isHovered ? palette.selection : palette.edgeStrong
      ctx.stroke()
      ctx.font = layout.font
      ctx.fillStyle = node.type === "topic" || isHovered ? palette.label : palette.labelMuted
      ctx.textAlign = "center"
      ctx.textBaseline = "middle"
      ctx.fillText(layout.text, sx, y + h / 2 + 0.5)
    }
    ctx.globalAlpha = 1
    dirty = false
    options.onFrame?.({
      durationMs: performance.now() - started,
      edgeStrokes,
      labels: placedLabels.length,
      pixels: canvas.width * canvas.height,
    })
    if (focused && (!reduced || dragging || Math.abs(targetDistance - distance) > 0.1))
      raf = requestAnimationFrame(render)
  }
  const resume = () => {
    focused = document.hasFocus()
    last = performance.now()
    invalidate()
  }
  const pause = () => {
    focused = false
    cancelAnimationFrame(raf)
    raf = 0
  }
  const visibility = () => (document.hidden ? pause() : resume())
  window.addEventListener("focus", resume)
  window.addEventListener("blur", pause)
  document.addEventListener("visibilitychange", visibility)
  invalidate()

  return Object.assign(
    () => {
      disposed = true
      cancelAnimationFrame(raf)
      observer.disconnect()
      themeObserver.disconnect()
      media.removeEventListener("change", refreshTheme)
      document.fonts.removeEventListener("loadingdone", refreshTheme)
      window.removeEventListener("focus", resume)
      window.removeEventListener("blur", pause)
      document.removeEventListener("visibilitychange", visibility)
      labelCache.clear()
      canvas.removeEventListener("pointerdown", onPointerDown)
      canvas.removeEventListener("pointermove", onPointerMove)
      canvas.removeEventListener("pointerup", onPointerUp)
      canvas.removeEventListener("pointercancel", onPointerUp)
      canvas.removeEventListener("pointerleave", onPointerLeave)
      canvas.removeEventListener("wheel", onWheel)
    },
    { invalidate },
  )
}

/** A quiet placeholder constellation for an empty workspace, so the page is never blank. */
export function placeholderGraph(): Graph {
  const topics = ["新会话会在这里生长", "话题", "偏好", "文件", "决定"]
  const nodes: Graph["nodes"] = topics.map((label, i) => ({
    id: `placeholder_topic_${i}`,
    label: i === 0 ? label : "",
    type: "topic",
    state: "archived",
    event_count: 1,
    size: 20,
  }))
  const edges: Graph["edges"] = []
  for (let i = 1; i < topics.length; i++) {
    for (let j = 0; j < 3; j++) {
      const id = `placeholder_entity_${i}_${j}`
      nodes.push({ id, label: "", type: "entity", kind: "keyword", degree: 1, size: 12 })
      edges.push({ id: `pe_${i}_${j}`, source: `placeholder_topic_${i}`, target: id, type: "topic_tag" })
    }
  }
  return { nodes, edges, stats: { topics: 0, entities: 0, relations: 0 } }
}
