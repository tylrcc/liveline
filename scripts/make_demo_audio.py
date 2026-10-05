"""Generate a short Korean (and Chinese) spoken demo clip using macOS `say`."""
from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"
TARGET_RATE = 16_000


def pick_voice(lang_tag: str, preferred: list[str]) -> str | None:
    """Return a `say -v` voice name for the given locale."""
    lines = subprocess.check_output(["say", "-v", "?"], text=True).splitlines()
    # Prefer dedicated voices (Yuna, Tingting) over multi-lingual Eddy variants
    available = {}
    for line in lines:
        if lang_tag not in line:
            continue
        name = line.split("#")[0].strip()
        # "Yuna                ko_KR" or "Eddy (Korean (South Korea)) ko_KR"
        voice = name.rsplit(" ", 1)[0].strip() if name.endswith(lang_tag) else name
        # Keep short canonical names when present
        short = voice.split()[0]
        available[short.lower()] = short
        available[voice.lower()] = voice
    for pref in preferred:
        if pref.lower() in available:
            return available[pref.lower()]
    # fall back to any matching voice short name
    for line in lines:
        if lang_tag in line:
            return line.split()[0]
    return None


def aiff_to_wav(aiff: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.wav")
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(tmp)], check=True)
    with wave.open(str(tmp), "rb") as w:
        rate, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        raw = w.readframes(n)
    tmp.unlink(missing_ok=True)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if rate != TARGET_RATE:
        target = int(len(data) / rate * TARGET_RATE)
        data = np.interp(
            np.linspace(0, 1, target, endpoint=False),
            np.linspace(0, 1, len(data), endpoint=False),
            data,
        ).astype(np.float32)
    pcm16 = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TARGET_RATE)
        w.writeframes(pcm16.tobytes())


def synth(text: str, voice: str, dest: Path) -> None:
    aiff = dest.with_suffix(".aiff")
    # Use the voice name; for multi-variant Eddy, prefer dedicated names instead
    subprocess.run(["say", "-v", voice, "-r", "160", text, "-o", str(aiff)], check=True)
    aiff_to_wav(aiff, dest)
    aiff.unlink(missing_ok=True)
    info = dest.stat().st_size
    if info < 2000:
        raise RuntimeError(f"{dest} looks empty ({info} bytes); voice '{voice}' may be wrong")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ko = pick_voice("ko_KR", ["Yuna", "Sandy", "Jinha", "Flo"])
    zh = pick_voice("zh_CN", ["Tingting", "Meijia", "Sinji", "Lili"])

    if ko:
        synth("안녕하세요. 오늘 저녁에 같이 드라마 볼래요? 자막이 자동으로 번역됩니다.", ko, OUT / "demo_ko.wav")
        print(f"wrote {OUT / 'demo_ko.wav'} with voice {ko}")
    else:
        print("No Korean macOS voice installed. Skipping demo_ko.wav", file=sys.stderr)

    if zh:
        synth("你好。我们今晚一起看电视剧吧。字幕会自动翻译成英文。", zh, OUT / "demo_zh.wav")
        print(f"wrote {OUT / 'demo_zh.wav'} with voice {zh}")
    else:
        print("No Chinese macOS voice installed. Skipping demo_zh.wav", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
