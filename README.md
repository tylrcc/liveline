# liveline

Live translated subtitles for anything you watch.

Open the app, press **Start subtitles**, play a Korean or Chinese drama (or
anything else), and read the captions in the floating window.

```bash
# easiest while developing
./Liveline.command

# or
pip install -e ".[gui]"
liveline
```

## Install (one line)

```bash
curl -fsSL https://raw.githubusercontent.com/tylrcc/liveline/main/scripts/install.sh | bash
```

That downloads the latest Mac release, puts `Liveline.app` in `/Applications`, and opens it.

Or grab the DMG from [Releases](https://github.com/tylrcc/liveline/releases/latest).

### Build from this repo

```bash
./scripts/build_macos.sh
```

Writes `dist/Liveline.app` and `dist/Liveline-0.2.0-macos.dmg`.

> First launch downloads a Whisper model (~75 to 150 MB). The Mac app translates
> online by default. For fully offline translation when installing from source:
> `pip install -e ".[offline]"`.

## How to use it

1. Open Liveline.
2. Pick the spoken language (Korean / Chinese / Japanese / Auto).
3. Pick subtitle language (English by default).
4. Choose **What I am watching** for system audio, or Microphone.
5. Press **Start subtitles**.
6. Play your show. Captions appear in the overlay window.

### One-time system audio setup (Mac)

To caption Netflix, Viki, YouTube, local players, and games, Liveline needs to
hear your Mac's output:

1. Install [BlackHole 2ch](https://existential.audio/blackhole/).
2. Open **Audio MIDI Setup** → create a **Multi-Output Device** with your
   speakers/headphones **and** BlackHole.
3. Set that Multi-Output as the system sound output so you still hear the show.
4. In Liveline, press **Recheck audio**, then **Start**.

Windows users: enable Stereo Mix, or install [VB-Audio Cable](https://vb-audio.com/Cable/).

The app detects this for you and shows the setup steps if audio is missing.

## What works well

| Content | Expectation |
|---|---|
| Dramas, movies, interviews, lectures | Strong |
| YouTube / browser videos via system audio | Strong |
| Clear singing | Mixed |
| Heavy music beds / overlapping talk | Weaker |

Use **Accurate** quality for harder audio. **Fast** is best on older machines.

## Terminal commands (optional)

```bash
liveline                     # open the app
liveline devices             # list audio inputs
liveline file show.mkv --from ko --to en --srt show.en.srt
liveline drama --lang zh     # CLI live mode
```

## Privacy

Speech recognition runs locally (Whisper). Translation uses an online fallback
by default in the Mac app. Install `.[offline]` for Argos packs that never leave
your machine.

## Develop

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,gui]"
pytest -q -m "not integration"
liveline app
```

MIT.
