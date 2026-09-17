"""MCP stdio transport, sharing the same scoped application service."""

import json
import sys
from .facade import get_facade

TOOLS = [
    {
        "name": "resolve_topic",
        "description": "Resolve a query without writing memory",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "ingest_event",
        "description": "Store one standard event",
        "inputSchema": {
            "type": "object",
            "properties": {"event": {"type": "object"}},
            "required": ["event"],
        },
    },
    {
        "name": "search_memory",
        "description": "Search local memories",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "restore_context",
        "description": "Return topic context with evidence and gaps",
        "inputSchema": {
            "type": "object",
            "properties": {"topic_id": {"type": "string"}},
            "required": ["topic_id"],
        },
    },
    {
        "name": "list_topics",
        "description": "List topics in this scope",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "forget_memory",
        "description": "Forget an explicit event or topic",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_type": {"enum": ["event", "topic"]},
                "target_id": {"type": "string"},
            },
            "required": ["target_type", "target_id"],
        },
    },
]


def call(service, name, args):
    if name == "resolve_topic":
        return service.resolve(args["query"])
    if name == "ingest_event":
        return service.ingest(args["event"])
    if name == "search_memory":
        return service.search(args["query"])
    if name == "restore_context":
        return service.restore(args["topic_id"])
    if name == "list_topics":
        return service.list_topics()
    if name == "forget_memory":
        return service.forget(args["target_type"], args["target_id"])
    raise ValueError("Unknown tool: " + str(name))


def serve_stdio(db_path=None, user_id="default"):
    service = get_facade(db_path, user_id)
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            method = request.get("method")
            if "id" not in request:
                continue
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "MemPulse", "version": "0.1.0"},
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = request.get("params", {})
                try:
                    result = {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    call(
                                        service,
                                        params.get("name"),
                                        params.get("arguments", {}),
                                    ),
                                    ensure_ascii=False,
                                ),
                            }
                        ]
                    }
                except (KeyError, ValueError) as exc:
                    result = {
                        "isError": True,
                        "content": [{"type": "text", "text": str(exc)}],
                    }
            else:
                raise ValueError("Unknown method")
            response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32600, "message": str(exc)},
            }
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    serve_stdio()
