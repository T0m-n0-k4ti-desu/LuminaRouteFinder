from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import cv2
import numpy as np
from lumina_route_finder.recognition.contents import CONTENT_NAMES, classify_contents
from lumina_route_finder.recognize import recognize, read_image, RecognitionError
from lumina_route_finder.__main__ import run_image

ROOT = Path(__file__).resolve().parents[1]
# Visually checked against the supplied labelled symbols, row by row.
EXPECTED = [
    ['role_combat','element_tiles','element_combat','scales_of_sin','ancient_weapon_core'],
    ['two_faced_monarch','element_tiles','boss_mutation','element_tiles','ancient_weapon_core'],
    ['role_combat','scales_of_sin','wheel_of_fate','escape_room','ancient_weapon_core'],
    ['escape_room','boss_mutation','two_faced_monarch','debuff_dispersion','scales_of_sin'],
    ['wheel_of_fate','wheel_of_fate','wheel_of_fate','scales_of_sin','role_combat'],
    ['wheel_of_fate','escape_room','wheel_of_fate','wheel_of_fate','debuff_dispersion'],
    ['scales_of_sin','overheat_control','element_combat','ancient_weapon_core','role_combat'],
    ['boss_mutation','boss_mutation','wheel_of_fate','role_combat','ancient_weapon_core'],
    ['boss_mutation','ancient_weapon_core','two_faced_monarch','role_combat','escape_room'],
    ['overheat_control','wheel_of_fate','element_combat','element_survival','two_faced_monarch'],
]


class ContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT/'docs/images/sample_image.jpg'
        cls.full = read_image(cls.source)

    def test_all_fifty_labels_in_scaled_and_compressed_images(self):
        variants = [cv2.resize(self.full,None,fx=scale,fy=scale) for scale in (1., .75, 1.75)]
        ok,data = cv2.imencode('.jpg',self.full,[cv2.IMWRITE_JPEG_QUALITY,70])
        self.assertTrue(ok)
        variants.append(cv2.imdecode(data,cv2.IMREAD_COLOR))
        for index,image in enumerate(variants):
            with self.subTest(variant=index):
                board = recognize(image)[0]
                labels,_ = classify_contents(board)
                self.assertEqual([[labels[r,c] for c in range(5)] for r in range(10)],EXPECTED)

    def test_unknown_symbol_is_rejected(self):
        board = recognize(self.full)[0]
        board[12:39,16:43] = 128
        with self.assertRaises(RecognitionError) as caught:
            classify_contents(board)
        self.assertEqual(caught.exception.issues[0]['code'],'AMBIGUOUS_CONTENT')

    def test_default_search_identifies_types_without_filtering_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_image(self.source,Path(temp))
        board,_,edges,_,_ = recognize(self.full)
        from lumina_route_finder.solver import solve
        expected = solve([(r,c) for r in range(10) for c in range(5)],edges)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['max_count'],expected['max_count'])
        self.assertEqual(result['optimal_path_count'],expected['optimal_path_count'])
        self.assertEqual(result['paths'],[[[r+1,c+1] for r,c in path] for path in expected['paths']])
        self.assertEqual(result['content_types'],EXPECTED)
        self.assertNotIn('filters',result)

    def test_unknown_content_does_not_block_unfiltered_search(self):
        board,origin,edges,diagnostics,score = recognize(self.full)
        board[12:39,16:43] = 128
        labels,_ = classify_contents(board, strict=False)
        self.assertIsNone(labels[0,0])
        self.assertEqual(labels[0,1],EXPECTED[0][1])
        with tempfile.TemporaryDirectory() as temp, patch('lumina_route_finder.analysis.recognize',
                return_value=(board,origin,edges,diagnostics,score)):
            result = run_image(self.source,Path(temp))
            strict = run_image(self.source,Path(temp)/'strict',avoid_repeated=True)
        self.assertEqual(result['status'],'ok')
        self.assertIsNone(result['content_types'][0][0])
        self.assertEqual(strict['status'],'error')
        self.assertEqual(strict['errors'][0]['code'],'AMBIGUOUS_CONTENT')

    def test_excluded_bottleneck_returns_partial_unless_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            result=run_image(self.source,Path(temp),excluded_types=['wheel_of_fate'])
            self.assertTrue((Path(temp)/'route.png').exists())
            strict=run_image(self.source,Path(temp)/'strict',excluded_types=['wheel_of_fate'],fallback_priority=None)
        self.assertEqual(result['status'],'partial')
        self.assertFalse(result['goal_reached'])
        self.assertLess(result['reached_stage'],10)
        self.assertGreater(result['max_count'],0)
        for path in result['paths']:
            self.assertEqual(path[-1][0],result['reached_stage'])
            self.assertTrue(all(EXPECTED[r-1][c-1]!='wheel_of_fate' for r,c in path))
        self.assertEqual(strict['status'],'no_path')
        self.assertEqual(strict['paths'],[])
        self.assertIsNone(strict['max_count'])

    def test_filters_alone_and_combined(self):
        for repeat, excluded in [(True,()),(False,('boss_mutation',)),(True,('boss_mutation',))]:
            with self.subTest(repeat=repeat,excluded=excluded), tempfile.TemporaryDirectory() as temp:
                result = run_image(self.source,Path(temp),avoid_repeated=repeat,excluded_types=excluded)
                self.assertEqual(result['status'],'ok')
                self.assertEqual(result['content_types'],EXPECTED)
                for path in result['paths']:
                    kinds = [EXPECTED[r-1][c-1] for r,c in path]
                    self.assertFalse(set(kinds)&set(excluded))
                    if repeat:
                        self.assertTrue(all(a!=b for a,b in zip(kinds,kinds[1:])))


if __name__=='__main__':
    unittest.main()
