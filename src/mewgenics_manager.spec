# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['mewgenics_manager.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../locales/en.json', '.'),
        ('../locales/ru.json', '.'),
        ('../locales/zh_CN.json', '.'),
    ],
    hiddenimports=[
        'lz4.frame',
        'lz4.block',
        'visual_mutation_catalog',
    ],
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
    a.binaries,
    a.datas,
    [],
    name='MewgenicsManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
