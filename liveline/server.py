"""Local web overlay for browsers / OBS browser source."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from .types import Caption

OVERLAY_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>liveline</title>
<style>
  html, body { margin: 0; height: 100%; background: transparent; overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
  #wrap { position: fixed; left: 0; right: 0; bottom: 8%; display: flex; justify-content: center; pointer-events: none; }
  #card { max-width: 90vw; padding: 14px 22px; border-radius: 10px; background: rgba(0,0,0,.72);
    text-align: center; backdrop-filter: blur(6px); }
  #tr { color: #fff; font-size: clamp(18px, 3.2vw, 36px); font-weight: 650; line-height: 1.3; }
  #or { color: #9ca3af; font-size: clamp(12px, 1.8vw, 18px); margin-top: 6px; line-height: 1.35; }
  #status { position: fixed; top: 12px; right: 14px; color: #6b7280; font-size: 12px; }
</style>
</head>
<body>
  <div id="status">connecting…</div>
  <div id="wrap"><div id="card"><div id="tr">listening…</div><div id="or"></div></div></div>
  <script>
    const tr = document.getElementById('tr');
    const or = document.getElementById('or');
    const st = document.getElementById('status');
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    function connect() {
      const ws = new WebSocket(proto + '://' + location.host + '/ws');
      ws.onopen = () => st.textContent = 'live';
      ws.onclose = () => { st.textContent = 'reconnecting…'; setTimeout(connect, 1000); };
      ws.onmessage = (e) => {
        const d = JSON.parse(e.data);
        tr.textContent = d.translated || d.original || '';
        or.textContent = d.translated ? (d.original || '') : '';
      };
    }
    connect();
  </script>
</body>
</html>
"""


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
            await ws.send_text(json.dumps({
                "original": self.latest.original,
                "translated": self.latest.translated,
                "language": self.latest.language,
            }))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def publish(self, caption: Caption) -> None:
        self.latest = caption
        payload = json.dumps({
            "original": caption.original,
            "translated": caption.translated,
            "language": caption.language,
        })
        async with self._lock:
            dead = []
            for ws in self._clients:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)


def create_app(hub: CaptionHub) -> FastAPI:
    app = FastAPI(title="liveline")

    @app.get("/")
    async def index():
        return HTMLResponse(OVERLAY_HTML)

    @app.get("/overlay")
    async def overlay():
        return HTMLResponse(OVERLAY_HTML)

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await hub.connect(ws)
        try:
            while True:
                await ws.receive_text()  # keep alive / ignore client msgs
        except WebSocketDisconnect:
            await hub.disconnect(ws)

    return app


class WebOverlay:
    """Runs uvicorn in a daemon thread and exposes a sync `show()`."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.hub = CaptionHub()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/overlay"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        import uvicorn

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        config = uvicorn.Config(create_app(self.hub), host=self.host, port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        self._loop.run_until_complete(server.serve())

    def show(self, caption: Caption) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.hub.publish(caption), self._loop)

    def close(self) -> None:
        pass
