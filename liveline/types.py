from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Caption:
    original: str
    translated: str
    language: str | None = None
