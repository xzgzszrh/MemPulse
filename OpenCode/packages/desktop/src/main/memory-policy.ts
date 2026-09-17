/** The model-facing loopback gateway cannot execute or approve memory writes. */
export function memoryAgentMethodAllowed(method: string) {
  return new Set([
    "health",
    "bootstrap",
    "search",
    "resolve",
    "restore",
    "list_topics",
    "graph",
    "session_topic",
    "agent_context",
    "query_relations",
    "propose_operation",
    "operation",
  ]).has(method)
}
