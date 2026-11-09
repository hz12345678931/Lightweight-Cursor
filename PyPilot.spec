# Windows x64 onedir build. The console worker preserves MCP stdio.
from pathlib import Path
import importlib.metadata
import sys
from PyInstaller.utils.hooks import copy_metadata
root = Path(SPECPATH)
metadata = []
# Some Python distributions ship an SSL trust-policy resource beside ssl.py.
# Preserve that resource when freezing instead of changing certificate checks.
trust_policy = Path(sys.base_prefix) / 'Lib/codex-rejected-cas.pem'
if trust_policy.is_file():
    metadata.append((str(trust_policy), '.'))
for dist in importlib.metadata.distributions():
    metadata += copy_metadata(dist.metadata['Name'])
a = Analysis(
    [str(root / 'launch.py')], pathex=[str(root)],
    binaries=[],
    datas=[(str(root/'ui'), 'ui'), (str(root/'demo_project'), 'demo_project'),
           (str(root/'runtime'), 'runtime'), (str(root/'THIRD_PARTY_NOTICES.md'), '.')] + metadata,
    hiddenimports=['webview.platforms.edgechromium', 'pypilot.sample_mcp',
                   'uvicorn.logging', 'uvicorn.loops.asyncio', 'uvicorn.protocols.http.h11_impl',
                   'uvicorn.lifespan.on', 'win32api', 'win32job'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
desktop = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PyPilot',
              debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
              console=False, icon=str(root/'assets/pypilot.ico'))
worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PyPilot-worker',
             debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
             console=True, icon=str(root/'assets/pypilot.ico'))
coll = COLLECT(desktop, worker, a.binaries, a.datas, strip=False, upx=False, name='PyPilot')
