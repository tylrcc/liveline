#!/bin/bash
# Double-click this file to launch Liveline without building an .app first.
cd "$(dirname "$0")/.." || exit 1
if [[ ! -x .venv/bin/liveline ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -e ".[gui]"
fi
exec .venv/bin/liveline app
