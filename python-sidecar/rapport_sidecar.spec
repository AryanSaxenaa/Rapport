# -*- mode: python ; coding: utf-8 -*-
# Run from python-sidecar/:  pyinstaller rapport_sidecar.spec
# Output: python-sidecar/dist/rapport-sidecar/rapport-sidecar[.exe]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('.env', '.') if __import__('os').path.exists('.env') else ('rapport_contacts.json', '.'),
    ],
    hiddenimports=[
        # uvicorn internals
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # pydantic / fastapi
        'pydantic',
        'pydantic.v1',
        'fastapi',
        'starlette',
        'starlette.routing',
        'starlette.middleware',
        # email stdlib (used in email_file_reader, imap_reader)
        'email',
        'email.mime',
        'email.mime.text',
        'email.mime.multipart',
        'email.policy',
        # audio (sounddevice may bundle portaudio separately)
        'sounddevice',
        'numpy',
        # HydraDB SDK
        'hydra_db',
        'httpx',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
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
    name='rapport-sidecar',
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='rapport-sidecar',
)
