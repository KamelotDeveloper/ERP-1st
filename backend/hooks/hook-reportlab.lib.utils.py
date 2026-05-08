# PyInstaller build-time hook for reportlab.lib.utils
#
# This hook runs DURING the build phase (Analysis step), not at runtime.
# It registers a post-import hook that will patch rl_exec IMMEDIATELY
# after reportlab.lib.utils is imported, BEFORE any other module (like
# reportlab.graphics.barcode.widgets) can capture the original exec().

from PyInstaller.utils.hooks import install_on_import

def _patch_rl_exec(module):
    """Post-import callback: replaces rl_exec with a version that uses
    __import__ directly for from-import patterns, which works correctly
    in PyInstaller frozen apps."""
    import builtins
    
    _original_rl_exec = module.rl_exec
    
    def _patched_rl_exec(code, ns):
        if code.startswith('from ') and ' import ' in code:
            parts = code.strip().split()
            if len(parts) == 4 and parts[0] == 'from' and parts[2] == 'import':
                modname = parts[1]
                attr = parts[3]
                try:
                    mod = __import__(modname, fromlist=[attr])
                    ns[attr] = getattr(mod, attr)
                    return
                except Exception:
                    pass
        _original_rl_exec(code, ns)
    
    module.rl_exec = _patched_rl_exec

# Register the callback to run IMMEDIATELY after reportlab.lib.utils is loaded
install_on_import('reportlab.lib.utils', _patch_rl_exec)
