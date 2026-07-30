# PyInstaller spec for the Aeon Application Windows launcher.
#
# Produces a onedir bundle at dist/aeon-launcher/ containing the
# launcher executable, the pinned Aeon Language runtime, and every
# resource file needed for certified startup verification.
#
# Invoke from the aeon-application/ directory (not from packaging/windows):
#     pyinstaller --clean --noconfirm packaging/windows/aeon-launcher.spec
#
# so that dist/ and build/ land at aeon-application/dist/ and
# aeon-application/build/. The Inno Setup script assumes that layout.

# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all

# Path anchoring: SPECPATH is the directory of this spec file
# (aeon-application/packaging/windows). Everything else is derived
# from SPECPATH so the invocation directory doesn't matter for path
# resolution.
APP_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
REPO_ROOT = os.path.abspath(os.path.join(APP_ROOT, ".."))
LANG_ROOT = os.path.join(REPO_ROOT, "aeon-language")

datas = []
binaries = []
hiddenimports = []

for pkg in ("aeon", "aeon_app"):
    a_datas, a_binaries, a_hidden = collect_all(pkg)
    datas.extend(a_datas)
    binaries.extend(a_binaries)
    hiddenimports.extend(a_hidden)


block_cipher = None


a = Analysis(
    [os.path.join(APP_ROOT, "src", "aeon_app", "launcher", "__main__.py")],
    pathex=[
        os.path.join(APP_ROOT, "src"),
        LANG_ROOT,
        os.path.join(LANG_ROOT, "standard_library"),
    ],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["aeon", "aeon_app", "aeon_app.launcher"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="aeon-launcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # Show a console; certified failures print JSON to stdout.
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    name="aeon-launcher",
)
