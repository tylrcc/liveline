# liveline

Live translated subtitles for anything you watch or listen to.

Point it at system audio while a Korean or Chinese drama plays, or drop in a
video file. Whisper listens, a translator rewrites the line, and an always-on-top
overlay (or browser page) shows the caption.

```bash
pip install -e .
liveline drama --lang ko          # system audio, Korean → English
liveline drama --lang zh          # Chinese drama
liveline file episode.mp4 --from ko --to en --srt out.srt
liveline mic --from ja --to en    # headphones / mic
```

Works with dramas, YouTube, local files, and (with lower accuracy) songs.

## How it works

```
audio in  →  Whisper (ASR)  →  translate  →  overlay
```

| Mode | What it captures |
|---|---|
| `liveline drama` / `live` | System audio via BlackHole (macOS) or Stereo Mix / VB-Cable (Windows) |
| `liveline mic` | Default microphone |
| `liveline file` | Any video/audio ffmpeg can read |

Display options: desktop overlay window, browser page at `http://127.0.0.1:8765/overlay`
(OBS browser source friendly), or both.

## Setup

### 1. Install

Needs Python 3.10+ and [ffmpeg](https://ffmpeg.org/) on your PATH.

```bash
git clone https://github.com/tylrcc/liveline
cd liveline
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The first run downloads a Whisper model (`base` by default, ~150 MB).

### 2. Route system audio (for live dramas)

**macOS**

1. Install [BlackHole 2ch](https://existential.audio/blackhole/).
2. Open Audio MIDI Setup → create a Multi-Output Device with your speakers and BlackHole.
3. Set that Multi-Output as the system output so you can still hear the show.
4. Confirm BlackHole shows up:

```bash
liveline devices
```

**Windows**

Enable Stereo Mix, or install [VB-Audio Cable](https://vb-audio.com/Cable/), then pick it with `liveline devices`.

### 3. Watch

```bash
# Korean drama → English overlay
liveline drama --lang ko

# Chinese drama, larger model, bilingual overlay + browser page
liveline drama --lang zh --model small --overlay both
```

Play the episode in your browser or player. Captions appear in the floating
window. Drag to reposition. Esc closes it.

## File mode

Generate captions (and an `.srt`) for a downloaded episode:

```bash
liveline file drama.mkv --from ko --to en --model small --srt drama.en.srt --overlay none
```

## Songs

Speech-to-text on music is harder: beats and harmony confuse the model. It can
still catch clear vocals, especially with `--model small` or `medium`, but do
not expect karaoke-perfect lyrics. Dramas and talk tracks work much better.

## Options

```
--from ko|zh|ja|en|auto     source language (drama preset sets this)
--to en                     target language
--model tiny|base|small|…   Whisper size (base is the default tradeoff)
--chunk 3.0                 seconds of audio per pass
--overlay window|web|both|none
--mono                      hide the original line, show translation only
--device cpu|cuda|auto
```

## Privacy

Audio is processed on your machine by Whisper. Translation prefers **Argos
Translate** (offline language packs, installed on first use for ko→en / zh→en).
If Argos is missing a pair it falls back to Google, then MyMemory. No audio is
uploaded for recognition.

## Layout

```
liveline/
  audio.py       mic / loopback / file decode
  asr.py         faster-whisper
  translate.py   language normalize + translator
  overlay.py     always-on-top window
  server.py      browser / OBS overlay
  pipeline.py    glue
  cli.py
```

```bash
make test
make demo    # synthesizes a short Korean clip and captions it
```

MIT.
