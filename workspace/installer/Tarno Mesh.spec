# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

# SPECPATH wird von PyInstaller bereitgestellt und zeigt auf den Ordner der
# .spec-Datei (workspace/installer/, also zwei Ebenen unterm Repo-Root).
PROJECT_ROOT = Path(SPECPATH).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
ICON_PATH = SRC_DIR / "TARNO.UI" / "Assets" / "app.ico"

a = Analysis(
    [str(SRC_DIR / "tarno_backend" / "__main__.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[
        (str(ICON_PATH), "TARNO.UI/Assets")
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Tarno Mesh',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Tarno Mesh',
)