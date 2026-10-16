"""Desktop app HTTP API, control panel, and caption overlay."""
from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .audio import find_loopback_device
from .session import LiveSession, SessionConfig
from .types import Caption

WEB = Path(__file__).parent / "web"


class CaptionHub:
    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.latest: Caption | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        if self.latest:
            await ws.send_text(_cap_json(self.latest))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def publish(self, caption: Caption) -> None:
        self.latest = caption
        payload = _cap_json(caption)
        async with self._lock:
            dead = []
            for ws in self._clients:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)


def _cap_json(caption: Caption) -> str:
    return json.dumps({
        "original": caption.original,
        "translated": caption.translated,
        "language": caption.language,
    })


class StartBody(BaseModel):
    source: str = "system"
    device_index: int | None = None
    source_lang: str = "ko"
    target_lang: str = "en"
    model: str = "base"
    bilingual: bool = True
    chunk_seconds: float = Field(default=2.5, ge=1.0, le=8.0)


def create_app(session: LiveSession | None = None, hub: CaptionHub | None = None) -> FastAPI:
    hub = hub or CaptionHub()
    session = session or LiveSession(on_caption=lambda c: _schedule_publish(hub, c))

    app = FastAPI(title="Liveline", version="0.2.0")
    app.state.hub = hub
    app.state.session = session

    @app.get("/")
    async def home():
        return FileResponse(WEB / "app.html")

    @app.get("/overlay")
    async def overlay():
        return FileResponse(WEB / "overlay.html")

    @app.get("/api/status")
    async def status():
        return asdict(session.snapshot())

    @app.get("/api/devices")
    async def devices():
        return {"devices": session.devices()}

    @app.post("/api/start")
    async def start(body: StartBody):
        if body.source == "system" and find_loopback_device() is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No system audio device found. Install BlackHole 2ch on Mac "
                    "(or VB-Cable / Stereo Mix on Windows), route your speakers "
                    "through it, then try again."
                ),
            )
        st = session.start(SessionConfig(
            source=body.source,
            device_index=body.device_index,
            source_lang=body.source_lang,
            target_lang=body.target_lang,
            model=body.model,
            chunk_seconds=body.chunk_seconds,
            bilingual=body.bilingual,
        ))
        return asdict(st)

    @app.post("/api/stop")
    async def stop():
        return asdict(session.stop())

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await hub.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            await hub.disconnect(ws)

    return app


_loop_ref: dict[str, asyncio.AbstractEventLoop] = {}


def _schedule_publish(hub: CaptionHub, caption: Caption) -> None:
    loop = _loop_ref.get("loop")
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(hub.publish(caption), loop)


class AppServer:
    """Runs uvicorn + LiveSession for the desktop app."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.hub = CaptionHub()
        self.session = LiveSession(on_caption=self._on_caption)
        self.app = create_app(self.session, self.hub)
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    @property
    def overlay_url(self) -> str:
        return f"http://{self.host}:{self.port}/overlay"

    def _on_caption(self, caption: Caption) -> None:
        _schedule_publish(self.hub, caption)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        import uvicorn

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _loop_ref["loop"] = loop
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())

    def wait_ready(self, timeout: float = 15.0) -> None:
        import time
        import urllib.request

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(self.url, timeout=0.5) as r:
                    if r.status == 200:
                        return
            except Exception:
                time.sleep(0.1)
        raise TimeoutError("Liveline server did not start")

    def show(self, caption: Caption) -> None:
        self._on_caption(caption)

    def close(self) -> None:
        self.session.stop()
