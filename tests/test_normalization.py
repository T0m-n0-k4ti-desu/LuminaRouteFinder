from pathlib import Path
import os
import unittest
import cv2
import numpy as np
from lumina_route_finder.recognize import RecognitionError,read_image,recognize
from lumina_route_finder.solver import solve

ROOT=Path(__file__).resolve().parents[1]
EXTERNAL=Path(os.environ.get('LUMINA_SAMPLE_ROOT',str(ROOT.parent)))


class NormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full=read_image(ROOT/'docs/images/sample_image.jpg')
        cls.expected=set(recognize(cls.full)[2])

    def assert_same_graph(self,image,expected=None):
        self.assertEqual(set(recognize(image)[2]),self.expected if expected is None else expected)

    def test_scaled_header_recovers_when_grid_detection_misses(self):
        from unittest.mock import patch
        scale = 1.75
        image = cv2.resize(self.full, None, fx=scale, fy=scale)
        with patch('lumina_route_finder.locate.find_grids', return_value=[]):
            board, origin, edges, _, _ = recognize(image)
        self.assertEqual(board.shape, (500, 260, 3))
        self.assertEqual(set(edges), self.expected)
        for actual, expected in zip(origin, (715*scale, 327*scale)):
            self.assertAlmostEqual(actual, expected, delta=2)

    def test_scaled_header_ignores_covered_window_and_rejects_two_boards(self):
        from lumina_route_finder.recognize import locate_scaled_header
        window = cv2.resize(self.full[237:843,633:1288], None, fx=1.25, fy=1.25)
        h, w = window.shape[:2]
        image = np.zeros((h+40, 2*w+80, 3), np.uint8)
        image[20:20+h,20:20+w] = window
        # Only the other title is visible; its covered board must not count.
        image[20:55,w+50:w+50+w] = window[:35]
        board, _, _, _ = locate_scaled_header(image)
        self.assertEqual(board.shape, (500,260,3))
        image[20:20+h,w+50:w+50+w] = window
        with self.assertRaises(RecognitionError) as caught:
            locate_scaled_header(image)
        self.assertEqual(caught.exception.issues[0]['code'], 'MULTIPLE_BOARDS')

    def test_board_only_crop(self):
        self.assert_same_graph(self.full[327:827,715:975])
        # Tight margins around the icons; header/side labels are absent.
        self.assert_same_graph(self.full[330:825,721:970])

    def test_scaled_images_preserve_every_connection(self):
        for scale in [.75,.9,.98,1.02,1.1,1.25,1.5,2]:
            with self.subTest(scale=scale):
                self.assert_same_graph(cv2.resize(self.full,None,fx=scale,fy=scale))

    def test_independent_horizontal_and_vertical_scaling(self):
        for sx,sy in [(1.15,.9),(.8,1.2)]:
            with self.subTest(scale=(sx,sy)):
                self.assert_same_graph(cv2.resize(self.full,None,fx=sx,fy=sy))

    def test_jpeg_recompression_preserves_every_connection(self):
        for quality in [90,70,40,20]:
            with self.subTest(quality=quality):
                ok,data=cv2.imencode('.jpg',self.full,[cv2.IMWRITE_JPEG_QUALITY,quality])
                self.assertTrue(ok)
                self.assert_same_graph(cv2.imdecode(data,cv2.IMREAD_COLOR))

    def test_supplied_crop(self):
        crop=read_image(ROOT/'tests/fixtures/board_crop.jpg')
        _,_,edges,_,_=recognize(crop)
        result=solve([(r,c) for r in range(10) for c in range(5)],edges)
        self.assertEqual(result['max_count'],18)
        full_source=EXTERNAL/'passan_image/TWCI_2026_10_9_22_9_36.jpg'
        if full_source.is_file():
            self.assert_same_graph(crop,set(recognize(read_image(full_source))[2]))

    def test_cropped_out_icons_are_rejected(self):
        crop=self.full[327:827,715:975]
        for image in [crop[:450],crop[:,50:]]:
            with self.assertRaises(RecognitionError):
                recognize(image)

    def test_multiple_board_crops_are_rejected(self):
        crop=self.full[327:827,715:975]
        combined=np.zeros((550,650,3),np.uint8)
        combined[10:510,10:270]=crop
        combined[10:510,350:610]=crop
        with self.assertRaises(RecognitionError) as caught:
            recognize(combined)
        self.assertEqual(caught.exception.issues[0]['code'],'MULTIPLE_BOARDS')

    def test_scaled_error_examples_remain_errors(self):
        files=[('TWCI_2026_11_1_1_28_51.jpg','INCOMPLETE_BOARD'),
               ('TWCI_2026_11_1_1_29_33.jpg','CURSOR_OCCLUSION')]
        for name,code in files:
            source=EXTERNAL/'error_images'/name
            if not source.is_file():
                self.skipTest('External error samples unavailable')
            with self.subTest(error=code):
                image=cv2.resize(read_image(source),None,fx=.75,fy=.75)
                with self.assertRaises(RecognitionError) as caught:
                    recognize(image)
                self.assertIn(code,[x['code'] for x in caught.exception.issues])


if __name__=='__main__':
    unittest.main()
