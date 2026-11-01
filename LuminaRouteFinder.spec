# Build with: python -m PyInstaller --noconfirm LuminaRouteFinder.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
a = Analysis(
    [str(root / 'tools' / 'exe_entry.py')],
    pathex=[str(root)],
    binaries=[],
    datas=collect_data_files('lumina_route_finder', includes=['assets/*.png', 'assets/content_icons/*.png']),
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['pytest', 'matplotlib', 'pandas', 'scipy', 'IPython'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='LuminaRouteFinder',
    debug=False, bootloader_ignore_signals=False, strip=False,
    upx=False, console=False,
)
