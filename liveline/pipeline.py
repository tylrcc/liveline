"""End-to-end live caption pipeline."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .asr import Transcriber
from .audio import LiveCapture, find_loopback_device, iter_file, list_devices
from .types import Caption
from .translate import Translator


def _make_overlay(kind: str, bilingual: bool, host: str, port: int):
    sinks = []
    if kind in ("window", "both"):
        from .overlay import Overlay
        ov = Overlay(bilingual=bilingual)
        ov.start()
        sinks.append(ov)
    if kind in ("web", "both"):
        from .server import WebOverlay
        import time as _time
        web = WebOverlay(host, port)
        web.start()
        _time.sleep(0.4)
        print(f"browser overlay: {web.url}", file=sys.stderr)
        sinks.append(web)
    return sinks


@dataclass
class Settings:
    source_lang: str = "ko"
    target_lang: str = "en"
    model: str = "base"
    device: str = "auto"
    chunk_seconds: float = 3.0
    bilingual: bool = True
    overlay: str = "window"  # window | web | both | none
    host: str = "127.0.0.1"
    port: int = 8765
    min_chars: int = 2


@dataclass
class Pipeline:
    settings: Settings = field(default_factory=Settings)
    on_caption: Callable[[Caption], None] | None = None
    _last_text: str = ""
    _transcriber: Transcriber | None = None
    _translator: Translator | None = None
    _sinks: list = field(default_factory=list)

    def setup(self) -> None:
        s = self.settings
        print(f"loading whisper model '{s.model}'…", file=sys.stderr)
        self._transcriber = Transcriber(
            model_size=s.model,
            device=s.device,
            language=None if s.source_lang in ("auto", "") else s.source_lang.split("-")[0],
        )
        self._translator = Translator(source=s.source_lang, target=s.target_lang)
        self._sinks = _make_overlay(s.overlay, s.bilingual, s.host, s.port)

    def handle_pcm(self, pcm, sample_rate: int, t0: float = 0.0) -> Caption | None:
        assert self._transcriber and self._translator
        tr = self._transcriber.transcribe(pcm, sample_rate)
        if tr is None or len(tr.text.strip()) < self.settings.min_chars:
            return None
        # skip near-duplicates from overlapping windows
        norm = tr.text.strip().lower()
        if norm == self._last_text or (self._last_text and norm in self._last_text):
            return None
        if self._last_text and self._last_text in norm and len(norm) - len(self._last_text) < 4:
            return None
        self._last_text = norm
        translated = self._translator.translate(tr.text)
        cap = Caption(original=tr.text, translated=translated, language=tr.language)
        self.emit(cap)
        return cap

    def emit(self, caption: Caption) -> None:
        print(f"[{caption.language or '?'}] {caption.original}", flush=True)
        if caption.translated and caption.translated != caption.original:
            print(f"  → {caption.translated}", flush=True)
        for sink in self._sinks:
            sink.show(caption)
        if self.on_caption:
            self.on_caption(caption)

    def run_device(self, device: int | str | None = None) -> None:
        self.setup()
        print(f"capturing audio (chunk={self.settings.chunk_seconds}s). Ctrl+C to stop.", file=sys.stderr)
        with LiveCapture(device=device) as cap:
            try:
                while True:
                    chunk = cap.read(self.settings.chunk_seconds)
                    if chunk is None:
                        time.sleep(0.05)
                        continue
                    self.handle_pcm(chunk.pcm, chunk.sample_rate, chunk.t0)
            except KeyboardInterrupt:
                print("\nstopped.", file=sys.stderr)
        self.close()

    def run_loopback(self) -> None:
        dev = find_loopback_device()
        if dev is None:
            print(
                "No system-audio device found.\n"
                "macOS: install BlackHole 2ch, set it as the output (or use a Multi-Output Device).\n"
                "Windows: enable Stereo Mix, or install VB-Audio Cable.\n"
                "Then run: liveline devices\n"
                "Or use: liveline mic   /   liveline file movie.mp4",
                file=sys.stderr,
            )
            sys.exit(2)
        print(f"using loopback device [{dev.index}] {dev.name}", file=sys.stderr)
        self.run_device(dev.index)

    def run_file(self, path: Path | str, write_srt: Path | str | None = None) -> list[Caption]:
        self.setup()
        path = Path(path)
        print(f"processing {path}…", file=sys.stderr)
        captions: list[Caption] = []
        srt_rows = []
        idx = 1
        for chunk in iter_file(path, chunk_seconds=self.settings.chunk_seconds):
            cap = self.handle_pcm(chunk.pcm, chunk.sample_rate, chunk.t0)
            if cap is None:
                continue
            captions.append(cap)
            if write_srt:
                start = chunk.t0
                end = chunk.t0 + self.settings.chunk_seconds
                text = cap.translated or cap.original
                srt_rows.append(_srt_block(idx, start, end, text))
                idx += 1
            # paced a little so overlay is watchable when not live
            time.sleep(0.05)
        if write_srt:
            out = Path(write_srt)
            out.write_text("\n".join(srt_rows), encoding="utf-8")
            print(f"wrote {out}", file=sys.stderr)
        self.close()
        return captions

    def close(self) -> None:
        for sink in self._sinks:
            if hasattr(sink, "close"):
                sink.close()


def _srt_block(i: int, start: float, end: float, text: str) -> str:
    return f"{i}\n{_ts(start)} --> {_ts(end)}\n{text}\n"


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def print_devices() -> None:
    devices = list_devices()
    loop = find_loopback_device()
    if not devices:
        print("No input devices found.")
        return
    for d in devices:
        mark = "  <-- loopback candidate" if loop and d.index == loop.index else ""
        print(f"[{d.index:>2}] {d.name}  ({d.channels} ch, {d.hostapi}){mark}")
