# -*- mode: python ; coding: utf-8 -*-

import importlib
import os
import sys

def get_pynput_module():
    '''Adapted from pystray.__init__'''
    backend_name = os.environ.get('PYSTRAY_BACKEND', None)
    if backend_name:
        modules = (backend_name,)
    elif sys.platform == 'darwin':
        modules = ('darwin',)
    elif sys.platform == 'win32':
        modules = ('win32',)
    else:
        modules = ('appindicator', 'gtk', 'xorg')
    for module in modules:
        try:
            importlib.import_module(f'pynput.keyboard._{module}')
            return module
        except ImportError:
            pass
    raise ImportError(f'Unsupported platform: {sys.platform}')

def get_hidden_imports():
    pynput_module = get_pynput_module()
    return [
        f'pynput.keyboard._{pynput_module}',
        f'pynput.mouse._{pynput_module}',
    ]

block_cipher = None
a = Analysis(
    ['src/app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('res', 'res')],
    hiddenimports=get_hidden_imports(),
    hookspath=[],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)
