"""Build and validate a standalone Windows GUI, then generate its checksum."""
import hashlib
from pathlib import Path
import subprocess
import sys
from .smoke_tests import test_executable,test_portable_zip
from ..release.package import create_portable_zip

ROOT = Path(__file__).resolve().parents[2]


def main():
    if sys.platform != 'win32':
        raise SystemExit('Build the Windows executable on Windows.')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm',
                    str(ROOT/'LuminaRouteFinder.spec')], cwd=ROOT, check=True)
    test_executable()
    exe=ROOT/'dist/LuminaRouteFinder.exe'
    archive=create_portable_zip(exe,ROOT/'config/gui-settings.json',ROOT/'dist/LuminaRouteFinder-Windows-x64.zip')
    test_portable_zip(archive)
    lines=[f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}' for file in (exe,archive)]
    (ROOT/'dist/SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='ascii')
    print(f'ZIP: {archive}')
    print(f'Built: {exe}')


if __name__ == '__main__':
    main()
