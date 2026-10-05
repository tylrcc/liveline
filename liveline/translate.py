"""Translation backends.

Order: optional Argos (offline) → Google → MyMemory → original text.
Failed network calls never poison the caption with error strings.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

LANG_ALIASES = {
    "korean": "ko", "kr": "ko", "ko": "ko",
    "chinese": "zh-CN", "zh": "zh-CN", "zh-cn": "zh-CN", "zh-tw": "zh-TW", "cn": "zh-CN",
    "japanese": "ja", "jp": "ja", "ja": "ja",
    "english": "en", "en": "en",
    "spanish": "es", "es": "es",
    "french": "fr", "fr": "fr",
    "german": "de", "de": "de",
    "auto": "auto",
}

# Argos / Whisper language codes are short
ARGOS_CODES = {"zh-CN": "zh", "zh-TW": "zh", "zh": "zh"}


def normalize_lang(code: str) -> str:
    return LANG_ALIASES.get(code.lower().strip(), code.lower().strip())


def _short(code: str) -> str:
    code = normalize_lang(code)
    return ARGOS_CODES.get(code, code.split("-")[0])


@dataclass
class Translator:
    source: str = "auto"
    target: str = "en"
    prefer_offline: bool = True
    _cache: dict[str, str] = field(default_factory=dict, repr=False)
    _last_call: float = 0.0
    _argos = None

    def __post_init__(self):
        self.source = normalize_lang(self.source)
        self.target = normalize_lang(self.target)
        if self.prefer_offline:
            self._argos = self._load_argos()

    def _load_argos(self):
        try:
            import argostranslate.package
            import argostranslate.translate
        except ImportError:
            return None
        src, tgt = _short(self.source if self.source != "auto" else "ko"), _short(self.target)
        installed = argostranslate.translate.get_installed_languages()
        from_lang = next((l for l in installed if l.code == src), None)
        to_lang = next((l for l in installed if l.code == tgt), None)
        if from_lang and to_lang:
            return from_lang.get_translation(to_lang)
        # try to install the language pack once
        try:
            argostranslate.package.update_package_index()
            available = argostranslate.package.get_available_packages()
            pkg = next((p for p in available if p.from_code == src and p.to_code == tgt), None)
            if pkg is None:
                return None
            log.info("installing Argos package %s → %s", src, tgt)
            argostranslate.package.install_from_path(pkg.download())
            installed = argostranslate.translate.get_installed_languages()
            from_lang = next(l for l in installed if l.code == src)
            to_lang = next(l for l in installed if l.code == tgt)
            return from_lang.get_translation(to_lang)
        except Exception as exc:
            log.warning("Argos offline translation unavailable: %s", exc)
            return None

    def translate(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        if self.source != "auto" and _short(self.source) == _short(self.target):
            return text
        key = text.lower()
        if key in self._cache:
            return self._cache[key]

        out = None
        if self._argos is not None:
            try:
                out = self._argos.translate(text)
            except Exception as exc:
                log.debug("Argos failed: %s", exc)

        if not out:
            out = self._online(text)

        if not out:
            out = text
        self._cache[key] = out
        if len(self._cache) > 512:
            for k in list(self._cache)[:256]:
                self._cache.pop(k, None)
        return out

    def _online(self, text: str) -> str | None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < 0.4:
            time.sleep(0.4 - elapsed)
        self._last_call = time.monotonic()
        src = "auto" if self.source == "auto" else self.source
        # Google, then MyMemory
        for name, factory in (
            ("google", lambda: __import__("deep_translator", fromlist=["GoogleTranslator"]).GoogleTranslator(source=src, target=self.target)),
            ("mymemory", lambda: __import__("deep_translator", fromlist=["MyMemoryTranslator"]).MyMemoryTranslator(source=src if src != "auto" else "ko-KR", target=self.target if self.target != "en" else "en-US")),
        ):
            try:
                result = factory().translate(text)
                if result and not result.startswith("MYMEMORY WARNING"):
                    return result
            except Exception as exc:
                log.warning("%s translation failed: %s", name, exc)
        return None


_PUNCT_END = re.compile(r"[.!?…。！？]$")


def is_sentence_like(text: str) -> bool:
    text = text.strip()
    return len(text) >= 12 or bool(_PUNCT_END.search(text))
