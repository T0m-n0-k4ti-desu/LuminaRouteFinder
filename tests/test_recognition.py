import json
import os
from pathlib import Path
import unittest
import cv2
import numpy as np
from lumina_route_finder.recognize import RecognitionError, recognize, read_image
from lumina_route_finder.solver import solve

ROOT=Path(os.environ.get('LUMINA_SAMPLE_ROOT',str(Path(__file__).resolve().parents[2])))
NORMAL=ROOT/'sample_image'
ERROR=ROOT/'error_images'


@unittest.skipUnless(NORMAL.is_dir() and ERROR.is_dir(),'External sample folders not available; set LUMINA_SAMPLE_ROOT')
class RecognitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first=read_image(NORMAL/'TWCI_2026_11_1_1_2_47.jpg')
        cls.reference=recognize(cls.first)

    def test_all_normal_samples(self):
        files=sorted(NORMAL.glob('*.jpg'))
        self.assertEqual(len(files),14)
        for f in files:
            with self.subTest(image=f.name):
                _,_,edges,_,_=recognize(read_image(f))
                result=solve([(r,c) for r in range(10) for c in range(5)],edges)
                self.assertEqual(result['status'],'ok')

    def test_visually_reviewed_first_board(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/first_board.json').read_text(encoding='utf-8-sig'))
        expected=[]
        for row,pairs in fixture['horizontal'].items():
            expected.extend([((int(row)-1,a-1),(int(row)-1,b-1)) for a,b in pairs])
        for row,pairs in fixture['down'].items():
            expected.extend([((int(row)-1,a-1),(int(row),b-1)) for a,b in pairs])
        edges=self.reference[2]
        self.assertEqual(set(edges),set(expected))
        self.assertNotIn(((4,0),(5,0)),edges)
        result=solve([(r,c) for r in range(10) for c in range(5)],expected)
        self.assertEqual(result['max_count'],fixture['max_count'])

    def test_error_samples(self):
        expected={'1_28_51':'INCOMPLETE_BOARD','1_29_1':'INCOMPLETE_BOARD',
                  '1_29_4':'INCOMPLETE_BOARD','1_29_33':'CURSOR_OCCLUSION',
                  '1_29_35':'CURSOR_OCCLUSION'}
        for suffix,code in expected.items():
            with self.subTest(image=suffix):
                with self.assertRaises(RecognitionError) as caught:
                    recognize(read_image(ERROR/f'TWCI_2026_11_1_{suffix}.jpg'))
                self.assertEqual([i['code'] for i in caught.exception.issues],[code])

    def test_background_and_right_panel_do_not_change_graph(self):
        rng=np.random.default_rng(7)
        changed=rng.integers(0,256,self.first.shape,dtype=np.uint8)
        # Only the header and board survive; everything else is unrelated noise.
        changed[237:265,633:1286]=self.first[237:265,633:1286]
        changed[327:827,715:975]=self.first[327:827,715:975]
        self.assertEqual(recognize(changed)[2],self.reference[2])

    def test_window_translation(self):
        changed=np.zeros_like(self.first)
        # Shift the complete window left 117px and down 31px.
        changed[268:874,516:1171]=self.first[237:843,633:1288]
        result=recognize(changed)
        self.assertEqual(result[1],(598,358))
        self.assertEqual(result[2],self.reference[2])

    def test_cursor_partly_outside_board(self):
        from lumina_route_finder.recognize import ASSETS
        changed=self.first.copy()
        cursor=read_image(ASSETS/'cursor.png')
        changed[477:510,705:738]=cursor
        with self.assertRaises(RecognitionError) as caught:
            recognize(changed)
        self.assertIn('CURSOR_OCCLUSION',[i['code'] for i in caught.exception.issues])

    def test_missing_icon_rejected(self):
        changed=self.first.copy()
        changed[780:825,922:968]=(230,215,200)
        with self.assertRaises(RecognitionError) as caught:
            recognize(changed)
        self.assertIn('INVALID_BOARD_STRUCTURE',[i['code'] for i in caught.exception.issues])

    def test_unsupported_scale_and_cropped_board_rejected(self):
        for image in [cv2.resize(self.first,None,fx=.5,fy=.5),self.first[:700]]:
            with self.assertRaises(RecognitionError):
                recognize(image)

    def test_multiple_windows_rejected(self):
        changed=np.zeros((1080,2600,3),dtype=np.uint8)
        window=self.first[237:843,633:1288]
        changed[100:706,100:755]=window
        changed[100:706,1400:2055]=window
        with self.assertRaises(RecognitionError) as caught:
            recognize(changed)
        self.assertEqual(caught.exception.issues[0]['code'],'MULTIPLE_BOARDS')


if __name__=='__main__':
    unittest.main()
