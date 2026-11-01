import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from lumina_route_finder.analysis import run_image
from lumina_route_finder.analysis_session import AnalysisCache,AnalysisCancelled
from lumina_route_finder.domain.solver import solve
ROOT=Path(__file__).resolve().parents[1]
class SessionTests(unittest.TestCase):
    def test_reuses_recognition_for_options_and_limits_and_invalidates_source_or_region(self):
        import lumina_route_finder.analysis as analysis
        cache=AnalysisCache()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'input.jpg';source.write_bytes((ROOT/'docs/images/sample_image.jpg').read_bytes())
            with patch.object(analysis,'recognize',wraps=analysis.recognize) as recognize:
                first=run_image(source,root/'a',cache=cache)
                next_result=run_image(source,root/'b',cache=cache,limit=1,excluded_types=['escape_room'])
                self.assertEqual(recognize.call_count,1)
                self.assertTrue(next_result['recognition_reused'])
                self.assertFalse(first['recognition_reused'])
                source.write_bytes(source.read_bytes()+b'changed')
                run_image(source,root/'c',cache=cache)
                self.assertEqual(recognize.call_count,2)
                run_image(source,root/'d',cache=cache,region=(715,327,975,827))
                self.assertEqual(recognize.call_count,3)
                reused=run_image(source,root/'e',cache=cache,region=(715,327,975,827))
                self.assertTrue((root/'e/input.png').is_file())
                self.assertTrue(reused['recognition_reused'])
    def test_hash_input_read_error_keeps_input_error_code(self):
        cache=AnalysisCache()
        with tempfile.TemporaryDirectory() as temp,patch.object(cache,'signature',side_effect=PermissionError('cannot read')):
            result=run_image(ROOT/'docs/images/sample_image.jpg',Path(temp),cache=cache)
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['errors'][0]['code'],'INPUT_READ_ERROR')

    def test_cancel_does_not_cache_unfinished_recognition_and_can_restart(self):
        event=threading.Event();cache=AnalysisCache()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def progress(stage):
                if stage=='コンテンツを判定中':event.set()
            with self.assertRaises(AnalysisCancelled):run_image(ROOT/'docs/images/sample_image.jpg',root/'a',cache=cache,cancel=event,progress=progress)
            self.assertIsNone(cache.snapshot)
            event.clear()
            result=run_image(ROOT/'docs/images/sample_image.jpg',root/'b',cache=cache,cancel=event)
            self.assertEqual(result['status'],'ok')
        event.set()
        with self.assertRaises(AnalysisCancelled):solve([(0,0)],[],cancel=event)
if __name__=='__main__':unittest.main()
