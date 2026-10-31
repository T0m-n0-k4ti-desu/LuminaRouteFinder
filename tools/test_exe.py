"""Validate the frozen Windows GUI on a full screenshot and a board-only crop."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_executable():
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    cases=[('full',ROOT/'docs/images/sample_image.jpg',14),
           ('crop',ROOT/'tests/fixtures/board_crop.jpg',18),
           ('clipboard',ROOT/'tests/fixtures/board_crop.jpg',18),
           ('region',ROOT/'docs/images/sample_image.jpg',14)]
    for name,source,expected in cases:
        report=ROOT/f'outputs/exe-smoke/{name}_report.json'
        report.unlink(missing_ok=True)
        command=[str(ROOT/'dist/LuminaRouteFinder.exe'),'--smoke-test',str(source),'--report',str(report)]
        if name=='clipboard':command.append('--clipboard-test')
        if name=='region':command.append('--region-test')
        subprocess.run(command,
                       check=True,timeout=45,startupinfo=startup)
        result=json.loads(report.read_text(encoding='utf-8'))
        if result['status']!='ok' or result['max_count']!=expected or not result['has_preview']:
            raise RuntimeError(f'Unexpected frozen GUI result: {result}')
        if name=='region' and result['input_region'] != [715,327,975,827]:
            raise RuntimeError('Frozen GUI did not use the selected region')
        print(f'Frozen GUI: {name}, TkDnD and preview verified ({expected} icons).',flush=True)


if __name__=='__main__':
    test_executable()
