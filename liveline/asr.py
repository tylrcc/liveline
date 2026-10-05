"""Speech recognition via faster-whisper."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Transcript:
    text: str
    language: str | None
    start: float
    end: float
    no_speech_prob: float = 0.0


class Transcriber:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "default",
        language: str | None = None,
    ):
        from faster_whisper import WhisperModel

        if device == "auto":
            device = "cpu"
            compute_type = compute_type if compute_type != "default" else "int8"
        elif compute_type == "default":
            compute_type = "float16" if device == "cuda" else "int8"

        self.language = language
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, pcm: np.ndarray, sample_rate: int = 16_000) -> Transcript | None:
        if pcm.size == 0 or float(np.abs(pcm).mean()) < 1e-4:
            return None
        segments, info = self.model.transcribe(
            pcm,
            language=self.language,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            without_timestamps=False,
        )
        parts = []
        start = end = 0.0
        no_speech = 1.0
        for i, seg in enumerate(segments):
            t = seg.text.strip()
            if not t:
                continue
            parts.append(t)
            if i == 0:
                start = float(seg.start)
            end = float(seg.end)
            no_speech = min(no_speech, float(seg.no_speech_prob))
        if not parts:
            return None
        return Transcript(
            text=" ".join(parts),
            language=getattr(info, "language", self.language),
            start=start,
            end=end,
            no_speech_prob=no_speech,
        )
