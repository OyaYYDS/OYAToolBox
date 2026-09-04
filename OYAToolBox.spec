# -*- mode: python ; coding: utf-8 -*-
# OYAToolBox 打包脚本 (pywebview + WebView2)
# WebView2 内核由系统提供, 无需打包; 只收集 pythonnet(clr) 与 webview 包资源
from PyInstaller.utils.hooks import collect_all

datas = [('web', 'web'), ('OYAToolBoxICO.ico', '.')]
binaries = []
hiddenimports = []

# pythonnet (clr) - pywebview edgechromium 后端依赖
tmp = collect_all('clr')
datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

# webview 包资源 (WebView2Loader.dll, 平台后端模块等)
tmp = collect_all('webview')
datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc', 'PySide6', 'PyQt5', 'PyQt6', 'numpy', 'scipy', 'matplotlib'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OYAToolBox',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['OYAToolBoxICO.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='OYAToolBox',
)
