"""Controllable live caption session for the desktop app."""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .asr import Transcriber
from .audio import LiveCapture, find_loopback_device, list_devices
from .translate import Translator
from .types import Caption


@dataclass
class SessionConfig:
    source: str = "system"  # system | mic | device
    device_index: int | None = None
    source_lang: str = "ko"
    target_lang: str = "en"
    model: str = "base"
    chunk_seconds: float = 2.5
    bilingual: bool = True


@dataclass
class SessionStatus:
    running: bool = False
    loading: bool = False
    source: str = "system"
    device_name: str | None = None
    source_lang: str = "ko"
    target_lang: str = "en"
    model: str = "base"
    error: str | None = None
    captions: int = 0
    last_original: str = ""
    last_translated: str = ""
    loopback_ok: bool = False
    ready: bool = False


class LiveSession:
    """Start/stop live captions from a background thread."""

    def __init__(self, on_caption: Callable[[Caption], None] | None = None):
        self.on_caption = on_caption
        self.config = SessionConfig()
        self.status = SessionStatus()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._transcriber: Transcriber | None = None
        self._translator: Translator | None = None
        self._lock = threading.Lock()
        self._last_text = ""
        self.refresh_audio_status()

    def refresh_audio_status(self) -> None:
        loop = find_loopback_device()
        self.status.loopback_ok = loop is not None
        if loop and self.status.device_name is None:
            self.status.device_name = loop.name

    def devices(self) -> list[dict[str, Any]]:
        loop = find_loopback_device()
        out = []
        for d in list_devices():
            out.append({
                "index": d.index,
                "name": d.name,
                "channels": d.channels,
                "hostapi": d.hostapi,
                "loopback": bool(loop and d.index == loop.index),
            })
        return out

    def start(self, config: SessionConfig | None = None) -> SessionStatus:
        with self._lock:
            if self.status.running or self.status.loading:
                return self.snapshot()
            if config:
                self.config = config
            self.status.error = None
            self.status.loading = True
            self.status.ready = False
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self.snapshot()

    def stop(self) -> SessionStatus:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=8)
        with self._lock:
            self.status.running = False
            self.status.loading = False
        return self.snapshot()

    def snapshot(self) -> SessionStatus:
        self.refresh_audio_status()
        return SessionStatus(**asdict(self.status))

    def _resolve_device(self) -> tuple[int | None, str]:
        cfg = self.config
        if cfg.source == "mic":
            return None, "Default microphone"
        if cfg.source == "device" and cfg.device_index is not None:
            for d in list_devices():
                if d.index == cfg.device_index:
                    return d.index, d.name
            return cfg.device_index, f"Device {cfg.device_index}"
        loop = find_loopback_device()
        if loop is None:
            raise RuntimeError(
                "No system audio device found. Install BlackHole 2ch (Mac) or "
                "VB-Cable / Stereo Mix (Windows), then route your speakers through it."
            )
        return loop.index, loop.name

    def _run(self) -> None:
        try:
            device, name = self._resolve_device()
            self.status.device_name = name
            self.status.source = self.config.source
            self.status.source_lang = self.config.source_lang
            self.status.target_lang = self.config.target_lang
            self.status.model = self.config.model

            lang = None if self.config.source_lang in ("auto", "") else self.config.source_lang.split("-")[0]
            self._transcriber = Transcriber(model_size=self.config.model, language=lang)
            self._translator = Translator(source=self.config.source_lang, target=self.config.target_lang)
            self._last_text = ""

            with self._lock:
                self.status.loading = False
                self.status.running = True
                self.status.ready = True

            with LiveCapture(device=device) as cap:
                while not self._stop.is_set():
                    chunk = cap.read(self.config.chunk_seconds)
                    if chunk is None:
                        time.sleep(0.04)
                        continue
                    self._handle(chunk.pcm, chunk.sample_rate)
        except Exception as exc:
            self.status.error = str(exc)
            traceback.print_exc()
        finally:
            with self._lock:
                self.status.running = False
                self.status.loading = False
                self.status.ready = False

    def _handle(self, pcm, sample_rate: int) -> None:
        assert self._transcriber and self._translator
        tr = self._transcriber.transcribe(pcm, sample_rate)
        if tr is None or len(tr.text.strip()) < 2:
            return
        norm = tr.text.strip().lower()
        if norm == self._last_text or (self._last_text and norm in self._last_text):
            return
        if self._last_text and self._last_text in norm and len(norm) - len(self._last_text) < 4:
            return
        self._last_text = norm
        translated = self._translator.translate(tr.text)
        cap = Caption(original=tr.text, translated=translated, language=tr.language)
        self.status.captions += 1
        self.status.last_original = cap.original
        self.status.last_translated = cap.translated
        if self.on_caption:
            self.on_caption(cap)
