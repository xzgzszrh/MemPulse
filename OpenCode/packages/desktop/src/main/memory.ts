import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process"
import { randomBytes } from "node:crypto"
import { existsSync } from "node:fs"
import { createServer, type Server as HttpServer } from "node:http"
import { join, resolve } from "node:path"
import { app } from "electron"
import { memoryAgentMethodAllowed } from "./memory-policy"

type Pending = { resolve: (value: unknown) => void; reject: (error: Error) => void }

/**
 * Starts MemPulse beside the OpenCode server and keeps its JSON-lines protocol
 * behind one small main-process boundary. The renderer never gets filesystem or
 * process access; it only sees typed IPC methods exposed by preload.
 *
 * Two clients share this bridge: the renderer (memory workbench) and the
 * OpenCode server plugin, which reaches it over a loopback HTTP gateway guarded
 * by a per-launch token. Capture of the conversation happens here, from the
 * server's event stream, so the chat request path never waits on memory writes.
 */
export class MemoryBridge {
  private child: ChildProcessWithoutNullStreams | undefined
  private buffer = ""
  private nextID = 0
  private pending = new Map<number, Pending>()
  private starting: Promise<void> | undefined
  private gateway: HttpServer | undefined
  private gatewayUrl: string | undefined
  private readonly gatewayToken = randomBytes(24).toString("hex")
  private captureAbort: AbortController | undefined
  private messageMeta = new Map<string, { role: string; created?: number }>()
  private childSessions = new Set<string>()
  private queuedText = new Map<string, { directory: string; sessionID: string; part: Record<string, unknown> }>()
  private captured = new Set<string>()

  constructor(private readonly userDataPath: string) {}

  /** Shared secret the server plugin must present to the gateway. */
  get token() {
    return this.gatewayToken
  }

  async request(method: string, params: Record<string, unknown> = {}) {
    await this.start()
    const child = this.child
    if (!child) throw new Error("记忆服务不可用")

    return new Promise<unknown>((resolveRequest, reject) => {
      const id = this.nextID++
      this.pending.set(id, { resolve: resolveRequest, reject })
      child.stdin.write(`${JSON.stringify({ id, method, params })}\n`, "utf8", (error) => {
        if (!error) return
        this.pending.delete(id)
        reject(error)
      })
    })
  }

  async stop() {
    this.captureAbort?.abort()
    this.captureAbort = undefined
    if (this.gateway) {
      await new Promise<void>((resolveClose) => this.gateway?.close(() => resolveClose()))
      this.gateway = undefined
      this.gatewayUrl = undefined
    }
    const child = this.child
    this.child = undefined
    if (!child) return
    for (const pending of this.pending.values()) pending.reject(new Error("记忆服务已停止"))
    this.pending.clear()
    child.kill()
    await new Promise<void>((resolveExit) => {
      if (child.exitCode !== null) return resolveExit()
      child.once("exit", () => resolveExit())
    })
  }

  async startGateway() {
    if (this.gatewayUrl) return this.gatewayUrl
    const gateway = createServer(async (request, response) => {
      if (request.method !== "POST" || request.url !== "/request") {
        response.writeHead(404, { "content-type": "application/json" })
        response.end(JSON.stringify({ ok: false, error: "记忆网关路径不存在" }))
        return
      }
      if (request.headers.authorization !== `Bearer ${this.gatewayToken}`) {
        response.writeHead(401, { "content-type": "application/json" })
        response.end(JSON.stringify({ ok: false, error: "记忆网关拒绝未授权请求" }))
        return
      }
      const chunks: Buffer[] = []
      for await (const chunk of request) chunks.push(Buffer.from(chunk))
      try {
        const payload = JSON.parse(Buffer.concat(chunks).toString("utf8")) as { method?: unknown; params?: unknown }
        if (typeof payload.method !== "string") throw new Error("记忆网关请求无效")
        if (!memoryAgentMethodAllowed(payload.method)) throw new Error("记忆修改必须先提出操作并由用户在客户端确认")
        const params = isRecord(payload.params) ? payload.params : {}
        const data = await this.request(payload.method, params)
        response.writeHead(200, { "content-type": "application/json" })
        response.end(JSON.stringify({ ok: true, data }))
      } catch (error) {
        response.writeHead(400, { "content-type": "application/json" })
        response.end(JSON.stringify({ ok: false, error: error instanceof Error ? error.message : String(error) }))
      }
    })
    await new Promise<void>((resolveListen, rejectListen) => {
      gateway.once("error", rejectListen)
      gateway.listen(0, "127.0.0.1", () => resolveListen())
    })
    const address = gateway.address()
    if (!address || typeof address === "string") throw new Error("记忆网关未能监听本地端口")
    this.gateway = gateway
    this.gatewayUrl = `http://127.0.0.1:${address.port}`
    return this.gatewayUrl
  }

  connectOpenCode(server: { url: string; username: string | null; password: string | null }) {
    this.captureAbort?.abort()
    const abort = new AbortController()
    this.captureAbort = abort
    void this.captureLoop(server, abort.signal)
  }

  private async start() {
    if (this.child) return
    if (this.starting) return this.starting
    this.starting = Promise.resolve()
      .then(() => {
        const root = resolve(app.getAppPath(), "../../..")
        const sourceEntry = join(root, "MemPulse", "scripts", "desktop_entry.py")
        const bundled = join(
          process.resourcesPath,
          "mempulse",
          process.platform === "win32" ? "mempulse-service.exe" : "mempulse-service",
        )
        const dataDir = join(this.userDataPath, "mempulse")
        const command =
          app.isPackaged && existsSync(bundled)
            ? bundled
            : process.env.MEMPULSE_PYTHON || join(root, "MemPulse", ".venv", "bin", "python")
        const args =
          app.isPackaged && existsSync(bundled) ? ["--data-dir", dataDir] : [sourceEntry, "--data-dir", dataDir]
        const child = spawn(command, args, {
          cwd: root,
          env: { ...process.env, PYTHONPATH: join(root, "MemPulse", "src") },
          stdio: "pipe",
        })
        this.child = child
        child.stdout.setEncoding("utf8")
        child.stdout.on("data", (chunk: string) => this.handleOutput(chunk))
        child.stderr.setEncoding("utf8")
        child.stderr.on("data", (chunk: string) => console.warn("[mempulse]", chunk.trim()))
        child.on("error", (error) => this.failPending(error))
        child.on("exit", () => {
          if (this.child !== child) return
          this.child = undefined
          this.failPending(new Error("记忆服务已退出"))
        })
      })
      .finally(() => {
        this.starting = undefined
      })
    return this.starting
  }

  private handleOutput(chunk: string) {
    this.buffer += chunk
    const lines = this.buffer.split("\n")
    this.buffer = lines.pop() ?? ""
    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const response = JSON.parse(line) as { id?: number; ok?: boolean; data?: unknown; error?: string }
        if (typeof response.id !== "number") continue
        const pending = this.pending.get(response.id)
        if (!pending) continue
        this.pending.delete(response.id)
        if (response.ok) pending.resolve(response.data)
        else pending.reject(new Error(response.error || "记忆请求失败"))
      } catch (error) {
        this.failPending(error instanceof Error ? error : new Error(String(error)))
      }
    }
  }

  private failPending(error: Error) {
    for (const pending of this.pending.values()) pending.reject(error)
    this.pending.clear()
  }

  private async captureLoop(
    server: { url: string; username: string | null; password: string | null },
    signal: AbortSignal,
  ) {
    while (!signal.aborted) {
      try {
        await this.captureOnce(server, signal)
      } catch (error) {
        if (!signal.aborted) console.warn("[mempulse] OpenCode event stream disconnected", error)
      }
      if (!signal.aborted) await new Promise((resolveDelay) => setTimeout(resolveDelay, 1500))
    }
  }

  private async captureOnce(
    server: { url: string; username: string | null; password: string | null },
    signal: AbortSignal,
  ) {
    const headers = new Headers({ Accept: "text/event-stream" })
    if (server.password) {
      headers.set(
        "Authorization",
        `Basic ${Buffer.from(`${server.username || "opencode"}:${server.password}`).toString("base64")}`,
      )
    }
    const response = await fetch(new URL("/global/event", server.url), { headers, signal })
    if (!response.ok || !response.body) throw new Error(`事件流连接失败：${response.status}`)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    while (!signal.aborted) {
      const chunk = await reader.read()
      if (chunk.done) return
      buffer += decoder.decode(chunk.value, { stream: true })
      const blocks = buffer.split("\n\n")
      buffer = blocks.pop() ?? ""
      for (const block of blocks) {
        const raw = block
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim())
          .join("\n")
        if (!raw) continue
        await this.captureEvent(JSON.parse(raw))
      }
    }
  }

  private async captureEvent(value: unknown) {
    if (!isRecord(value) || !isRecord(value.payload)) return
    const directory = typeof value.directory === "string" ? value.directory : ""
    const type = typeof value.payload.type === "string" ? value.payload.type : ""
    const properties = isRecord(value.payload.properties) ? value.payload.properties : {}
    const info = isRecord(properties.info) ? properties.info : {}
    const sessionID = text(properties.sessionID) || text(info.sessionID) || text(info.id)

    if ((type === "session.created" || type === "session.updated") && sessionID) {
      // Subagent sessions are internal to their parent's turn; the parent's own
      // text and the task tool's result already carry what mattered.
      if (typeof info.parentID === "string" && info.parentID) {
        this.childSessions.add(sessionID)
        return
      }
      return
    }

    if (type === "message.updated" && isRecord(properties.info)) {
      const messageID = text(properties.info.id)
      const role = text(properties.info.role)
      const time = isRecord(properties.info.time) ? properties.info.time : {}
      if (messageID && role)
        this.messageMeta.set(messageID, { role, created: typeof time.created === "number" ? time.created : undefined })
      return
    }

    if (type === "message.part.updated" && isRecord(properties.part)) {
      const part = properties.part
      const partSessionID = text(part.sessionID) || sessionID
      const partID = text(part.id)
      if (!partSessionID || !partID || this.childSessions.has(partSessionID)) return
      if (part.type === "text") {
        this.queuedText.set(`${partSessionID}:${partID}`, { directory, sessionID: partSessionID, part })
        const time = isRecord(part.time) ? part.time : {}
        // User text arrives complete and never gets an end time; assistant text
        // streams, so it waits for the end marker (or session.idle as a backstop).
        const role = this.messageMeta.get(text(part.messageID))?.role
        if (role === "user" || typeof time.end === "number") await this.flushText(partSessionID, partID)
        return
      }
      if (part.type === "tool" && isRecord(part.state)) await this.captureTool(directory, partSessionID, part)
      return
    }

    if (type === "session.idle" && sessionID) {
      const keys = [...this.queuedText.keys()].filter((key) => key.startsWith(`${sessionID}:`))
      for (const key of keys) await this.flushText(sessionID, key.slice(sessionID.length + 1))
    }
  }

  private async flushText(sessionID: string, partID: string) {
    const key = `${sessionID}:${partID}`
    const queued = this.queuedText.get(key)
    if (!queued || this.captured.has(key)) return
    const content = text(queued.part.text).trim()
    if (!content) return
    this.queuedText.delete(key)
    const messageID = text(queued.part.messageID)
    const meta = this.messageMeta.get(messageID)
    const role = meta?.role || "assistant"
    const time = isRecord(queued.part.time) ? queued.part.time : {}
    const occurred =
      typeof time.end === "number" ? time.end : typeof time.start === "number" ? time.start : meta?.created
    await this.ingestOpenCode({
      sessionID,
      directory: queued.directory,
      eventID: `opencode:${sessionID}:message:${messageID || partID}`,
      content,
      sourceType: "conversation",
      occurredAt: occurred,
      metadata: { opencode_role: role, message_id: text(queued.part.messageID), part_id: partID },
    })
    this.captured.add(key)
  }

  private async captureTool(directory: string, sessionID: string, part: Record<string, unknown>) {
    const state = part.state as Record<string, unknown>
    const status = text(state.status)
    if (status !== "completed" && status !== "error") return
    const callID = text(part.callID) || text(part.id)
    const key = `${sessionID}:tool:${callID}`
    if (!callID || this.captured.has(key)) return
    const tool = text(part.tool) || "tool"
    // Memory tools write through the plugin already; echoing their output back
    // into memory would store the recall itself as new evidence.
    if (tool.startsWith("memory_")) {
      this.captured.add(key)
      return
    }
    const output = status === "completed" ? text(state.output) : text(state.error)
    const time = isRecord(state.time) ? state.time : {}
    await this.ingestOpenCode({
      sessionID,
      directory,
      eventID: `opencode:${sessionID}:tool:${callID}`,
      content: `${tool}：${text(state.title) || (status === "completed" ? "执行完成" : "执行失败")}\n${output}`.slice(
        0,
        12000,
      ),
      sourceType: "tool",
      status: status === "completed" ? "success" : "failed",
      occurredAt: typeof time.end === "number" ? time.end : undefined,
      metadata: { tool, call_id: callID, input: state.input ?? {}, output: output.slice(0, 6000) },
    })
    this.captured.add(key)
  }

  private async ingestOpenCode(input: {
    sessionID: string
    directory: string
    eventID: string
    content: string
    sourceType: string
    status?: string
    occurredAt?: number
    metadata: Record<string, unknown>
  }) {
    await this.request("capture_event", {
      event_id: input.eventID,
      idempotency_key: input.eventID,
      content: input.content,
      session_id: input.sessionID,
      ...(input.occurredAt ? { occurred_at: new Date(input.occurredAt).toISOString() } : {}),
      source_type: input.sourceType,
      status: input.status ?? "success",
      app: "OpenCode",
      metadata: { ...input.metadata, opencode_session_id: input.sessionID, opencode_directory: input.directory },
    })
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function text(value: unknown) {
  return typeof value === "string" ? value : ""
}
