# MemPulse Code

This guide describes our current desktop integration built on the excellent OpenCode project. MemPulse itself is an independent memory solution with CLI, MCP and HTTP interfaces. We plan plugin integrations for more IDEs; those dedicated plugins are not yet released.

This checkout is the OpenCode desktop client with a MemPulse memory layer. OpenCode keeps the session, terminal, file review, model selection, update flow and server sidecar as upstream; MemPulse adds long-term memory across sessions and a home page built around it. The upstream repository is `https://github.com/anomalyco/opencode`; this checkout is a local customization and is not affiliated with the OpenCode maintainers.

## Division of labour

- **OpenCode** — short-term context: the messages of the current session, compaction, tool execution.
- **MemPulse** (`../MemPulse`, Python) — long-term memory: a local SQLite store of topics → events, with restore contracts, CPR preferences, knowledge versions, checkpoints and precise forgetting. One `DesktopService` (`src/mempulse/desktop.py`) serves every client over JSON-lines.

## How the pieces connect

```
renderer (SolidJS)  ── preload IPC ──►  Electron main: MemoryBridge  ── stdin/stdout ──►  mempulse desktop service
                                              │  ▲
opencode server (sidecar) ── MEMPULSE_BRIDGE_URL + bearer token ──┘  │
                                                                     └── /global/event stream (capture)
```

- `packages/desktop/src/main/memory.ts` — `MemoryBridge`. Spawns the MemPulse process on first use, exposes it to the renderer through `window.api.mempulse.request` (typed, no filesystem or ports in the renderer), and publishes a loopback HTTP gateway for the server plugin guarded by a per-launch bearer token (`MEMPULSE_BRIDGE_URL`, `MEMPULSE_BRIDGE_TOKEN`; both are set before the sidecar forks because the sidecar snapshots `process.env`).
- **Capture** follows the server event stream and records completed user/assistant text and tool results with idempotent IDs. Unbound records go to a pending inbox. Session creation and session titles never create or rename topics. A user-confirmed task binding is stored separately; the project directory is a reference, not a one-project/one-topic rule. Earlier inbox records are admitted only when selected in the confirmation form.
- **Memory operations** are durable proposals. The model-facing gateway allows reads/proposals but cannot confirm or execute writes. The renderer presents the target, scope, affected evidence and tag preview, then commits through IPC. Terminal receipts retain identifiers rather than another copy of memory prose. Queries and graph reads do not create topics or demo databases.
- `packages/opencode/src/plugin/mempulse.ts` — the agent-facing side, built into the server as an internal plugin:
  - `chat.message` fetches `agent_context` for the user's text so the same turn's system prompt already has it.
  - `experimental.chat.system.transform` appends a constant `<mempulse-protocol>` (what memory is, which tools exist, evidence-not-instruction rules, AMBIGUOUS handling, preference tiers) plus a bounded `<mempulse-memory>` block (route, the session topic's restore contract, cross-topic hits, active preferences). Title/summary/compaction prompts are left alone.
  - `experimental.session.compacting` tells the summariser what memory already keeps.
  - Tools: `memory_search`, `memory_recall`, `memory_topics`, plus proposals through `memory_create_topic`, `memory_bind_topic`, `memory_remember`, `memory_manage`, `memory_checkpoint` and `memory_forget`; `memory_operation_status` reads the result.
  - Fails soft: if the bridge is missing the plugin registers nothing; a service outage backs off for 30 s and the prompt says memory is unavailable.
- `packages/app/src/memory/` — renderer surfaces: the home page constellation (`constellation.ts`, `views/overview-3d.tsx`), the workbench sections (topics, graph, recent, events, governance, health), the session side-panel tab, settings, and the timeline cards for `memory_*` tool calls (`session/tool-cards.tsx`).

Desktop-service methods the client uses beyond the facade: `bootstrap`, `graph`, `search` (with `limit`), `list_topics`, `restore`, `ingest`, `preference`, `knowledge`, `checkpoint`, `forget`, `forget_field`, `move`, `merge`, `split`, `session_topic`, `rename_topic`, `agent_context`, `switch_workspace`, `reindex`, `worker`.

## Home page

The app opens on the MemPulse overview: the mark and tagline over a live constellation of topics and the entities they share (Fibonacci-sphere layout, perspective camera, slow orbit, drag to rotate, wheel to zoom, honours reduced motion). Two floating panels sit near the bottom: a wide recent-sessions list and a compact panel for starting a session or opening the `工作台`. Memory counts sit beneath the panels; the home page has no service-status badge. Topics, graph and governance are available inside the workbench. Everything is drawn from the OpenCode v2 theme tokens so it follows light/dark. An empty workspace shows a faint placeholder constellation. The panels stack in narrow windows, and the content scrolls when the window is too short.

The constellation uses the original full-page composition, orbit speed, depth styling and label display. Clicking a topic node opens that topic's details. The two floating panels and the removal of the home-page service-status line are retained.

The recent panel shows at most three sessions with 32 px desktop rows and 16 px panel padding. The project heading is a menu for choosing an open project or browsing for a folder; new sessions use that selection. Touch targets keep a 44 px minimum. The shadows and translucent floating surfaces remain.

Background edges are thinner and fainter. At rest, each topic has at most three topic-to-topic background links; direct entity links and the complete adjacency remain available, and hovering reveals all incident relationships. The canvas keeps its original layout with a 60 fps drawing budget, pauses on blur/hidden state, and stops repeated drawing in reduced-motion mode. Text layout is cached and offscreen segments are skipped. Normal windows retain DPR 2; large bitmaps are capped at six million pixels.

The macOS icon tile now occupies 80.47% of the canvas width, matching the reference native icon margins. Generate only app icons with `python3 packages/desktop/scripts/generate-mempulse-icons.py --app-icons-only`.

## Kylin source handoff

See [the native Linux build guide](../deploy/kylin/README.md) and [the Codex handoff](../deploy/kylin/CODEX_HANDOFF.md). The supplied workflow targets the user's x86_64 Kylin machine. It builds an ONNX-enabled Python sidecar and packages FP32 assets beside it. Existing user model configuration takes precedence over bundled defaults. The Linux build must still be validated on the target machine; macOS measurements are not Kylin acceptance results.

## Persistent tasks and the merged demonstration

The current demonstration combines legacy material and authored work histories into 53 task topics and 284 events. Only the same Kylin adaptation task is merged; unrelated tasks sharing a project, person or filename stay separate. Import makes a backup, archives only known wholly synthetic legacy topics and preserves mixed/personal records. See [the task and label contract](../../MemPulse/docs/TOPIC-CONTRACT-20260915.md).

Keyword generation is open-vocabulary and evidence-gated. FTS tokenization is not a tag generator. Raw capture does not turn every sentence into keywords; low-confidence candidates stay pending, broad terms are attributes, and each topic has at most eight active keyword anchors. Stable person/resource IDs carry readable labels. TIDE produces task candidates, followed by event-level evidence retrieval, and never approves memory operations.

## Development

```bash
cd OpenCode
bun install
bun run --cwd packages/opencode build:node   # or: bun run script/build-node.ts — the desktop sidecar loads dist/node/node.js, rebuild after plugin changes
bun run --cwd packages/desktop dev
```

Browser preview of the renderer (no Electron) can still show memory data: run `cd ../MemPulse && PYTHONPATH=src .venv/bin/python scripts/desktop_dev.py` (loopback :51984, CORS for localhost) and `bun run --cwd packages/app dev`; DEV builds fall back to that shim when the preload bridge is absent.

Verification used so far: `bun run typecheck` in `packages/opencode`, `packages/desktop`, `packages/app`; `python -m pytest` in MemPulse (`tests/test_desktop.py` covers the desktop methods); end-to-end in the dev app with the `opencode/big-pickle` model calling every `memory_*` tool, then confirming the events, preference and checkpoint in the store.

## Packaging (macOS)

```bash
cd ../MemPulse
PYTHONPATH=src .venv/bin/python scripts/build_desktop_sidecar.py
cd ../OpenCode
bun run --cwd packages/desktop build
CSC_IDENTITY_AUTO_DISCOVERY=false bun run --cwd packages/desktop package:mac -- --dir
```

The unpacked app is emitted under `packages/desktop/dist/mac-arm64/MemPulse Code Dev.app` on Apple Silicon. MemPulse stores its demo and personal workspaces in separate SQLite files under the OpenCode user-data directory.
