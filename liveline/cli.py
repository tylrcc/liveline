from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="liveline",
        description="Live translated subtitles for dramas, videos, and songs.",
    )
    parser.add_argument("--version", action="version", version=f"liveline {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--from", dest="source_lang", default="ko",
                        help="source language: ko, zh, ja, en, auto (default: ko)")
    common.add_argument("--to", dest="target_lang", default="en",
                        help="target language (default: en)")
    common.add_argument("--model", default="base",
                        help="whisper size: tiny, base, small, medium, large-v3 (default: base)")
    common.add_argument("--device", default="auto", help="cpu, cuda, or auto")
    common.add_argument("--chunk", type=float, default=3.0, help="seconds of audio per pass")
    common.add_argument("--overlay", choices=["window", "web", "both", "none"], default="window")
    common.add_argument("--port", type=int, default=8765, help="web overlay port")
    common.add_argument("--mono", action="store_true", help="show translation only, hide original")

    p = sub.add_parser("live", parents=[common], help="caption system audio (BlackHole / Stereo Mix)")
    p.add_argument("--device-index", type=int, help="force a sounddevice input index")

    sub.add_parser("mic", parents=[common], help="caption the default microphone")

    f = sub.add_parser("file", parents=[common], help="caption a local video or audio file")
    f.add_argument("path", type=Path)
    f.add_argument("--srt", type=Path, help="also write an .srt file")

    sub.add_parser("devices", help="list audio input devices")

    d = sub.add_parser("drama", parents=[common],
                       help="preset for Korean / Chinese dramas over system audio")
    d.add_argument("--lang", choices=["ko", "zh", "ja"], default="ko",
                   help="drama language (default: ko)")

    args = parser.parse_args(argv)

    if args.cmd == "devices":
        from .pipeline import print_devices
        print_devices()
        return 0

    from .pipeline import Pipeline, Settings

    if args.cmd == "drama":
        source = args.lang
    else:
        source = getattr(args, "source_lang", "ko")

    settings = Settings(
        source_lang=source,
        target_lang=getattr(args, "target_lang", "en"),
        model=getattr(args, "model", "base"),
        device=getattr(args, "device", "auto"),
        chunk_seconds=getattr(args, "chunk", 3.0),
        bilingual=not getattr(args, "mono", False),
        overlay=getattr(args, "overlay", "window"),
        port=getattr(args, "port", 8765),
    )
    pipe = Pipeline(settings)

    if args.cmd in ("live", "drama"):
        if getattr(args, "device_index", None) is not None:
            pipe.run_device(args.device_index)
        else:
            pipe.run_loopback()
    elif args.cmd == "mic":
        pipe.run_device(None)
    elif args.cmd == "file":
        pipe.run_file(args.path, write_srt=args.srt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
