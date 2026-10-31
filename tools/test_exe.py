"""Validate the frozen Windows GUI on a full screenshot and a board-only crop."""
import json
import cv2
import numpy as np
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_executable():
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    folder=ROOT/'outputs/exe-smoke'
    folder.mkdir(parents=True,exist_ok=True)
    full=cv2.imdecode(np.fromfile(str(ROOT/'docs/images/sample_image.jpg'),dtype=np.uint8),cv2.IMREAD_COLOR)
    scaled=cv2.resize(full,None,fx=1.75,fy=1.75)
    ok,data=cv2.imencode('.png',scaled)
    if not ok:raise RuntimeError('Cannot encode scaled smoke-test image')
    scaled_source=folder/'scaled_input.png'
    data.tofile(str(scaled_source))
    cases=[('full',ROOT/'docs/images/sample_image.jpg',14),
           ('crop',ROOT/'tests/fixtures/board_crop.jpg',18),
           ('clipboard',ROOT/'tests/fixtures/board_crop.jpg',18),
           ('region',ROOT/'docs/images/sample_image.jpg',14),
           ('scaled_header',scaled_source,14)]
    for name,source,expected in cases:
        report=ROOT/f'outputs/exe-smoke/{name}_report.json'
        report.unlink(missing_ok=True)
        command=[str(ROOT/'dist/LuminaRouteFinder.exe'),'--smoke-test',str(source),'--report',str(report)]
        if name=='clipboard':command.append('--clipboard-test')
        if name=='region':command.append('--region-test')
        if name=='scaled_header':command.append('--scaled-header-test')
        subprocess.run(command,
                       check=True,timeout=90,startupinfo=startup)
        result=json.loads(report.read_text(encoding='utf-8'))
        if result['status']!='ok' or result['max_count']!=expected or not result['has_preview']:
            raise RuntimeError(f'Unexpected frozen GUI result: {result}')
        if not result['cleanup_enabled'] or Path(result['generated_output']).exists():
            raise RuntimeError('Frozen GUI did not clean its generated output on exit')
        if name=='clipboard' and Path(result['input']).exists():
            raise RuntimeError('Frozen GUI did not clean its clipboard input on exit')
        if name=='region' and result['input_region'] != [715,327,975,827]:
            raise RuntimeError('Frozen GUI did not use the selected region')
        print(f'Frozen GUI: {name}, TkDnD and preview verified ({expected} icons).',flush=True)


if __name__=='__main__':
    test_executable()
