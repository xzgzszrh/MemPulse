"""Local HTTP transport and built shadcn WebUI."""

from pathlib import Path
from fastapi import FastAPI, Body, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .facade import get_facade


def create_app(db_path=None, *, serve_ui=True):
    service = get_facade(db_path)
    from contextlib import asynccontextmanager
    from threading import Thread, Event
    from .worker import OutboxWorker

    @asynccontextmanager
    async def lifespan(app):
        stop = Event()

        def maintain():
            worker = OutboxWorker(service.store, service)
            while not stop.wait(1):
                try:
                    with service.store._lock:
                        app.state.worker_status = worker.run_once(limit=10)
                except Exception as exc:
                    app.state.worker_status = {"error": str(exc)}

        thread = Thread(target=maintain, name="mempulse-outbox", daemon=True)
        thread.start()
        yield
        stop.set()
        thread.join(timeout=3)

    app = FastAPI(title="MemPulse", version="0.1.0", lifespan=lifespan)
    app.state.service = service

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            from urllib.parse import urlparse

            origin = request.headers.get("origin")
            if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
                return JSONResponse({"error": "Local origin required"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=400)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=404)

    @app.get("/health")
    @app.get("/api/health")
    def health():
        return service.health()

    @app.get("/api/topics")
    def topics():
        return service.list_topics()

    @app.get("/api/graph")
    def graph():
        from .desktop import project_graph
        return project_graph(service)

    @app.get("/api/search")
    def search(q: str, limit: int = 20):
        return service.search(q, limit=limit)

    @app.get("/api/context")
    def context(q: str, topic_id: str | None = None):
        return service.context(q, topic_id)

    @app.post("/api/run")
    def run(data: dict = Body(...)):
        return service.run_tool(**data)

    @app.get("/api/resolve")
    def resolve(q: str):
        return service.resolve(q)

    @app.get("/api/restore")
    def restore(topic_id: str | None = None, q: str | None = None):
        return service.restore(topic_id=topic_id, query=q)

    @app.post("/api/ingest")
    def ingest(event: dict = Body(...)):
        return service.ingest(event)

    @app.post("/api/checkpoint")
    def checkpoint(data: dict = Body(...)):
        return service.checkpoint(**data)

    @app.post("/api/preference")
    def preference(data: dict = Body(...)):
        return service.update_preference(data)

    @app.post("/api/knowledge")
    def knowledge(data: dict = Body(...)):
        return service.knowledge(data)

    @app.post("/api/forget")
    def forget(data: dict = Body(...)):
        return service.forget(**data)

    @app.get("/api/relations")
    def relations(
        person_a: str, person_b: str, limit: int = 50, cursor: str | None = None
    ):
        return service.query_relations(person_a, person_b, limit=limit, cursor=cursor)

    @app.post("/api/topic/move")
    def move(data: dict = Body(...)):
        return service.move_event(**data)

    @app.post("/api/topic/merge")
    def merge(data: dict = Body(...)):
        return service.merge_topics(**data)

    @app.post("/api/topic/split")
    def split(data: dict = Body(...)):
        return service.split_topic(**data)

    @app.post("/api/forget-field")
    def forget_field(data: dict = Body(...)):
        return service.forget_field(**data)

    @app.post("/api/reindex")
    def reindex():
        return service.reindex()

    @app.post("/api/worker")
    def worker():
        from .worker import OutboxWorker

        return OutboxWorker(service.store, service).drain()

    @app.get("/api/governance")
    def governance():
        conn = service.store.conn

        def rows(table):
            column = "requested_by" if table == "mp_tombstones" else "user_id"
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM "
                    + table
                    + " WHERE "
                    + column
                    + "=? ORDER BY created_at DESC LIMIT 100",
                    (service.user_id,),
                )
            ]

        return {
            "preferences": rows("mp_preferences"),
            "knowledge": rows("mp_knowledge"),
            "receipts": rows("mp_tombstones"),
            "checkpoints": rows("mp_checkpoints"),
        }

    dist = Path(__file__).resolve().parents[2] / "ui" / "dist"
    if not dist.exists():
        dist = Path(__file__).resolve().parent / "static"
    if serve_ui and dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
    else:

        @app.get("/")
        def build_required():
            return {
                "service": "MemPulse",
                "webui": "not_built" if serve_ui else "disabled",
                **({"next": "Build UI with: cd ui && npm ci && npm run build"} if serve_ui else {}),
                "docs": "/docs",
            }

    return app
