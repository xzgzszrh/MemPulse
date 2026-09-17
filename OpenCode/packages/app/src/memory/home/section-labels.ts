import { tabLabelKey, TAB_ICON } from "../labels"
import type { MemorySection } from "../types"

export function sectionLabelKey(section: MemorySection) {
  return tabLabelKey(section)
}

export function sectionIcon(section: MemorySection) {
  return TAB_ICON[section]
}
