"""PyInstaller entrypoint for the Liveline macOS / Windows app."""
from liveline.app import run

if __name__ == "__main__":
    raise SystemExit(run())
