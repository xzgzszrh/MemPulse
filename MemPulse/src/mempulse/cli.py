"""JSON CLI for both humans and agent tool loops."""

import os
import argparse
import json
import sys
from pathlib import Path
from .facade import get_facade


def build_parser():
    p = argparse.ArgumentParser(
        prog="mempulse", description="MemPulse · 记忆是沿着话题不断生长的脉络"
    )
    p.add_argument("--db")
    p.add_argument(
        "--server",
        default=os.environ.get("MEMPULSE_API_URL"),
        help="Use the local daemon without loading models in the CLI",
    )
    p.add_argument("--user", default="default")
    p.add_argument(
        "--socket",
        default=os.environ.get("MEMPULSE_SOCKET"),
        help="Use a local Unix-socket daemon",
    )
    p.add_argument(
        "--json", action="store_true", help="Output is always JSON for memory commands"
    )
    sub = p.add_subparsers(dest="command", required=True)
    x = sub.add_parser("run", help="record a tool outcome; the host executes the tool")
    x.add_argument("--tool", required=True)
    x.add_argument("--action", required=True)
    x.add_argument("--topic-id")
    x.add_argument(
        "--status",
        choices=("success", "failed", "cancelled", "pending_confirmation"),
        default="success",
    )
    x.add_argument("--result-json")
    x.add_argument("--args-json")
    x.add_argument("--error-type")
    x.add_argument("--fallback-reason")
    x.add_argument("--requested-action")
    x.add_argument("--idempotency-key")
    x.add_argument("--json", dest="_sub_json", action="store_true")
    x = sub.add_parser("ingest")
    x.add_argument("content", nargs="?")
    x.add_argument("--topic")
    x.add_argument("--topic-id")
    x.add_argument("--file")
    x.add_argument("--event-json")
    x.add_argument("--kind", default="conversation")
    x.add_argument("--json", dest="_sub_json", action="store_true")
    for name in ("search", "resolve", "context"):
        x = sub.add_parser(name)
        x.add_argument("query")
        x.add_argument("--topic-id") if name == "context" else None
        x.add_argument("--json", dest="_sub_json", action="store_true")
    x = sub.add_parser("restore")
    x.add_argument("query", nargs="?")
    x.add_argument("--topic-id")
    x.add_argument("--json", dest="_sub_json", action="store_true")
    for name in (
        "health",
        "status",
        "topics",
        "mcp",
        "demo",
        "worker",
        "reindex",
    ):
        sub.add_parser(name)
    x = sub.add_parser("doctor")
    x.add_argument("--db", dest="doctor_db")
    x = sub.add_parser("init")
    x.add_argument("--db", dest="init_db")
    x = sub.add_parser("daemon", help="run yishu-memd on a Unix socket")
    x.add_argument(
        "--socket",
        default=os.environ.get("MEMPULSE_SOCKET", "/tmp/mempulse.sock"),
        dest="daemon_socket",
    )
    x = sub.add_parser("model")
    x.add_argument("model_action", choices=("register",))
    x.add_argument("path")
    x = sub.add_parser("skill")
    x.add_argument("skill_action", choices=("install",))
    x.add_argument("--target", required=True)
    x = sub.add_parser("checkpoint")
    x.add_argument("topic_id")
    x = sub.add_parser("forget")
    x.add_argument("target_id")
    x.add_argument("--type", choices=("event", "topic"), default="event")
    x.add_argument("--field")
    x = sub.add_parser("relations")
    x.add_argument("person_a")
    x.add_argument("person_b")
    x.add_argument("--cursor")
    x.add_argument("--limit", type=int, default=50)
    for name in ("preference", "knowledge"):
        x = sub.add_parser(name)
        x.add_argument("--file")
        x.add_argument("--event-json")
    x = sub.add_parser("ui")
    x.add_argument("--port", type=int, default=51983)
    return p


def read_json(args):
    if getattr(args, "file", None):
        return json.loads(Path(args.file).read_text())
    if getattr(args, "event_json", None):
        return json.loads(args.event_json)
    if not sys.stdin.isatty():
        return json.load(sys.stdin)
    raise ValueError("Provide --file, --event-json, or JSON on stdin")


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "daemon":
            from .daemon import MemPulseDaemon

            MemPulseDaemon(args.daemon_socket, args.db, args.user).serve_forever()
            return 0
        if args.command == "model":
            from .model import register

            out = register(args.path)
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
        if args.command == "skill":
            from .skill import install

            out = install(args.target)
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
        if args.command == "doctor":
            from .doctor import inspect

            print(
                json.dumps(
                    inspect(args.doctor_db or args.db), ensure_ascii=False, indent=2
                )
            )
            return 0
        if args.command == "init":
            f = get_facade(args.init_db or args.db, args.user)
            out = {"status": "ready", "health": f.health()}
            f.store.close()
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
        if args.command == "ui":
            import uvicorn
            from .web import create_app

            uvicorn.run(create_app(args.db), host="127.0.0.1", port=args.port)
            return 0
        if args.command == "mcp":
            from .mcp import serve_stdio

            serve_stdio(args.db, args.user)
            return 0
        if args.socket:
            if args.user != "default":
                raise ValueError("Unix daemon serves its configured default scope")
            from .client import UnixFacade

            f = UnixFacade(args.socket)
        elif args.server:
            if args.user != "default":
                raise ValueError(
                    "The local HTTP daemon serves its configured default scope"
                )
            from .client import HTTPFacade

            f = HTTPFacade(args.server)
        else:
            f = get_facade(
                (args.init_db if args.command == "init" else args.db), args.user
            )
        if args.command == "context":
            out = f.context(args.query, topic_id=args.topic_id)
        elif args.command == "run":
            result = json.loads(args.result_json) if args.result_json else None
            tool_args = json.loads(args.args_json) if args.args_json else None
            out = f.run_tool(
                tool=args.tool,
                action=args.action,
                result_json=result,
                status=args.status,
                topic_id=args.topic_id,
                args_json=tool_args,
                error_type=args.error_type,
                fallback_reason=args.fallback_reason,
                requested_action=args.requested_action,
                idempotency_key=args.idempotency_key,
            )
        elif args.command == "ingest":
            event = (
                {
                    "content": args.content,
                    "topic_title": args.topic,
                    "topic_id": args.topic_id,
                    "source_type": args.kind,
                }
                if args.content
                else read_json(args)
            )
            out = f.ingest(event)
        elif args.command == "search":
            out = f.search(args.query)
        elif args.command == "resolve":
            out = f.resolve(args.query)
        elif args.command == "restore":
            out = f.restore(args.topic_id, args.query)
        elif args.command in ("health", "status"):
            out = f.health()
        elif args.command == "topics":
            out = f.list_topics()
        elif args.command == "checkpoint":
            out = f.checkpoint(args.topic_id)
        elif args.command == "forget":
            out = (
                f.forget_field(args.target_id, args.field)
                if args.field
                else f.forget(args.type, args.target_id)
            )
        elif args.command == "relations":
            out = f.query_relations(
                args.person_a, args.person_b, limit=args.limit, cursor=args.cursor
            )
        elif args.command == "preference":
            out = f.update_preference(read_json(args))
        elif args.command == "knowledge":
            out = f.knowledge(read_json(args))
        elif args.command == "reindex":
            out = f.reindex()
        elif args.command == "worker":
            from .worker import OutboxWorker

            out = (
                f.worker() if hasattr(f, "worker") else OutboxWorker(f.store, f).drain()
            )
        else:
            from .demo import seed_demo

            out = seed_demo(f)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, ImportError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
