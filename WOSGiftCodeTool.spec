# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('model', 'model')],
    hiddenimports=['onnxruntime', 'bs4', 'core', 'gui', 'scraper'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['ddddocr', 'lxml', 'lxml.etree', 'lxml.objectify', 'lxml.isoschematron', 'lxml.html', 'scipy', 'pandas', 'matplotlib', 'tensorflow', 'keras', 'easyocr', 'torch', 'torchvision', 'PIL.ImageQt', 'PIL.ImageTk', 'tkinter.test', 'unittest', 'xmlrpc', 'pydoc', 'doctest', 'lib2to3', 'curses', 'setuptools', 'pip', 'email.test', 'test', 'tests', 'sqlite3', 'ctypes.test', 'distutils', 'ensurepip', 'venv', 'zipimport'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WOSGiftCodeTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
