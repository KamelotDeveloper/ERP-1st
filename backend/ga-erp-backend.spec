# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

reportlab_datas, reportlab_binaries, reportlab_hiddenimports = collect_all('reportlab')
xhtml2pdf_datas, xhtml2pdf_binaries, xhtml2pdf_hiddenimports = collect_all('xhtml2pdf')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[] + reportlab_binaries + xhtml2pdf_binaries,
     datas=[
          ('.env.example', '.'),
      ] + reportlab_datas + xhtml2pdf_datas,
     hiddenimports=['fastapi', 'uvicorn', 'sqlalchemy', 'pydantic', 'pydantic_settings', 'slowapi', 'passlib', 'passlib.handlers.bcrypt', 'bcrypt', 'alembic', 'openpyxl', 'httpx', 'python_jose', 'python_multipart', 'email_validator', 'jose', 'dotenv', 'starlette', 'anyio', 'click', 'h11', 'idna', 'certifi', 'typing_extensions', 'greenlet', 'mako', 'markupsafe', 'wrapt', 'cryptography', 'ecdsa', 'rsa', 'pyasn1', 'cffi', 'pycparser', 'six', 'packaging', 'limits', 'colorama', 'reportlab', 'reportlab.graphics.barcode', 'reportlab.graphics.barcode.code128', 'reportlab.graphics.barcode.code39', 'reportlab.graphics.barcode.eanbc', 'reportlab.graphics.barcode.usps', 'reportlab.graphics.barcode.widgets', 'xhtml2pdf'] + reportlab_hiddenimports + xhtml2pdf_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook-reportlab-barcodes.py'],
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
