/**
 * What the home page's content column can show. Selecting a project shows that
 * project's sessions; selecting a memory section swaps the whole column. One
 * union means the sidebar and the content switcher cannot disagree about what
 * exists.
 */

import type { MemorySection } from "../types"

export type HomeSection = "sessions" | MemorySection

export function isMemorySection(value: HomeSection): value is MemorySection {
  return value !== "sessions"
}

export { MEMORY_SECTIONS, type MemorySection } from "../types"
export { sectionIcon, sectionLabelKey } from "./section-labels"
