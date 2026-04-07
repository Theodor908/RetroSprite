# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for RetroSprite."""
import re

# Read version from source
with open('src/__init__.py', 'r') as f:
    _version_match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", f.read())
    VERSION = _version_match.group(1) if _version_match else '0.0.0'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('icons', 'icons'),
    ],
    hiddenimports=['PIL._tkinter_finder', 'numpy', 'numpy.core._methods',
                   'svglib', 'svglib.svglib', 'reportlab',
                   'reportlab.graphics', 'reportlab.graphics.renderPM',
                   'psd_tools', 'psd_tools.psd', 'psd_tools.psd.header'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RetroSprite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window — GUI app
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RetroSprite',
)
