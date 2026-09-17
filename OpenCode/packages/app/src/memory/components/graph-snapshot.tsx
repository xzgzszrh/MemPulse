import { createEffect, createSignal, onCleanup, onMount } from "solid-js"
import { computeLayout, fitTransform, graphSignature, type LayoutState } from "../graph-layout"
import { drawGraph, readPalette, type Palette } from "../graph-render"
import type { Graph } from "../types"

/**
 * A still of the knowledge graph.
 *
 * The home page shows this instead of the interactive canvas: the layout is
 * computed once, synchronously, painted once, and then nothing runs — no
 * animation frames, no timers, no listeners beyond a resize observer. Opening
 * the app therefore costs one burst of a few milliseconds rather than a
 * continuously animating simulation.
 *
 * Results are memoised by graph signature and canvas size, so revisiting the
 * section — or any poll that returns the same graph — repaints a cached layout
 * for free.
 */

type CacheEntry = { signature: string; layout: LayoutState }
const cache: CacheEntry[] = []
const CACHE_LIMIT = 4

/**
 * Physics steps are traded off against node count so the synchronous burst
 * stays bounded: a big graph settles less precisely, but the home page never
 * blocks on it. Layouts are cached, so the cost is paid once per graph revision.
 */
function stepsFor(count: number) {
  return Math.max(40, Math.min(320, Math.round(30000 / Math.max(1, count))))
}

function layoutFor(data: Graph, width: number, height: number): LayoutState {
  const signature = `${Math.round(width)}x${Math.round(height)}|${graphSignature({ nodes: data.nodes, edges: data.edges })}`
  const hit = cache.find((entry) => entry.signature === signature)
  if (hit) return hit.layout

  const layout = computeLayout({ nodes: data.nodes, edges: data.edges }, width, height, stepsFor(data.nodes.length))
  cache.unshift({ signature, layout })
  if (cache.length > CACHE_LIMIT) cache.length = CACHE_LIMIT
  return layout
}

export function GraphSnapshot(props: { data: Graph; class?: string }) {
  let canvas: HTMLCanvasElement | undefined
  let container: HTMLDivElement | undefined
  let palette: Palette | undefined

  const [size, setSize] = createSignal({ width: 0, height: 0 })

  function paint() {
    if (!canvas || !container) return
    const { width, height } = size()
    if (width === 0 || height === 0 || props.data.nodes.length === 0) return

    const context = canvas.getContext("2d")
    if (!context) return
    palette ??= readPalette(container)

    const dpr = window.devicePixelRatio || 1
    canvas.width = Math.round(width * dpr)
    canvas.height = Math.round(height * dpr)
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`

    const layout = layoutFor(props.data, width, height)
    const transform = fitTransform(layout, width, height, 32)
    context.setTransform(dpr, 0, 0, dpr, 0, 0)
    drawGraph(context, layout, {
      palette,
      width,
      height,
      scale: transform.scale,
      offsetX: transform.x,
      offsetY: transform.y,
      edges: layout.edges,
    })
  }

  onMount(() => {
    if (!container) return
    const observer = new ResizeObserver(() => {
      const rect = container!.getBoundingClientRect()
      const next = { width: rect.width, height: rect.height }
      setSize((current) => (current.width === next.width && current.height === next.height ? current : next))
    })
    observer.observe(container)

    const themeObserver = new MutationObserver(() => {
      palette = readPalette(container!)
      paint()
    })
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] })
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    const onScheme = () => {
      palette = readPalette(container!)
      paint()
    }
    media.addEventListener("change", onScheme)

    const rect = container.getBoundingClientRect()
    setSize({ width: rect.width, height: rect.height })

    onCleanup(() => {
      observer.disconnect()
      themeObserver.disconnect()
      media.removeEventListener("change", onScheme)
    })
  })

  // The one expensive moment: whenever the graph or the box changes, recompute
  // and repaint. Everything after this is a no-op until something changes again.
  createEffect(() => {
    props.data
    size()
    paint()
  })

  return (
    <div ref={container} class={props.class ?? "relative size-full"}>
      <canvas ref={canvas} class="block size-full" aria-hidden="true" />
    </div>
  )
}
