import { expect, test } from "bun:test"
import { memoryAgentMethodAllowed } from "./memory-policy"

test("agent requests can propose changes but cannot grant their own approval", () => {
  for (const method of ["search", "restore", "agent_context", "propose_operation", "operation"])
    expect(memoryAgentMethodAllowed(method)).toBe(true)
  for (const method of [
    "confirm_operation",
    "reject_operation",
    "ingest",
    "capture_event",
    "forget",
    "rename_topic",
    "merge",
    "split",
    "checkpoint",
    "preference",
    "knowledge",
    "configure_model",
  ])
    expect(memoryAgentMethodAllowed(method)).toBe(false)
})
