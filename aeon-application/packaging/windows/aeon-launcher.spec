# PyInstaller spec for the Aeon Application Windows launcher.
#
# Produces a onedir bundle at dist/aeon-launcher/ containing the
# launcher executable, the pinned Aeon Language runtime, and every
# resource file needed for certified startup verification.
#
# Invoke from the repo root:
#     pyinstaller --clean --noconfirm packaging/windows/aeon-launcher.spec
#
# The resulting dist/aeon-launcher/ is passed to Inno Setup by
# packaging/windows/aeon-installer.iss.

# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all

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
    ["../../src/aeon_app/launcher/__main__.py"],
    pathex=[
        os.path.abspath("../../src"),
        os.path.abspath("../../../aeon-language"),
        os.path.abspath("../../../aeon-language/standard_library"),
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
