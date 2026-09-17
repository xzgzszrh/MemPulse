import type { Tone } from "../labels"

/**
 * Tone → design-token class maps. The strings are written out in full because
 * Tailwind only sees classes it can find literally in source; building them by
 * interpolation would silently produce no styles.
 */

export const toneDot: Record<Tone, string> = {
  neutral: "bg-v2-text-text-faint",
  accent: "bg-v2-text-text-accent",
  success: "bg-v2-state-fg-success",
  warning: "bg-v2-state-fg-warning",
  danger: "bg-v2-state-fg-danger",
}

export const toneText: Record<Tone, string> = {
  neutral: "text-v2-text-text-muted",
  accent: "text-v2-text-text-accent",
  success: "text-v2-state-fg-success",
  warning: "text-v2-state-fg-warning",
  danger: "text-v2-state-fg-danger",
}

export const toneChip: Record<Tone, string> = {
  neutral: "border-v2-border-border-base bg-v2-background-bg-layer-02 text-v2-text-text-muted",
  accent: "border-v2-state-border-info bg-v2-state-bg-info text-v2-state-fg-info",
  success: "border-v2-state-border-success bg-v2-state-bg-success text-v2-state-fg-success",
  warning: "border-v2-state-border-warning bg-v2-state-bg-warning text-v2-state-fg-warning",
  danger: "border-v2-state-border-danger bg-v2-state-bg-danger text-v2-state-fg-danger",
}
