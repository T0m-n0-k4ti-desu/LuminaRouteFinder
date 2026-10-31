"""Validate the frozen Windows GUI without requiring Python on its runtime path."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_executable():
    report = ROOT / 'outputs/exe-smoke/report.json'
    report.unlink(missing_ok=True)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    subprocess.run([str(ROOT/'dist/LuminaRouteFinder.exe'),
                    '--smoke-test', str(ROOT/'docs/images/sample_image.jpg'),
                    '--report', str(report)], check=True, timeout=45, startupinfo=startup)
    result = json.loads(report.read_text(encoding='utf-8'))
    if result['status'] != 'ok' or result['max_count'] != 14 or not result['has_preview']:
        raise RuntimeError(f'Unexpected frozen GUI result: {result}')
    print('Frozen GUI: TkDnD, recognition and preview verified (14 icons).')


if __name__ == '__main__':
    test_executable()
