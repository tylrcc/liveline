"""Audio capture from microphone, system loopback, or media files."""
from __future__ import annotations

import subprocess
import threading
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

SAMPLE_RATE = 16_000


@dataclass
class AudioChunk:
    pcm: np.ndarray  # float32 mono, -1..1
    sample_rate: int = SAMPLE_RATE
    t0: float = 0.0  # seconds since stream start


@dataclass
class DeviceInfo:
    index: int
    name: str
    channels: int
    is_input: bool
    hostapi: str = ""


def list_devices() -> list[DeviceInfo]:
    import sounddevice as sd

    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            host = sd.query_hostapis(d["hostapi"])["name"]
            out.append(DeviceInfo(i, d["name"], d["max_input_channels"], True, host))
    return out


def find_loopback_device() -> DeviceInfo | None:
    """Best-effort system-audio device (BlackHole, Soundflower, VB-Cable, WASAPI loopback)."""
    keys = ("blackhole", "soundflower", "cable", "loopback", "stereo mix", "what u hear")
    for d in list_devices():
        if any(k in d.name.lower() for k in keys):
            return d
    return None


class LiveCapture:
    """Ring-buffer capture from a sounddevice input."""

    def __init__(self, device: int | str | None = None, sample_rate: int = SAMPLE_RATE, channels: int = 1):
        import sounddevice as sd

        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._buf: deque[np.ndarray] = deque()
        self._lock = threading.Lock()
        self._frames = 0
        self._stream = sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            device=device,
            blocksize=int(sample_rate * 0.1),
            callback=self._callback,
        )

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata.reshape(-1)
        with self._lock:
            self._buf.append(mono.copy())
            self._frames += len(mono)

    def start(self) -> None:
        self._stream.start()

    def stop(self) -> None:
        self._stream.stop()
        self._stream.close()

    def read(self, seconds: float) -> AudioChunk | None:
        need = int(seconds * self.sample_rate)
        with self._lock:
            if not self._buf:
                return None
            data = np.concatenate(list(self._buf)) if len(self._buf) > 1 else self._buf[0]
            if len(data) < need:
                return None
            take, keep = data[:need], data[need:]
            self._buf.clear()
            if len(keep):
                self._buf.append(keep)
            t0 = (self._frames - len(data)) / self.sample_rate
        return AudioChunk(take.astype(np.float32), self.sample_rate, t0)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()


def load_file(path: Path | str, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Decode media to mono float32 PCM.

    `.wav` files are read directly. Anything else goes through ffmpeg.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".wav":
        return _read_wav(path, sample_rate)

    cmd = [
        "ffmpeg", "-v", "error", "-i", str(path),
        "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(sample_rate),
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace") or "ffmpeg failed")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def _read_wav(path: Path, sample_rate: int) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        n = w.getnchannels()
        rate = w.getframerate()
        width = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif width == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise RuntimeError(f"unsupported wav sample width: {width}")
    if n > 1:
        data = data.reshape(-1, n).mean(axis=1)
    if rate != sample_rate:
        duration = len(data) / rate
        target = int(duration * sample_rate)
        x_old = np.linspace(0, 1, len(data), endpoint=False)
        x_new = np.linspace(0, 1, target, endpoint=False)
        data = np.interp(x_new, x_old, data).astype(np.float32)
    return data


def iter_file(path: Path | str, chunk_seconds: float = 3.0, hop_seconds: float | None = None,
              sample_rate: int = SAMPLE_RATE) -> Iterator[AudioChunk]:
    """Sliding windows over a media file for near-live style processing."""
    pcm = load_file(path, sample_rate)
    hop = hop_seconds if hop_seconds is not None else chunk_seconds * 0.75
    size = int(chunk_seconds * sample_rate)
    step = max(int(hop * sample_rate), 1)
    if len(pcm) <= size:
        yield AudioChunk(pcm, sample_rate, 0.0)
        return
    for start in range(0, len(pcm) - size + 1, step):
        yield AudioChunk(pcm[start:start + size], sample_rate, start / sample_rate)
    last = len(pcm) - size
    if last % step:
        yield AudioChunk(pcm[last:], sample_rate, last / sample_rate)


def write_wav(path: Path | str, pcm: np.ndarray, sample_rate: int = SAMPLE_RATE) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(pcm, -1, 1)
    pcm16 = (clipped * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16.tobytes())
    return path
