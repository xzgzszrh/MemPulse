import { createEffect, createSignal, onCleanup, onMount } from "solid-js"
import { createLayout, fitTransform, stepLayout, type LayoutState, type Sim } from "../graph-layout"
import { drawGraph, readPalette, type Palette } from "../graph-render"
import type { Graph, GraphNode } from "../types"

/**
 * The interactive knowledge graph.
 *
 * Layout and painting live in `graph-layout` and `graph-render` so the static
 * snapshot on the home page runs exactly the same physics and produces exactly
 * the same picture. This file owns only what makes it *interactive*: dragging,
 * panning, zooming, hit testing and the animation budget.
 *
 * The simulation converges against a wall-clock budget rather than a per-frame
 * decay. A fixed decay made settling depend on how fast the machine could paint
 * — on a slow compositor the graph stayed hot for tens of seconds.
 */

export type GraphController = {
  /** Re-run the layout from scratch. */
  reset: () => void
  /** Center the viewport on a node and select it. */
  focus: (id: string) => void
  /** Multiply the current zoom. */
  zoom: (factor: number) => void
}

export function createGraphController() {
  let impl: GraphController | undefined
  return {
    controller: {
      reset: () => impl?.reset(),
      focus: (id: string) => impl?.focus(id),
      zoom: (factor: number) => impl?.zoom(factor),
    } satisfies GraphController,
    attach: (next: GraphController) => {
      impl = next
    },
  }
}

const HIT_SLOP = 6
const SETTLE_MS = 1500
const FRAME_MS = 16.7
const MAX_STEPS_PER_FRAME = 4
const REHEAT_MS = 400

export function GraphCanvas(props: {
  data: Graph
  selectedId?: string
  hiddenKinds?: Set<string>
  /** Node ids to emphasise, e.g. the current search hit. */
  matches?: Set<string>
  onSelect?: (node: GraphNode | undefined) => void
  onReady?: (controller: GraphController) => void
  class?: string
}) {
  let canvas: HTMLCanvasElement | undefined
  let container: HTMLDivElement | undefined
  let frame: number | undefined
  let palette: Palette | undefined

  let state: LayoutState = createLayout({ nodes: [], edges: [] }, 0, 0)
  let alpha = 1
  let settleRemaining = 0
  let lastFrameAt = 0
  // Once the user pans or zooms, auto-framing would fight them.
  let userAdjusted = false
  let width = 0
  let height = 0

  const [view, setView] = createSignal({ x: 0, y: 0, scale: 1 })
  const [hoverId, setHoverId] = createSignal<string | undefined>()

  let dragging: { sim: Sim; moved: boolean } | undefined
  let panning: { startX: number; startY: number; originX: number; originY: number } | undefined
  let pointerStart: { x: number; y: number } | undefined

  function rebuild() {
    state = createLayout(
      { nodes: props.data.nodes, edges: props.data.edges, hiddenKinds: props.hiddenKinds },
      width,
      height,
      state,
    )
    heat()
  }

  /** Restart the layout budget; the physics cools down over SETTLE_MS. */
  function heat(duration = SETTLE_MS) {
    settleRemaining = duration
    lastFrameAt = 0
    alpha = 1
    schedule()
  }

  /** Frame the settled graph, so a small graph does not sit in a large empty canvas. */
  function fitToContent() {
    if (!state.sims.length || width === 0 || height === 0) return
    setView(fitTransform(state, width, height))
  }

  /**
   * One animation loop drives both simulation and painting. While the settle
   * budget lasts a frame steps the physics; afterwards the loop stops entirely,
   * so a resting graph costs nothing until a hover, drag or theme change needs
   * a repaint.
   */
  function schedule() {
    if (frame !== undefined) return
    frame = requestAnimationFrame((now) => {
      frame = undefined
      if (settleRemaining <= 0) {
        alpha = 0
        draw()
        return
      }

      const previous = lastFrameAt || now
      const elapsed = Math.min(64, now - previous)
      lastFrameAt = now
      settleRemaining -= elapsed
      alpha = Math.max(0.02, settleRemaining / SETTLE_MS)

      // More physics steps when frames are long, so a slow machine reaches the
      // same layout inside the same wall-clock budget.
      const steps = Math.max(1, Math.min(MAX_STEPS_PER_FRAME, Math.round(elapsed / FRAME_MS)))
      for (let i = 0; i < steps; i++) stepLayout(state, alpha)
      if (settleRemaining <= 0 && !userAdjusted) fitToContent()
      draw()
      schedule()
    })
  }

  const redraw = schedule

  function draw() {
    if (!canvas) return
    const context = canvas.getContext("2d")
    if (!context) return
    palette ??= readPalette(container ?? document.documentElement)
    const dpr = window.devicePixelRatio || 1
    const transform = view()

    context.setTransform(dpr, 0, 0, dpr, 0, 0)
    drawGraph(context, state, {
      palette,
      width,
      height,
      scale: transform.scale,
      offsetX: transform.x,
      offsetY: transform.y,
      edges: state.edges,
      selectedId: props.selectedId,
      hoverId: hoverId(),
      matches: props.matches,
    })
  }

  function resize() {
    if (!canvas || !container) return
    const rect = container.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return
    width = rect.width
    height = rect.height
    const dpr = window.devicePixelRatio || 1
    canvas.width = Math.round(width * dpr)
    canvas.height = Math.round(height * dpr)
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`
    if (state.sims.length === 0) rebuild()
    else redraw()
  }

  function toGraph(clientX: number, clientY: number) {
    const rect = canvas?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    const transform = view()
    return {
      x: (clientX - rect.left - transform.x) / transform.scale,
      y: (clientY - rect.top - transform.y) / transform.scale,
    }
  }

  function hitTest(clientX: number, clientY: number): Sim | undefined {
    const point = toGraph(clientX, clientY)
    let best: Sim | undefined
    let bestDistance = Number.POSITIVE_INFINITY
    for (const sim of state.sims) {
      const distance = Math.hypot(sim.x - point.x, sim.y - point.y)
      if (distance <= sim.radius + HIT_SLOP / view().scale && distance < bestDistance) {
        best = sim
        bestDistance = distance
      }
    }
    return best
  }

  function onPointerDown(event: PointerEvent) {
    if (!canvas) return
    canvas.setPointerCapture(event.pointerId)
    pointerStart = { x: event.clientX, y: event.clientY }
    const hit = hitTest(event.clientX, event.clientY)
    if (hit) {
      dragging = { sim: hit, moved: false }
      hit.pinned = true
      return
    }
    userAdjusted = true
    const transform = view()
    panning = { startX: event.clientX, startY: event.clientY, originX: transform.x, originY: transform.y }
  }

  function onPointerMove(event: PointerEvent) {
    if (dragging) {
      const point = toGraph(event.clientX, event.clientY)
      dragging.sim.x = point.x
      dragging.sim.y = point.y
      if (pointerStart && Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 3)
        dragging.moved = true
      redraw()
      return
    }
    if (panning) {
      setView((current) => ({
        ...current,
        x: panning!.originX + (event.clientX - panning!.startX),
        y: panning!.originY + (event.clientY - panning!.startY),
      }))
      redraw()
      return
    }
    const hit = hitTest(event.clientX, event.clientY)
    const next = hit?.node.id
    if (next !== hoverId()) {
      setHoverId(next)
      redraw()
    }
  }

  function onPointerUp(event: PointerEvent) {
    canvas?.releasePointerCapture(event.pointerId)
    if (dragging) {
      // A click selects; a drag just moves the node.
      if (!dragging.moved) props.onSelect?.(dragging.sim.node)
      dragging.sim.pinned = false
      heat(REHEAT_MS)
    } else if (panning && pointerStart) {
      const moved = Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 3
      if (!moved) props.onSelect?.(undefined)
    }
    dragging = undefined
    panning = undefined
    pointerStart = undefined
  }

  function onWheel(event: WheelEvent) {
    event.preventDefault()
    userAdjusted = true
    const rect = canvas?.getBoundingClientRect()
    if (!rect) return
    const transform = view()
    const factor = Math.exp(-event.deltaY * 0.0015)
    const scale = Math.min(4, Math.max(0.15, transform.scale * factor))
    // Keep the point under the cursor anchored while zooming.
    const px = event.clientX - rect.left
    const py = event.clientY - rect.top
    const ratio = scale / transform.scale
    setView({ scale, x: px - (px - transform.x) * ratio, y: py - (py - transform.y) * ratio })
    redraw()
  }

  onMount(() => {
    if (!container || !canvas) return
    palette = readPalette(container)
    const observer = new ResizeObserver(() => resize())
    observer.observe(container)

    // Theme switches rewrite the custom properties; re-read so the graph follows.
    const themeObserver = new MutationObserver(() => {
      palette = readPalette(container!)
      redraw()
    })
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] })
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    const onScheme = () => {
      palette = readPalette(container!)
      redraw()
    }
    media.addEventListener("change", onScheme)

    resize()

    props.onReady?.({
      reset: () => {
        if (!container) return
        const rect = container.getBoundingClientRect()
        setView({ x: 0, y: 0, scale: 1 })
        state = createLayout({ nodes: [], edges: [] }, 0, 0)
        userAdjusted = false
        width = rect.width
        height = rect.height
        rebuild()
      },
      focus: (id) => {
        const sim = state.index.get(id)
        if (!sim) return
        userAdjusted = true
        const scale = Math.max(view().scale, 1.1)
        setView({ scale, x: width / 2 - sim.x * scale, y: height / 2 - sim.y * scale })
        redraw()
      },
      zoom: (factor) => {
        setView((current) => ({ ...current, scale: Math.min(4, Math.max(0.15, current.scale * factor)) }))
        redraw()
      },
    })

    onCleanup(() => {
      observer.disconnect()
      themeObserver.disconnect()
      media.removeEventListener("change", onScheme)
      if (frame !== undefined) cancelAnimationFrame(frame)
    })
  })

  createEffect(() => {
    // Track the inputs that change the layout.
    props.data
    props.hiddenKinds
    if (width > 0 && height > 0) rebuild()
  })

  createEffect(() => {
    props.selectedId
    props.matches
    redraw()
  })

  return (
    <div ref={container} class={props.class ?? "relative size-full"}>
      <canvas
        ref={canvas}
        class="block size-full touch-none"
        classList={{ "cursor-grab": !hoverId(), "cursor-pointer": Boolean(hoverId()) }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onWheel={onWheel}
      />
    </div>
  )
}
