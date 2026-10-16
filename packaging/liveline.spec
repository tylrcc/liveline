# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None
root = Path(SPECPATH).resolve().parent

datas = collect_data_files("liveline")
datas += [(str(root / "liveline" / "web"), "liveline/web")]

hidden = [
    "faster_whisper",
    "ctranslate2",
    "av",
    "sounddevice",
    "argostranslate",
    "deep_translator",
    "fastapi",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "multipart",
    "pydantic",
]

binaries = []
tmp_ret = collect_all("ctranslate2")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hidden += tmp_ret[2]

a = Analysis(
    [str(root / "liveline" / "__main__.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch", "torchvision", "torchaudio", "tensorflow", "tensorboard",
        "spacy", "thinc", "stanza", "argostranslate", "pytest", "IPython",
        "notebook", "matplotlib", "tkinter", "_tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Liveline",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Liveline",
)

app = BUNDLE(
    coll,
    name="Liveline.app",
    icon=None,
    bundle_identifier="com.tylrcc.liveline",
    info_plist={
        "CFBundleName": "Liveline",
        "CFBundleDisplayName": "Liveline",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        "NSMicrophoneUsageDescription": "Liveline listens to audio to generate live subtitles.",
        "NSHighResolutionCapable": True,
        "LSUIElement": False,
    },
)
