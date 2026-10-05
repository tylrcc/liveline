"""Always-on-top subtitle window (tkinter)."""
from __future__ import annotations

import queue
import threading

from .types import Caption


class Overlay:
    """Bottom-of-screen caption bar. Drag to move. Esc or close to quit."""

    def __init__(self, bilingual: bool = True, font_size: int = 28):
        self.bilingual = bilingual
        self.font_size = font_size
        self._q: queue.Queue[Caption | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        try:
            import tkinter  # noqa: F401
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "tkinter is not available in this Python. "
                "Use --overlay web or --overlay none, or install a Python build with Tk."
            ) from exc
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def show(self, caption: Caption) -> None:
        self._q.put(caption)

    def close(self) -> None:
        self._q.put(None)

    def _run(self) -> None:
        import tkinter as tk

        root = tk.Tk()
        root.title("liveline")
        root.attributes("-topmost", True)
        try:
            root.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        root.configure(bg="#000000")
        root.overrideredirect(True)

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        width, height = int(sw * 0.8), 120 if self.bilingual else 72
        x, y = (sw - width) // 2, sh - height - 60
        root.geometry(f"{width}x{height}+{x}+{y}")

        translated = tk.Label(
            root, text="listening…", fg="#ffffff", bg="#000000",
            font=("Helvetica", self.font_size, "bold"), wraplength=width - 40, justify="center",
        )
        translated.pack(fill="both", expand=True, padx=16, pady=(12, 4))
        original = None
        if self.bilingual:
            original = tk.Label(
                root, text="", fg="#9ca3af", bg="#000000",
                font=("Helvetica", max(14, self.font_size - 10)), wraplength=width - 40, justify="center",
            )
            original.pack(fill="x", padx=16, pady=(0, 12))

        state = {"x": 0, "y": 0}

        def start_drag(e):
            state["x"], state["y"] = e.x_root - root.winfo_x(), e.y_root - root.winfo_y()

        def on_drag(e):
            root.geometry(f"+{e.x_root - state['x']}+{e.y_root - state['y']}")

        for w in (root, translated) + ((original,) if original else ()):
            w.bind("<Button-1>", start_drag)
            w.bind("<B1-Motion>", on_drag)

        def on_key(e):
            if e.keysym in ("Escape", "q"):
                root.destroy()

        root.bind("<Key>", on_key)

        def poll():
            try:
                while True:
                    item = self._q.get_nowait()
                    if item is None:
                        root.destroy()
                        return
                    translated.config(text=item.translated or item.original)
                    if original is not None:
                        original.config(text=item.original if item.translated else "")
            except queue.Empty:
                pass
            root.after(80, poll)

        poll()
        root.mainloop()
