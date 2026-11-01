"""Rebuild committed templates from the original external sample folders."""
import argparse
from pathlib import Path
import cv2
import numpy as np


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('sample_root',type=Path,help='Directory containing sample_image and error_images')
    args=parser.parse_args()
    out=Path(__file__).resolve().parents[2]/'lumina_route_finder/assets'
    out.mkdir(parents=True,exist_ok=True)
    specs=[('sample_image/TWCI_2026_11_1_1_2_47.jpg',(633,237,1286,265),'window.png'),
           ('error_images/TWCI_2026_11_1_1_29_33.jpg',(805,455,838,488),'cursor.png')]
    for source,(x1,y1,x2,y2),name in specs:
        image=cv2.imdecode(np.fromfile(str(args.sample_root/source),dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f'Cannot read {source}')
        ok,data=cv2.imencode('.png',image[y1:y2,x1:x2])
        if not ok:
            raise ValueError(f'Cannot encode {name}')
        data.tofile(str(out/name))


if __name__=='__main__':
    main()
