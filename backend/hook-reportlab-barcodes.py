# PyInstaller runtime hook for reportlab barcode dynamic imports.
#
# PROBLEM: reportlab/graphics/barcode/__init__._reset() uses exec() for
# dynamic imports (from reportlab.graphics.barcode.code128 import Code128).
# In PyInstaller frozen apps, this fails because the FrozenImporter cannot
# resolve submodules of a package that is STILL being initialized.
#
# SOLUTION: Pre-register a minimal package for reportlab.graphics.barcode
# in sys.modules BEFORE any import triggers _reset(). This prevents Python
# from executing __init__.py (and thus _reset()). Then we load all needed
# submodules via the FrozenImporter. When the REAL import eventually
# triggers from xhtml2pdf, all submodules are already cached in sys.modules.

import sys
import types
import importlib.util

def _preload_barcode_submodules():
    """Pre-register reportlab.graphics.barcode submodules in sys.modules
    by injecting a fake package before the real __init__.py runs."""
    
    # Step 1: Ensure parent packages exist in sys.modules
    import reportlab
    import reportlab.graphics
    
    # Step 2: Create a minimal package module for reportlab.graphics.barcode
    # This prevents Python from executing __init__.py (and _reset())
    fake_pkg = types.ModuleType('reportlab.graphics.barcode')
    fake_pkg.__path__ = []  # FrozenImporter will provide the real path
    fake_pkg.__package__ = 'reportlab.graphics.barcode'
    fake_pkg.__file__ = None
    fake_pkg.__loader__ = None
    
    # Register BEFORE any import tries to load the real package
    sys.modules['reportlab.graphics.barcode'] = fake_pkg
    
    # Step 3: Now iterate all FrozenImporters to find and load submodules
    barcode_modules = [
        'reportlab.graphics.barcode.code128',
        'reportlab.graphics.barcode.code39',
        'reportlab.graphics.barcode.code93',
        'reportlab.graphics.barcode.common',
        'reportlab.graphics.barcode.eanbc',
        'reportlab.graphics.barcode.usps',
        'reportlab.graphics.barcode.usps4s',
        'reportlab.graphics.barcode.ecc200datamatrix',
        'reportlab.graphics.barcode.fourstate',
        'reportlab.graphics.barcode.lto',
        'reportlab.graphics.barcode.qr',
        'reportlab.graphics.barcode.qrencoder',
        'reportlab.graphics.barcode.dmtx',
        'reportlab.graphics.barcode.widgets',
    ]
    
    loaded = 0
    for modname in barcode_modules:
        if modname in sys.modules:
            loaded += 1
            continue
        # Find the module via FrozenImporter
        for importer in sys.meta_path:
            if hasattr(importer, 'find_spec'):
                spec = importer.find_spec(modname)
                if spec is not None:
                    try:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[modname] = mod
                        spec.loader.exec_module(mod)
                        loaded += 1
                    except Exception:
                        # Remove partial module on failure
                        if modname in sys.modules:
                            del sys.modules[modname]
                    break
    
    # Step 4: Replace fake package with a real one by importing __init__
    # Since all submodules are already cached, _reset()'s exec() should
    # find them in sys.modules and succeed.
    try:
        del sys.modules['reportlab.graphics.barcode']
        import reportlab.graphics.barcode
    except Exception:
        # If all else fails, restore the fake package with the paths
        # so imports resolve from sys.modules cache
        if 'reportlab.graphics.barcode' not in sys.modules:
            sys.modules['reportlab.graphics.barcode'] = fake_pkg
        # Try to locate the real path from FrozenImporter
        for importer in sys.meta_path:
            if hasattr(importer, 'toc'):
                # FrozenImporter has a toc - try to find barcode package path
                for key in dir(importer):
                    if 'barcode' in str(getattr(importer, key, '')):
                        pass
                break

_preload_barcode_submodules()
