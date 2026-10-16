#!/usr/bin/env bash
# Install Liveline on macOS (Apple Silicon) with one command:
#   curl -fsSL https://raw.githubusercontent.com/tylrcc/liveline/main/scripts/install.sh | bash
set -euo pipefail

REPO="tylrcc/liveline"
APP_NAME="Liveline"
INSTALL_DIR="${LIVELINE_INSTALL_DIR:-/Applications}"
TMP="$(mktemp -d /tmp/liveline-install.XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Liveline's one-line installer currently supports macOS only." >&2
  exit 1
fi

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This build is for Apple Silicon (arm64). Your Mac is $(uname -m)." >&2
  exit 1
fi

echo "Finding latest Liveline release…"
ASSET_URL="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); a=next((x for x in r.get("assets",[]) if x["name"].endswith(".dmg")), None); print(a["browser_download_url"] if a else "")')"

if [[ -z "$ASSET_URL" ]]; then
  echo "Could not find a .dmg on the latest GitHub release." >&2
  exit 1
fi

DMG="$TMP/Liveline.dmg"
echo "Downloading…"
curl -fL --progress-bar -o "$DMG" "$ASSET_URL"

echo "Mounting…"
MOUNT="$(hdiutil attach "$DMG" -nobrowse -readonly | awk 'END{for(i=3;i<=NF;i++) printf (i>3?" ":"") $i; print ""}')"
if [[ -z "$MOUNT" || ! -d "$MOUNT" ]]; then
  echo "Failed to mount the disk image." >&2
  exit 1
fi

SRC="$MOUNT/${APP_NAME}.app"
if [[ ! -d "$SRC" ]]; then
  echo "Liveline.app not found inside the disk image." >&2
  hdiutil detach "$MOUNT" -quiet || true
  exit 1
fi

DEST="${INSTALL_DIR}/${APP_NAME}.app"
echo "Installing to ${DEST}…"
mkdir -p "$INSTALL_DIR"
rm -rf "$DEST"
ditto "$SRC" "$DEST"
hdiutil detach "$MOUNT" -quiet || true

# Clear quarantine so Gatekeeper does not block first launch from a curl install
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true

echo
echo "Installed ${APP_NAME} to ${DEST}"
echo "Open it with:  open -a Liveline"
if [[ "${LIVELINE_OPEN:-1}" == "1" ]]; then
  open -a "$APP_NAME" || open "$DEST"
fi

echo
echo "First time using system audio captions? Install BlackHole 2ch, then create a"
echo "Multi-Output Device (speakers + BlackHole) in Audio MIDI Setup:"
echo "  https://existential.audio/blackhole/"
