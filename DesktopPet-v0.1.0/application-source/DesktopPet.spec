# Build with: .venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath release --workpath work/build DesktopPet.spec
from pathlib import Path
import os
import sys

project = Path(SPECPATH)
diagnostic = os.environ.get('DESKTOPPET_BUILD_CONSOLE') == '1'
# Do not collect unrelated ICU DLLs from tools such as Poppler on the host PATH.
# Qt on supported Windows versions uses Windows' ICU implementation.
windows = Path(os.environ.get('SYSTEMROOT', 'C:/Windows'))
os.environ['PATH'] = os.pathsep.join([str(Path(sys.executable).parent), str(windows / 'System32'), str(windows)])
a = Analysis(
    [str(project / 'main.py')],
    pathex=[str(project)],
    binaries=[],
    datas=[(str(project / 'assets' / 'pet.png'), 'assets'),
           (str(project / 'assets' / 'desktop-pet-icon.ico'), 'assets'),
           (str(project / 'docs' / 'release-notes.txt'), 'docs')],
    hiddenimports=['desktop_pet.diagnostics'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PIL', 'PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtTest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
    name='DesktopPet-diagnostic' if diagnostic else 'DesktopPet-v0.1.0', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=diagnostic, disable_windowed_traceback=False,
    icon=str(project / 'assets' / 'desktop-pet-icon.ico'),
    version=str(project / 'docs' / 'version-info.txt'),
    uac_admin=False)
