import numpy as np
import pytest

from liveline.audio import write_wav, iter_file, SAMPLE_RATE
from liveline.translate import Translator, normalize_lang, is_sentence_like
from liveline.pipeline import _ts, _srt_block


def test_normalize_lang():
    assert normalize_lang("korean") == "ko"
    assert normalize_lang("zh") == "zh-CN"
    assert normalize_lang("JP") == "ja"


def test_is_sentence_like():
    assert is_sentence_like("Hello there, friend.")
    assert is_sentence_like("안녕하세요.")
    assert not is_sentence_like("hi")


def test_translator_same_language_passthrough():
    t = Translator(source="en", target="en")
    assert t.translate("hello world") == "hello world"


def test_srt_timestamp():
    assert _ts(0) == "00:00:00,000"
    assert _ts(3661.5) == "01:01:01,500"
    block = _srt_block(1, 0, 2.5, "hello")
    assert block.startswith("1\n00:00:00,000 --> 00:00:02,500\nhello")


def test_iter_file_chunks(tmp_path):
    rng = np.random.default_rng(0)
    pcm = (rng.standard_normal(SAMPLE_RATE * 5) * 0.1).astype(np.float32)
    path = write_wav(tmp_path / "a.wav", pcm)
    chunks = list(iter_file(path, chunk_seconds=2.0, hop_seconds=2.0))
    assert len(chunks) >= 2
    assert chunks[0].pcm.shape[0] == SAMPLE_RATE * 2


@pytest.mark.integration
def test_translate_korean_smoke():
    t = Translator(source="ko", target="en")
    out = t.translate("안녕하세요")
    assert out
    assert out != "안녕하세요" or "translation unavailable" in out
