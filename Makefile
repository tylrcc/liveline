.PHONY: setup test devices demo app build

setup:
	python3 -m venv .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install -q -e ".[dev,gui]"

test:
	.venv/bin/pytest -q -m "not integration"

devices:
	.venv/bin/liveline devices

demo:
	.venv/bin/python scripts/make_demo_audio.py
	.venv/bin/liveline file data/demo_ko.wav --from ko --to en --overlay none --model tiny --srt data/demo_ko.srt

app:
	.venv/bin/liveline app

build:
	bash scripts/build_macos.sh