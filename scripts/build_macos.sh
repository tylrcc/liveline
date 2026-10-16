#!/usr/bin/env bash
# Build a double-clickable macOS Liveline.app and a .dmg next to it.
# Uses a lean packaging venv (no Argos/Torch) so the download stays workable.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BUILD_VENV="$ROOT/.venv-app"
PY="$BUILD_VENV/bin/python"

if [[ ! -x "$PY" ]]; then
  python3 -m venv "$BUILD_VENV"
fi

"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -e ".[dev,app]"
rm -rf build dist
"$PY" -m PyInstaller --noconfirm --clean packaging/liveline.spec

APP="$ROOT/dist/Liveline.app"
DMG="$ROOT/dist/Liveline-0.2.0-macos.dmg"
if [[ -d "$APP" ]]; then
  rm -f "$DMG"
  hdiutil create -volname "Liveline" -srcfolder "$APP" -ov -format UDZO "$DMG"
  echo "Built:"
  echo "  $APP"
  echo "  $DMG"
  du -sh "$APP" "$DMG"
else
  echo "Liveline.app was not produced" >&2
  ls -la dist || true
  exit 1
fi
