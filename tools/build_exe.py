"""Build and validate a standalone Windows GUI, then generate its checksum."""
import hashlib
from pathlib import Path
import subprocess
import sys
from test_exe import test_executable

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != 'win32':
        raise SystemExit('Build the Windows executable on Windows.')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm',
                    str(ROOT/'LuminaRouteFinder.spec')], cwd=ROOT, check=True)
    test_executable()
    exe=ROOT/'dist/LuminaRouteFinder.exe'
    digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    (ROOT/'dist/SHA256SUMS.txt').write_text(f'{digest}  {exe.name}\n',encoding='ascii')
    print(f'Built: {exe}')


if __name__ == '__main__':
    main()
