"""Launch the Liveline desktop app."""
from __future__ import annotations

import sys
import time
import webbrowser


def run(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> int:
    from .server import AppServer

    server = AppServer(host=host, port=port)
    server.start()
    print(f"Liveline is running at {server.url}", flush=True)
    try:
        server.wait_ready()
    except TimeoutError as exc:
        print(exc, file=sys.stderr)
        return 1

    # Native windows (control + always-on-top captions) when pywebview is available.
    # webview.start() blocks the main thread, which is required on macOS.
    if _start_native(server.url, server.overlay_url):
        server.session.stop()
        return 0

    if open_browser:
        webbrowser.open(server.url)
        time.sleep(0.3)
        webbrowser.open_new(server.overlay_url)

    print("Press Ctrl+C to quit.", flush=True)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nQuitting Liveline.", flush=True)
        server.session.stop()
    return 0


def _start_native(control_url: str, overlay_url: str) -> bool:
    try:
        import webview
    except ImportError:
        return False
    try:
        webview.create_window(
            "Liveline",
            control_url,
            width=460,
            height=780,
            background_color="#0c0d10",
        )
        webview.create_window(
            "Liveline Captions",
            overlay_url,
            width=980,
            height=180,
            on_top=True,
            frameless=True,
            easy_drag=True,
            background_color="#000000",
        )
        webview.start()
        return True
    except Exception as exc:
        print(f"native windows unavailable ({exc}); using the browser UI", flush=True)
        return False


if __name__ == "__main__":
    raise SystemExit(run())
