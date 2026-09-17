import { expect, test } from "bun:test"
import { buildScene, placeholderGraph } from "./constellation"
import type { Graph } from "./types"
import type { Palette } from "./graph-render"

const palette: Palette = {
  surface: "#fafafa",
  label: "#222222",
  labelMuted: "#777777",
  edge: "#cccccc",
  edgeStrong: "#999999",
  selection: "#2255cc",
  swatches: new Map(),
}

test("background simplification keeps every relation available for hover", () => {
  const graph: Graph = { nodes: [], edges: [], stats: { topics: 8, entities: 8, relations: 36 } }
  for (let i = 0; i < 8; i++) {
    graph.nodes.push({ id: `t${i}`, label: `Topic ${i}`, type: "topic", size: 24 })
    graph.nodes.push({ id: `e${i}`, label: `Entity ${i}`, type: "entity", size: 12 })
    graph.edges.push({ id: `tag${i}`, source: `t${i}`, target: `e${i}`, type: "topic_tag" })
    for (let j = 0; j < i; j++)
      graph.edges.push({ id: `link${i}-${j}`, source: `t${i}`, target: `t${j}`, type: "topic_topic", weight: 2 })
  }
  const scene = buildScene(graph, palette)
  expect(scene.nodes).toHaveLength(16)
  expect(scene.edges).toHaveLength(36)
  expect(scene.edges.some((edge) => !edge.background)).toBe(true)
  for (const edge of scene.edges) {
    expect(scene.adjacency.get(edge.a)?.has(edge.b)).toBe(true)
    expect(scene.adjacency.get(edge.b)?.has(edge.a)).toBe(true)
    if (scene.nodes[edge.a].type === "entity" || scene.nodes[edge.b].type === "entity")
      expect(edge.background).toBe(true)
  }
  scene.nodes.forEach((node, index) => {
    if (node.type !== "topic") return
    const backdrop = scene.edges.filter(
      (edge) =>
        edge.background &&
        (edge.a === index || edge.b === index) &&
        scene.nodes[edge.a].type === "topic" &&
        scene.nodes[edge.b].type === "topic",
    )
    expect(backdrop.length).toBeLessThanOrEqual(3)
  })
})

test("the empty-workspace constellation keeps all of its direct links", () => {
  const graph = placeholderGraph()
  const scene = buildScene(graph, palette)
  expect(scene.edges).toHaveLength(graph.edges.length)
  expect(scene.edges.every((edge) => edge.background)).toBe(true)
})
