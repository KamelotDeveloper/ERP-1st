# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('carpinteria.db', '.'),
        ('.env.example', '.'),
    ],
    hiddenimports=['fastapi', 'uvicorn', 'sqlalchemy', 'pydantic', 'pydantic_settings', 'slowapi', 'passlib', 'passlib.handlers.bcrypt', 'bcrypt', 'alembic', 'openpyxl', 'httpx', 'python_jose', 'python_multipart', 'email_validator', 'jose', 'dotenv', 'starlette', 'anyio', 'click', 'h11', 'idna', 'certifi', 'typing_extensions', 'greenlet', 'mako', 'markupsafe', 'wrapt', 'cryptography', 'ecdsa', 'rsa', 'pyasn1', 'cffi', 'pycparser', 'six', 'packaging', 'limits', 'colorama'],
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
    a.binaries,
    a.datas,
    [],
    name='ga-erp-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
