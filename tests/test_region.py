from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np
from lumina_route_finder.__main__ import run_image,write_image
from lumina_route_finder.recognize import read_image

ROOT=Path(__file__).resolve().parents[1]


class RegionTests(unittest.TestCase):
    def test_region_selects_one_of_two_complete_boards(self):
        crop=read_image(ROOT/'tests/fixtures/board_crop.jpg')
        image=np.zeros((550,650,3),dtype=np.uint8)
        image[20:516,20:269]=crop
        image[20:516,350:599]=crop
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'two.png';write_image(source,image)
            automatic=run_image(source,root/'auto')
            self.assertEqual(automatic['errors'][0]['code'],'MULTIPLE_BOARDS')
            selected=run_image(source,root/'selected',region=(350,20,599,516))
            self.assertEqual(selected['status'],'ok')
            self.assertEqual(selected['max_count'],18)
            self.assertEqual(selected['input_region'],[350,20,599,516])
            self.assertEqual(read_image(root/'selected/input.png').shape,crop.shape)
            self.assertGreater(selected['board_origin'][0],340)

    def test_invalid_or_incomplete_region_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=ROOT/'tests/fixtures/board_crop.jpg'
            for i,box in enumerate([(-1,0,200,400),(0,0,5,5),(0,0,1000,1000)]):
                result=run_image(source,root/str(i),region=box)
                self.assertEqual(result['errors'][0]['code'],'INVALID_REGION')
            partial=run_image(source,root/'partial',region=(0,0,249,400))
            self.assertEqual(partial['status'],'error')
            self.assertNotIn('max_count',partial)


if __name__=='__main__':
    unittest.main()
