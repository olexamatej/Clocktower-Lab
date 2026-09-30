"""Loopback web API and bundled, dependency-free browser application."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import GameConfig, ModelConfig, demo_config
from .personas import SECTIONS
from .providers import CREDENTIALS, HTTPProvider, ProviderError
from .roles import ROLES
from .runner import Runner
from .storage import Store, project_run


class PersonaRequest(BaseModel):
    text: str
    ref: str | None = None


class SaveRequest(BaseModel):
    config: GameConfig
    id: str | None = None
    duplicate: bool = False


def create_app(root: Path | None = None) -> FastAPI:
    store = Store(root or Path(os.getenv("CLOCKTOWER_DATA", "data")))
    runners: dict[str, Runner] = {}
    tasks: dict[str, asyncio.Task] = {}

    @asynccontextmanager
    async def lifespan(app):
        # A single local process owns this store. Any previously running record was interrupted.
        for entry in store.list("runs"):
            if entry["status"] == "running":
                record = store.read("runs", entry["id"])
                pid = record.get("process_id")
                if pid:
                    try:
                        os.kill(pid, 0)
                        continue
                    except ProcessLookupError:
                        pass
                record["status"] = "interrupted"
                record["result"] = {
                    "status": "interrupted",
                    "winner": None,
                    "reason": "Application restarted before run completed",
                }
                store.write("runs", entry["id"], record)
        yield
        for runner in runners.values():
            runner.stop.set()
        await asyncio.gather(*tasks.values(), return_exceptions=True)

    app = FastAPI(title="Clocktower Lab", lifespan=lifespan)
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            return JSONResponse({"error": "Cross-origin requests are not allowed"}, status_code=403)
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and request.headers.get("content-type", "").split(";")[0] != "application/json"
        ):
            return JSONResponse({"error": "Use application/json"}, status_code=415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic's default error response reflects the entire invalid input (possibly a secret).
        return JSONResponse(
            {"error": "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())},
            status_code=422,
        )

    @app.exception_handler(ValueError)
    async def invalid_value(request, exc):
        message = "; ".join(e["msg"] for e in exc.errors()) if isinstance(exc, ValidationError) else str(exc)
        return JSONResponse({"error": message}, status_code=422)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return JSONResponse(
            {"error": "Requested configuration, run, or persona was not found"}, status_code=404
        )

    @app.exception_handler(ProviderError)
    async def provider_error(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=422)

    @app.get("/api/bootstrap")
    def bootstrap():
        return {
            "config": demo_config().model_dump(),
            "roles": [asdict(r) for r in ROLES.values()],
            "personas": store.personas.list(),
            "sections": SECTIONS,
            "credentials": {provider: bool(os.getenv(env)) for provider, env in CREDENTIALS.items()},
        }

    @app.get("/api/personas")
    def personas():
        return store.personas.list()

    @app.get("/api/persona")
    def persona(ref: str):
        return {"text": store.personas.read(ref), "ref": ref}

    @app.post("/api/personas")
    def save_persona(body: PersonaRequest):
        return {"ref": store.personas.save(body.text, body.ref)}

    @app.get("/api/configs")
    def configs():
        return store.list("configs")

    @app.get("/api/configs/{key}")
    def config(key: str):
        return store.read("configs", key)

    @app.post("/api/configs")
    def save_config(body: SaveRequest):
        key, config = store.save_config(body.config, body.id, duplicate=body.duplicate)
        return {"id": key, "config": config.model_dump()}

    @app.post("/api/validate")
    def validate_config(config: GameConfig):
        for p in config.players:
            store.personas.read(p.persona)
        return {"valid": True, "models": {p.id: config.model_for(p).model_dump() for p in config.players}}

    @app.post("/api/models")
    async def provider_models(config: ModelConfig):
        if config.provider == "mock":
            return ["demo"]
        return await HTTPProvider().models(config)

    @app.get("/api/runs")
    def runs():
        return store.list("runs")

    @app.post("/api/runs")
    async def start(config: GameConfig):
        if any(not t.done() for t in tasks.values()):
            raise HTTPException(status_code=409, detail="Stop the current run before starting another")
        runner = Runner(config, store)
        runner.save()
        runners[runner.id] = runner
        tasks[runner.id] = asyncio.create_task(runner.run())
        return {"id": runner.id}

    @app.get("/api/runs/{key}")
    def run(key: str, view: str = "public"):
        return project_run(store.read("runs", key), view)

    @app.post("/api/runs/{key}/stop")
    def stop(key: str):
        if key in runners:
            runners[key].stop.set()
        return {"stopping": True}

    app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")
    return app
